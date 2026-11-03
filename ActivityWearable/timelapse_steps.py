#!/usr/bin/env python3
"""Record the step net learning, for timelapse.html.

Trains one leave-one-person-out fold exactly as train_steps.py does (same
seed, same sessions, so the last frame ends where that person's line in
train_steps.py's output does) and snapshots it as it goes: the loss, how
many steps it counts on each of the held-out person's sessions, and its
output over 8 s of four of them (walk, stairs, fast run, air-bike).
Snapshots are dense early on, where it changes fastest. Steps are counted at
that fold's threshold from train_steps.py (figures/steps_results.json, picked
on the other people's held-out output), so run train_steps.py first.

    python ActivityWearable/timelapse_steps.py                  # holds out the person with the most taps
    python ActivityWearable/timelapse_steps.py --person BANJO

Writes figures/steps_timelapse.json (~2 MB). Takes about 5 minutes.
"""
import argparse
import json
import sys

import numpy as np
import torch
import torch.nn.functional as TF

import train_steps as T
from train_steps import S

WINDOW_S = 8.0
DOWNSAMPLE = 2           # keep every 2nd output sample in the windows (a bump is ~8 samples wide)
SHOW = ("walk_normal", "stairs", "run_fast", "bike_fast")


def frame_iterations(total):
    """Every 2nd iteration to 40, every 5th to 200, then every 10th."""
    its = set(range(0, 41, 2)) | set(range(40, 201, 5)) | set(range(200, total + 1, 10)) | {total}
    return {i for i in its if i <= total}


def probs(net, X):
    """The net's output for input rows NET_REACH onward (sample CTX + NET_REACH onward)."""
    with torch.no_grad():
        return torch.sigmoid(net(torch.from_numpy(X.T[None].astype(np.float32)))[0, 0]).numpy()


def pick_windows(test):
    out = []
    for activity in SHOW:
        cands = sorted([s for s in test if s["activity"] == activity], key=lambda s: -len(s["X"]))
        if not cands:
            continue
        s = cands[0]
        first, last = (T.NET_REACH + S.CTX) / S.RATE_HZ, (len(s["shin"]) - T.NET_REACH - S.CTX) / S.RATE_HZ - WINDOW_S
        a0 = s["taps"][0] / S.RATE_HZ + 2.0 if len(s["taps"]) else 5.0
        a0 = round(float(np.clip(a0, first, last)), 2)
        if last <= first:
            continue
        out.append((s, a0))
    return out


