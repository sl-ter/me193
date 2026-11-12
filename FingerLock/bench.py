#!/usr/bin/env python3
"""How fast the safe runs: laptop vs UNO Q, for section 4 of the write-up.

    python FingerLock/bench.py                # laptop: time the network on 200 camera-sized frames
    python FingerLock/bench.py --runs         # laptop: summarise laptop_lock.py's live logs (runs/*.csv)
    python FingerLock/bench.py --board 60     # UNO Q: listen to the board's own timings for 60 s (MQTT)

Each mode adds its numbers to figures/bench.json and prints the whole table,
so run all three and paste the table into Notion. The board times itself
(main.py publishes frames per second and milliseconds per frame in its
status), so its numbers are the real thing, camera included.
"""
import argparse
import csv
import json
import platform
import statistics
import time
from datetime import datetime

import numpy as np

from common import BROKER, FIG_DIR, MODEL_PATH, PORT, RUNS_DIR, load_codes
import fingernet as FN

BENCH_PATH = FIG_DIR / "bench.json"


def med(xs):
    return round(statistics.median(xs), 2) if xs else None


def p90(xs):
    return round(float(np.percentile(xs, 90)), 2) if xs else None


def laptop(n=200):
    net = FN.FingerNet(MODEL_PATH) if MODEL_PATH.exists() else FN.FingerNet(weights=FN.random_weights())
    rng = np.random.default_rng(0)
    frames = [rng.integers(0, 256, (480, 640, 3)).astype(np.uint8) for _ in range(20)]
    prep, run = [], []
    for k in range(n):
        t0 = time.perf_counter()
        x = FN.prepare(frames[k % len(frames)])
        t1 = time.perf_counter()
        net.forward(x)
        prep.append((t1 - t0) * 1000)
        run.append((time.perf_counter() - t1) * 1000)
    out = {"what": "network only, 640x480 frames, no camera", "frames": n,
           "prepare_ms": med(prep), "numpy_net_ms": med(run), "numpy_net_ms_p90": p90(run),
           "machine": f"{platform.system()} {platform.machine()}", "when": datetime.now().isoformat(timespec="minutes")}
    try:
        import torch
        import train
        tnet = train.Net().eval()
        tnet.load_state_dict({f"{name}.{'weight' if k == 'w' else 'bias'}": torch.from_numpy(net.w[f"{name}_{k}"])
                              for name in ("conv1", "conv2", "conv3", "fc", "count", "owner") for k in ("w", "b")})
        x = torch.from_numpy(FN.prepare(frames[0])[None])
        for threads in (torch.get_num_threads(), 1):
            torch.set_num_threads(threads)
            times = []
            with torch.no_grad():
                for _ in range(n):
                    t0 = time.perf_counter()
                    tnet(x)
                    times.append((time.perf_counter() - t0) * 1000)
            out[f"torch_net_ms_{threads}_threads"] = med(times)
    except Exception as e:
        out["torch"] = f"skipped: {e!r}"
    return out


def runs():
    files = sorted(RUNS_DIR.glob("laptop_*.csv"))
    fps, prep, net = [], [], []
    for f in files:
        rows = list(csv.DictReader(open(f)))
        rows = rows[len(rows) // 5:]            # skip the first 20% (camera warming up)
        fps += [float(r["fps"]) for r in rows if r["fps"]]
        prep += [float(r["prep_ms"]) for r in rows]
        net += [float(r["net_ms"]) for r in rows]
    return {"what": "laptop_lock.py, live with the camera", "files": len(files), "frames": len(prep),
            "fps": med(fps), "prepare_ms": med(prep), "numpy_net_ms": med(net), "numpy_net_ms_p90": p90(net)}


def board(seconds):
    import paho.mqtt.client as mqtt
    _, _, topic = load_codes()
    got = []

    def on_connect(cl, userdata, flags, rc, props):
        cl.subscribe(topic + "/status")

    def on_message(cl, userdata, msg):
        try:
            d = json.loads(msg.payload)
        except ValueError:
            return
        if d.get("platform") == "UNO Q":
            got.append(d)

    cl = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"safe-bench-{int(time.time())}")
    cl.on_connect, cl.on_message = on_connect, on_message
    cl.connect(BROKER, PORT, keepalive=15)
    cl.loop_start()
    print(f"Listening to the board on {topic}/status for {seconds} s ...")
    time.sleep(seconds)
    cl.loop_stop()
    if not got:
        raise SystemExit("Heard nothing from the board. Is the safe app running, with the same codes.json?")
    return {"what": "the board's own timing (main.py status), live with its camera", "messages": len(got),
            "fps": med([d["fps"] for d in got]), "prepare_ms": med([d["prep_ms"] for d in got]),
            "numpy_net_ms": med([d["net_ms"] for d in got])}


def table(b):
    rows = [("", "laptop, network only", "laptop, live", "UNO Q, live")]
    keys = [("frames per second", "fps"), ("prepare a frame (ms)", "prepare_ms"), ("network, numpy (ms)", "numpy_net_ms"),
            ("network, PyTorch (ms)", None)]
    for name, k in keys:
        lap = b.get("laptop", {})
        val = (next((v for kk, v in lap.items() if kk.startswith("torch_net_ms")), None) if k is None else lap.get(k))
        rows.append((name, val, b.get("laptop_live", {}).get(k) if k else None, b.get("board", {}).get(k) if k else None))
    widths = [max(len(str(r[i])) for r in rows) for i in range(4)]
    lines = ["| " + " | ".join(str("-" if v is None else v).ljust(widths[i]) for i, v in enumerate(r)) + " |" for r in rows]
    lines.insert(1, "|" + "|".join("-" * (w + 2) for w in widths) + "|")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", action="store_true")
    ap.add_argument("--board", type=float, metavar="SECONDS")
    args = ap.parse_args()
    b = json.loads(BENCH_PATH.read_text()) if BENCH_PATH.exists() else {}
    if args.board:
        b["board"] = board(args.board)
    elif args.runs:
        b["laptop_live"] = runs()
    else:
        b["laptop"] = laptop()
    FIG_DIR.mkdir(exist_ok=True)
    BENCH_PATH.write_text(json.dumps(b, indent=2) + "\n")
    print(json.dumps(b, indent=2))
    print("\n" + table(b))


if __name__ == "__main__":
    main()
