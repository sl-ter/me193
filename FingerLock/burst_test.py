#!/usr/bin/env python3
"""How the safe would do on real attempts: replay the lock rules on held-out bursts.

    python FingerLock/burst_test.py --model FingerLock/check/counting_run_2026-11-11b.npz --conf 0.8 0.7 0.6

Takes the last 20% of each label's photos in one of the owner's sessions (the
same photos `train.py --holdout-tail SESSION` holds out) and reports, for a
network that never trained on them:
- per frame: how often it reads the count right, and how often it's sure
  (at or above the confidence bar) and right;
- per burst (one key press in capture.py, ~4 s of one count): feed the frames
  to the safe's own rules (lock_policy.py) at their real timing, after a short
  empty mat, and see whether a digit gets accepted, and whether it's the right one.

Test a network that never saw these photos (`train.py --save-counting-run`),
not the exported one, which trains on everything.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np

import common  # noqa: F401  (puts the board's python folder on the path)
from common import DATA_DIR, MODEL_PATH, OWNER
import fingernet as FN
import lock_policy as LP

LABS = ["none", "0", "1", "2", "3", "4", "5"]
BURST_GAP_S = 0.25          # frames further apart than this start a new burst
MIN_BURST = 8               # skip the scrap of a burst left at the 80% cut


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", type=Path, default=MODEL_PATH)
    ap.add_argument("--person", default=OWNER)
    ap.add_argument("--session", default="safe1")
    ap.add_argument("--conf", type=float, nargs="+", default=[LP.CONF], help="confidence bars to try")
    args = ap.parse_args()

    net = FN.FingerNet(args.model)
    root = DATA_DIR / args.person / args.session
    res = {}
    for li, lab in enumerate(LABS):
        files = sorted((root / lab).glob("*.png"), key=lambda p: int(p.stem))
        rows = []
        for p in files[int(len(files) * 0.8):]:
            probs, _, _ = net.forward(FN.net_input(cv2.imread(str(p), 0)))
            rows.append((int(p.stem) / 1000.0, probs))
        res[li] = rows
    frames = [(li, pr) for li, rows in res.items() for _, pr in rows]
    if not frames:
        raise SystemExit(f"No photos in {root}")
    print(f"{args.model.name} on the last 20% of {args.person}/{args.session}: {len(frames)} frames, "
          f"{np.mean([np.argmax(pr) == li for li, pr in frames]):.1%} read right")
    print("  per label:", {LABS[li]: f"{np.mean([np.argmax(pr) == li for _, pr in rows]):.0%}"
                           for li, rows in res.items() if rows})

    for conf in args.conf:
        sure = [(li, pr) for li, pr in frames if pr.max() >= conf]
        print(f"\nBar {conf:.0%}: sure on {len(sure) / len(frames):.0%} of frames, right on "
              f"{np.mean([np.argmax(pr) == li for li, pr in sure]):.1%} of those")
        tally, per = {"right": 0, "wrong": 0, "nothing": 0}, {}
        for li, rows in res.items():
            if li == 0:
                continue
            bursts, cur = [], []
            for t, pr in rows:
                if cur and t - cur[-1][0] > BURST_GAP_S:
                    bursts.append(cur)
                    cur = []
                cur.append((t, pr))
            if cur:
                bursts.append(cur)
            for b in bursts:
                if len(b) < MIN_BURST:
                    continue
                p = LP.LockPolicy((1,), None, conf=conf, owner_t=0.0)
                t0 = b[0][0] - 0.6
                for k in range(6):                     # an empty mat first, so the hand-off rule is met
                    p.update(t0 + k * 0.1, [1, 0, 0, 0, 0, 0, 0], 0.0)
                got = None
                for t, pr in b:
                    for e in p.update(t, pr, 1.0):
                        if e.kind == "digit" and got is None:
                            got = e.digit
                k = "nothing" if got is None else ("right" if got == li - 1 else "wrong")
                tally[k] += 1
                per.setdefault(LABS[li], []).append(k[0])
        n = sum(tally.values())
        print(f"  bursts: {tally['right']} of {n} give the right digit, {tally['wrong']} a wrong one, "
              f"{tally['nothing']} none (r/w/n by count: {', '.join(f'{k} {''.join(v)}' for k, v in per.items())})")


if __name__ == "__main__":
    main()