def window_static(s, a0):
    i0, n = int(a0 * S.RATE_HZ), int(WINDOW_S * S.RATE_HZ)
    inwin = lambda xs: [round(x / S.RATE_HZ - a0, 3) for x in xs if i0 <= x < i0 + n]
    swing = None
    if s["has_phone"]:
        sw = s["X"][i0 - S.CTX:i0 - S.CTX + n:DOWNSAMPLE, 10] * S.GYRO_SCALE
        swing = [round(float(v), 1) for v in sw]
    return {"session": s["name"], "activity": s["activity"], "label": s["label"], "t0": a0,
            "dt": DOWNSAMPLE / S.RATE_HZ,
            "gx": [round(float(v), 1) for v in s["shin"][i0:i0 + n:DOWNSAMPLE, 3]], "swing": swing,
            "taps": inwin(s["taps"]), "strides": inwin(T.old_rule(s["shin"]))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--person", help="who to hold out (default: the person with the most taps)")
    ap.add_argument("--data", type=T.Path, default=T.DATA_DIR)
    ap.add_argument("--out", type=T.Path, default=T.FIG_DIR / "steps_timelapse.json")
    ap.add_argument("--epochs", type=int, default=T.EPOCHS)
    args = ap.parse_args()

    sessions = T.load(args.data)
    taps_by = {}
    for s in sessions:
        taps_by[s["person"]] = taps_by.get(s["person"], 0) + len(s["taps"])
    person = args.person or max(taps_by, key=taps_by.get)
    if person not in taps_by:
        sys.exit(f"no sessions for {person}; people: {', '.join(sorted(taps_by))}")
    train_set = [s for s in sessions if s["person"] != person]
    test = [s for s in sessions if s["person"] == person]
    tapped = [s for s in test if s["taps"].size >= 10]
    windows = pick_windows(test)
    results = T.FIG_DIR / "steps_results.json"
    try:
        threshold = json.loads(results.read_text())["fold_thresholds"][person]
    except (OSError, KeyError) as e:
        sys.exit(f"no threshold for {person} in {results} ({e}): run train_steps.py first")
    print(f"holding out {person}: {len(test)} sessions, {taps_by[person]} taps; "
          f"windows: {', '.join(s['activity'] for s, _ in windows)}")

    targets = [torch.from_numpy(s["y"][T.NET_REACH:len(s["y"]) - T.NET_REACH]) for s in tapped]
    total = args.epochs * T.ITERS
    want = frame_iterations(total)
    frames, recent = [], []

    def snapshot(net, it, loss, lr):
        if loss is not None:
            recent.append(loss)
        if it not in want:
            return
        held_loss = []
        for s, y in zip(tapped, targets):
            logits = net(torch.from_numpy(s["X"].T[None].astype(np.float32)))[0, 0].detach()
            held_loss.append(float(TF.binary_cross_entropy_with_logits(logits, y, weight=1 + T.POS_WEIGHT * y)))
        counts = {"phone": [], "shin": []}
        found_in = []
        p_win = []
        for s in tapped:
            for key, k in (("phone", "X"), ("shin", "X_shin")):
                counts[key].append(len(S.pick_peaks(probs(net, s[k]), threshold, T.MIN_GAP)))
        for s, a0 in windows:
            p = probs(net, s["X"])
            off = T.NET_REACH + S.CTX                           # p[0] is this sample
            i0, n = int(a0 * S.RATE_HZ), int(WINDOW_S * S.RATE_HZ)
            p_win.append([round(float(v), 3) for v in p[i0 - off:i0 - off + n:DOWNSAMPLE]])
            at = np.array(S.pick_peaks(p, threshold, T.MIN_GAP), dtype=int) + off
            found_in.append([round(c / S.RATE_HZ - a0, 3) for c in at if i0 <= c < i0 + n])
        frames.append({"it": it, "epoch": round(it / T.ITERS, 2), "lr": lr,
                       "loss_train": round(float(np.mean(recent)), 4) if recent else None,
                       "loss_held": round(float(np.mean(held_loss)), 4), "threshold": threshold,
                       "phone": counts["phone"], "shin": counts["shin"], "p": p_win, "found": found_in})
        recent.clear()
        if it % 250 == 0:
            print(f"  iteration {it}/{total}: held-out loss {frames[-1]['loss_held']:.3f}, "
                  f"{sum(counts['phone'])} steps vs {sum(len(s['taps_seen']) for s in tapped)} taps", flush=True)

    T.train(train_set, epochs=args.epochs, snapshot=snapshot)

    out = {
        "person": person, "trained_on": sorted({s["person"] for s in train_set}),
        "iterations": total, "iters_per_epoch": T.ITERS, "batch": T.BATCH, "lr": T.LR,
        "sessions": [{"session": s["name"], "activity": s["activity"], "label": s["label"],
                      "taps": int(len(s["taps_seen"])),
                      "old_rule": 2 * int(T.seen(T.old_rule(s["shin"]), len(s["shin"])).sum()),
                      "seconds": round(len(s["shin"]) / S.RATE_HZ, 1)} for s in tapped],
        "windows": [window_static(s, a0) for s, a0 in windows],
        "frames": frames,
    }
    args.out.write_text(json.dumps(out, separators=(",", ":")))
    last = frames[-1]
    print(f"{len(frames)} frames; at the end: {sum(last['phone'])} steps (shin only {sum(last['shin'])}) vs "
          f"{sum(o['taps'] for o in out['sessions'])} taps, threshold {last['threshold']:.2f}")
    print(f"wrote {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
