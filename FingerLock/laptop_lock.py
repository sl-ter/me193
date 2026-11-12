#!/usr/bin/env python3
"""The Infallible Safe on the laptop: the same network (fingernet.py, numpy),
the same rules (lock_policy.py) and the same codes as the board, with the
laptop's camera (or the board's USB webcam plugged into the laptop).

    python FingerLock/laptop_lock.py --camera 1            # the USB webcam
    python FingerLock/laptop_lock.py --camera 1 --mqtt     # also send status/alerts like the board does
    python FingerLock/laptop_lock.py --camera 1 --torch    # also time PyTorch on each frame

The window shows what the board can't: the camera with the crop square, what
the network sees (64 x 64), its 7 count probabilities, the owner score
against its threshold, the hold timer, and the board's LED screen as it would
look. q quits. b (or SPACE) is the board's start button: with "button": true
in settings.json the safe sleeps until it's pressed, takes one code, then
sleeps again; pressing it while open locks it at once.

For the UNO Q vs laptop comparison it logs every frame's timing (prepare ms,
network ms, frames per second, state, never the digits) to
runs/laptop_<time>.csv; bench.py summarises those files. The log also keeps
each frame's owner score and the rules' events with their owner averages
(e.g. "digit:0.412", "stranger:0.004"), for tuning the owner threshold
(settings.json). Intruder photos (stranger, lockout, duress) go to
intruders/ (gitignored).
"""
import argparse
import csv
import json
import time
from datetime import datetime

import cv2
import numpy as np

from common import (BROKER, CAMERA_INDEX, INTRUDER_DIR, MODEL_PATH, PORT, RUNS_DIR, load_codes,
                    load_settings, open_camera)
import fingernet as FN
import leds
import lock_policy as LP
import photo

W_PANEL = 330
FLASH_S = 1.5
STRANGER_PHOTO_GAP_S = 10.0
LED_CELL = 14


def led_image(arr):
    """The board's 13 x 8 LED matrix, drawn as red dots."""
    h, w = arr.shape
    img = np.zeros((h * LED_CELL, w * LED_CELL, 3), np.uint8)
    for r in range(h):
        for c in range(w):
            v = int(arr[r, c])
            colour = (40, 40, 60 + 195 * v // 7) if v else (30, 30, 30)
            cv2.circle(img, (c * LED_CELL + LED_CELL // 2, r * LED_CELL + LED_CELL // 2), LED_CELL // 2 - 2, colour, -1)
    return img


def panel(height, probs, owner, owner_t, method, status, stats, code_avg=None):
    """The right-hand panel: probabilities, owner score (this frame's, and the
    code's average so far, which is what the rules judge), hold, state, speed."""
    p = np.full((height, W_PANEL, 3), 245, np.uint8)
    y = 28
    cv2.putText(p, "count probabilities", (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 60, 60), 1)
    for k, lab in enumerate(FN.COUNT_LABELS):
        y += 26
        best = k == int(np.argmax(probs))
        cv2.putText(p, "no hand" if lab == "none" else f"{lab} fingers", (12, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (20, 20, 20), 2 if best else 1)
        cv2.rectangle(p, (110, y - 13), (110 + int(probs[k] * 165), y), (214, 120, 42) if best else (190, 190, 190), -1)
        cv2.putText(p, f"{probs[k]:.2f}", (284, y - 1), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (60, 60, 60), 1)
    y += 40
    cv2.putText(p, f"owner score ({method})", (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 60, 60), 1)
    y += 22
    ok = owner >= owner_t
    cv2.rectangle(p, (12, y - 14), (12 + int(owner * 300), y), (122, 175, 27) if ok else (52, 104, 235), -1)
    tx = 12 + int(owner_t * 300)
    cv2.line(p, (tx, y - 20), (tx, y + 4), (0, 0, 0), 2)
    cv2.putText(p, f"{owner:.2f} this frame (threshold {owner_t:.2f})", (12, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (60, 60, 60), 1)
    code_text = ("judged on the code's average" if code_avg is None
                 else f"this code's average so far: {code_avg:.2f}")
    cv2.putText(p, code_text, (12, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (20, 20, 20) if code_avg is None or code_avg >= owner_t else (52, 104, 235), 1)
    y += 74
    state = "ASLEEP" if status["state"] == "idle" else status["state"].upper()
    if status["state"] == "locked" and status["entered"]:
        state = f"ENTERING {status['entered']}/{status['code_len']}"
    if status["state"] in ("open", "lockout"):
        state += f"  {status['left_s']:.0f} s"
    cv2.putText(p, state, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    y += 26
    hint = ("press b (the button) to start" if status["state"] == "idle"
            else "b locks it now" if status["state"] == "open"
            else "take your hand off the mat" if status["need_clear"]
            else f"hold {status['hold'] * LP.HOLD_S:.1f} / {LP.HOLD_S} s")
    cv2.putText(p, hint, (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 60), 1)
    cv2.rectangle(p, (12, y + 8), (12 + int(status["hold"] * 300), y + 16), (214, 120, 42), -1)
    y += 44
    cv2.putText(p, f"{stats['fps']:.1f} frames/s   prepare {stats['prep_ms']:.1f} ms   net {stats['net_ms']:.1f} ms",
                (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (60, 60, 60), 1)
    if "torch_ms" in stats:
        cv2.putText(p, f"PyTorch net {stats['torch_ms']:.1f} ms", (12, y + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (60, 60, 60), 1)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camera", type=int, default=CAMERA_INDEX)
    ap.add_argument("--mqtt", action="store_true", help="publish status and alerts like the board (platform 'laptop')")
    ap.add_argument("--demo", action="store_true", help="with --mqtt, also publish live readings (.../live)")
    ap.add_argument("--torch", action="store_true", help="also run the PyTorch network each frame, for timing")
    ap.add_argument("--crop", type=float, default=FN.CROP_FRAC)
    args = ap.parse_args()

    code, duress, topic = load_codes()
    net = FN.FingerNet(MODEL_PATH)
    meta = net.meta
    settings = load_settings()
    policy = LP.make_policy(code, duress, meta, settings)
    owner_t = policy.owner_t
    source = "settings.json" if settings.get("owner_threshold") is not None else "trained"
    print(f"Network from {meta.get('trained', '?')}: owner check '{net.owner_method}', threshold {owner_t} "
          f"({source}), judged on each code's average")

    torch_net = None
    if args.torch:
        import torch
        import train
        torch_net = train.Net().eval()
        sd = {f"{n}.{'weight' if k == 'w' else 'bias'}": torch.from_numpy(net.w[f"{n}_{k}"])
              for n in ("conv1", "conv2", "conv3", "fc", "count", "owner") for k in ("w", "b")}
        torch_net.load_state_dict(sd)

    client = None
    if args.mqtt:
        import paho.mqtt.client as mqtt
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"safe-laptop-{int(time.time())}")
        client.connect_async(BROKER, PORT, keepalive=15)
        client.loop_start()
        print(f"MQTT on {topic}")

    def publish(sub, payload, qos=0):
        if client is not None:
            client.publish(f"{topic}/{sub}", json.dumps(payload), qos=qos)

    RUNS_DIR.mkdir(exist_ok=True)
    log_path = RUNS_DIR / f"laptop_{datetime.now():%Y%m%d-%H%M%S}.csv"
    log_file = open(log_path, "w", newline="")
    log = csv.writer(log_file)
    log.writerow(["t", "prep_ms", "net_ms", "torch_ms", "fps", "state", "entered", "owner_p", "events"])

    cap = open_camera(args.camera)
    stats = {"fps": 0.0, "prep_ms": 0.0, "net_ms": 0.0}
    flash_kind, flash_until, last_stranger, last_status, t_prev = None, 0.0, 0.0, 0.0, None
    pressed = False
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            now = time.time()
            t0 = time.perf_counter()
            x = FN.prepare(frame, args.crop)
            t1 = time.perf_counter()
            probs, owner, _ = net.forward(x)
            t2 = time.perf_counter()
            prep_ms, net_ms = (t1 - t0) * 1000, (t2 - t1) * 1000
            torch_ms = ""
            if torch_net is not None:
                import torch
                with torch.no_grad():
                    t3 = time.perf_counter()
                    torch_net(torch.from_numpy(x[None]))
                    torch_ms = (time.perf_counter() - t3) * 1000
                stats["torch_ms"] = 0.9 * stats.get("torch_ms", torch_ms) + 0.1 * torch_ms
            if t_prev is not None:
                stats["fps"] = 0.9 * stats["fps"] + 0.1 / max(now - t_prev, 1e-3) if stats["fps"] else 1 / max(now - t_prev, 1e-3)
            t_prev = now
            stats["prep_ms"] = 0.9 * stats["prep_ms"] + 0.1 * prep_ms if stats["prep_ms"] else prep_ms
            stats["net_ms"] = 0.9 * stats["net_ms"] + 0.1 * net_ms if stats["net_ms"] else net_ms

            events_here = []
            events = policy.press(now) if pressed else []
            pressed = False
            for e in events + policy.update(now, probs, owner):
                note = {k: v for k, v in e.detail.items() if k in ("fails", "owner_avg", "n")}
                print(f"{datetime.now():%H:%M:%S} {e.kind}", note)          # never the digit itself
                events_here.append(e.kind + (f":{e.detail['owner_avg']}" if "owner_avg" in e.detail else ""))
                if e.kind in ("wrong", "stranger"):
                    flash_kind, flash_until = e.kind, now + FLASH_S
                kind = ("stranger" if e.kind == "stranger" else "lockout" if e.kind == "lockout"
                        else "duress" if e.kind == "open" and e.duress else None)
                if kind and not (kind == "stranger" and now - last_stranger < STRANGER_PHOTO_GAP_S):
                    last_stranger = now if kind == "stranger" else last_stranger
                    thumb = photo.thumbnail(frame)
                    INTRUDER_DIR.mkdir(exist_ok=True)
                    (INTRUDER_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{kind}.png").write_bytes(photo.png_bytes(thumb))
                    publish("alert", {"board": "laptop", "kind": kind, "time": datetime.now().isoformat(timespec="seconds"),
                                      "detail": note, "png": photo.png_base64(thumb)}, qos=1)

            status = policy.status(now)
            log.writerow([round(now, 3), round(prep_ms, 3), round(net_ms, 3),
                          round(torch_ms, 3) if torch_ms != "" else "", round(stats["fps"], 2),
                          status["state"], status["entered"], round(float(owner), 4), ";".join(events_here)])
            if now - last_status >= 0.5:
                public = {k: v for k, v in status.items() if args.demo or k not in ("reading", "conf", "owner_p", "hold")}
                publish("status", {"board": "laptop", "platform": "laptop", **public,
                                   **{k: round(v, 2) for k, v in stats.items()}})
                if args.demo:
                    publish("live", {"board": "laptop", "probs": [round(float(p), 3) for p in probs],
                                     "owner_p": round(owner, 3)})
                last_status = now

            # The window
            shown = frame.copy()
            h, w = shown.shape[:2]
            side = int(round(min(h, w) * args.crop))
            top, left = (h - side) // 2, (w - side) // 2
            cv2.rectangle(shown, (left, top), (left + side, top + side), (0, 255, 255), 2)
            view = np.clip((x[0] * 0.25 + 0.5) * 255, 0, 255).astype(np.uint8)     # standardised -> visible
            view = cv2.cvtColor(cv2.resize(view, (160, 160), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
            shown[8:168, 8:168] = view
            led = led_image(leds.render(status, flash_kind if now < flash_until else None))
            shown[h - led.shape[0] - 8:h - 8, w - led.shape[1] - 8:w - 8] = led
            code_avg = sum(policy.digit_owner) / len(policy.digit_owner) if policy.digit_owner else None
            side_panel = panel(h, probs, owner, owner_t, net.owner_method, status, stats, code_avg)
            cv2.imshow("Infallible Safe - laptop (q quits)", np.hstack([shown, side_panel]))
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            pressed = pressed or key in (ord("b"), ord(" "))     # the board's start button
    finally:
        cap.release()
        cv2.destroyAllWindows()
        log_file.close()
        if client is not None:
            client.loop_stop()
        print(f"Timing log: {log_path}")


if __name__ == "__main__":
    main()
