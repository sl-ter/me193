#!/usr/bin/env python3
"""Take labelled photos of hands over the mat, for training the safe's network.

    python FingerLock/capture.py --list                                  # which camera is which (names)
    python FingerLock/capture.py --aim --camera 1                        # live view for building the camera rig
    python FingerLock/capture.py --person SAM --session lamp1 --camera 1

Keys:   0-5  that many fingers, n  no hand (empty mat): saves a 4 s burst of that
             label (10 photos a second) and stops by itself. Pose first, then press.
        SPACE  start / stop saving with no time limit      q  quit

Each photo is the square crop of the mat, grey, 128 x 128 (exactly what the
board will feed the network, see fingernet.crop_for_saving), saved to
data/<PERSON>/<session>/<label>/<time>.png. data/ is gitignored: hand photos
never go to GitHub.

Use the same webcam, mat and lamp you'll use on the board. After any key,
saving waits 0.3 s, so the moment of pressing isn't saved. Move the hand
around (position, angle) during each burst; change the pose only between bursts.

What to capture (the network only learns what it has seen):
- Every class: no hand, a fist (0), and 1-5 fingers. Fingers clearly apart.
- Your hand everywhere on the mat, turned different ways, nearer and farther,
  both hands, palm up and palm down, different sleeves (or none).
- Two lighting setups, as two sessions (e.g. lamp1 and lamp2). One of your
  sessions is held out to test the network on conditions it hasn't trained on.
- Friends: the same routine, shorter (~40 photos per class). They're what
  teaches the network what "not the owner" looks like.
"""
import argparse
import time

import cv2
import numpy as np

from common import CAMERA_INDEX, CHECK_DIR, DATA_DIR, OWNER, list_cameras, open_camera
import fingernet as FN

LABEL_KEYS = {ord(str(d)): str(d) for d in range(6)}
LABEL_KEYS[ord("n")] = "none"
SETTLE_S = 0.3
VIEW = 192                      # the net's 64 x 64 view, drawn 3x


def list_mode(show):
    """Print each camera's index and name (from macOS). With --show, also open
    each one and show a snapshot."""
    cams = list_cameras()
    for idx, name in cams:
        note = "   <- your iPhone (Continuity Camera), not the webcam" if "iPhone" in name else ""
        print(f"  --camera {idx}: {name}{note}")
    if not cams:
        print("  (camera names unavailable: use --list --show to see a snapshot from each)")
    if not any("iPhone" not in n and "MacBook" not in n and "FaceTime" not in n for _, n in cams):
        print("  No USB webcam found. Is it plugged into this Mac (not the board)?")
    if not show:
        return
    names = dict(cams)
    tiles = []
    for idx in range(5):
        try:
            cap = open_camera(idx, quiet=True)
        except RuntimeError:
            continue
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            continue
        print(f"  --camera {idx}: {frame.shape[1]}x{frame.shape[0]}  {names.get(idx, '')}")
        tile = cv2.resize(frame, (320, 240))
        cv2.putText(tile, f"--camera {idx}", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        tiles.append(tile)
    if not tiles:
        print("No camera delivered frames.")
        return
    cv2.imshow("cameras (any key to close)", np.hstack(tiles))
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def crop_box(shape, frac):
    h, w = shape[:2]
    side = int(round(min(h, w) * frac))
    top, left = (h - side) // 2, (w - side) // 2
    return left, top, side


def aim_mode(args):
    """Live view for building the camera rig. Nothing is saved unless you press s.
    Only the yellow square is used (--dim below 1 darkens everything outside it).
    Fill the green square (2/3 of the yellow one) with your hand, fingers spread."""
    cap = open_camera(args.camera)
    name = dict(list_cameras()).get(args.camera, "")
    t_prev, fps = None, 0.0
    print("Aim mode: only the yellow square matters. s saves a snapshot, q quits.")
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        now = time.time()
        if t_prev is not None and now > t_prev:
            fps = 0.9 * fps + 0.1 / (now - t_prev) if fps else 1 / (now - t_prev)
        t_prev = now
        h, w = frame.shape[:2]
        left, top, side = crop_box(frame.shape, args.crop)
        shown = frame.copy()
        if args.dim < 1:
            shown = (frame * args.dim).astype(np.uint8)
            shown[top:top + side, left:left + side] = frame[top:top + side, left:left + side]
        cv2.rectangle(shown, (left, top), (left + side, top + side), (0, 255, 255), 2)
        g = int(side * 2 / 3)
        gl, gt = left + (side - g) // 2, top + (side - g) // 2
        cv2.rectangle(shown, (gl, gt), (gl + g, gt + g), (0, 200, 0), 1)
        view = np.clip(FN.shrink(FN.crop_for_saving(frame, args.crop), FN.NET_SIZE), 0, 255).astype(np.uint8)
        view = cv2.cvtColor(cv2.resize(view, (VIEW, VIEW), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        shown[8:8 + VIEW, w - 8 - VIEW:w - 8] = view
        cv2.putText(shown, f"camera {args.camera} {name}  {w}x{h}  {fps:.0f} fps", (10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(shown, "only mat inside yellow; spread hand ~ fills green", (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow("aim the camera (s = snapshot, q = quit)", shown)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s"):
            CHECK_DIR.mkdir(exist_ok=True)
            path = CHECK_DIR / f"aim_{time.strftime('%Y%m%d-%H%M%S')}.png"
            cv2.imwrite(str(path), shown)
            print(f"Saved {path}")
    cap.release()
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="print each camera's index and name, and exit")
    ap.add_argument("--show", action="store_true", help="with --list: also show a snapshot from each camera")
    ap.add_argument("--aim", action="store_true", help="live view for building the camera rig (saves nothing)")
    ap.add_argument("--dim", type=float, default=1.0,
                    help="with --aim: brightness outside the yellow square, 0-1 (default 1 = no dimming)")
    ap.add_argument("--person", help=f"whose hand: {OWNER} for the owner, any other name for friends")
    ap.add_argument("--session", default="s1", help="e.g. lamp1, lamp2 (one per lighting setup)")
    ap.add_argument("--camera", type=int, default=CAMERA_INDEX)
    ap.add_argument("--rate", type=float, default=10.0, help="photos per second while saving")
    ap.add_argument("--burst", type=float, default=4.0, help="seconds a label key saves for")
    ap.add_argument("--crop", type=float, default=FN.CROP_FRAC, help="square crop size, fraction of the short side")
    args = ap.parse_args()

    if args.list:
        list_mode(args.show)
        return
    if args.aim:
        aim_mode(args)
        return
    if not args.person:
        ap.error("--person is required (e.g. --person SAM)")

    person = args.person.upper()
    root = DATA_DIR / person / args.session
    counts = {lab: len(list((root / lab).glob("*.png"))) for lab in FN.COUNT_LABELS}
    role = "the OWNER (opens the safe)" if person == OWNER else "NOT the owner (teaches 'not Sam')"
    print(f"Saving to {root}  ({role})")
    print(f"Keys: 0-5 or n = save a {args.burst:g} s burst of that label (pose first!), "
          "SPACE = start/stop with no time limit, q = quit")

    cap = open_camera(args.camera)
    label, recording, last_save, settle_until, stop_at = "none", False, 0.0, 0.0, None
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        now = time.time()
        img128 = FN.crop_for_saving(frame, args.crop)
        if recording and stop_at is not None and now >= stop_at:
            recording, stop_at = False, None                     # the burst is over
        if recording and now >= settle_until and now - last_save >= 1.0 / args.rate:
            folder = root / label
            folder.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(folder / f"{int(now * 1000)}.png"), img128)
            counts[label] += 1
            last_save = now

        # Overlay: the crop square, what the network sees, the label and the counts.
        shown = frame.copy()
        left, top, side = crop_box(frame.shape, args.crop)
        cv2.rectangle(shown, (left, top), (left + side, top + side), (0, 255, 255), 2)
        view = np.clip(FN.shrink(img128, FN.NET_SIZE), 0, 255).astype(np.uint8)
        view = cv2.cvtColor(cv2.resize(view, (VIEW, VIEW), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        shown[8:8 + VIEW, -8 - VIEW:-8] = view
        settling = recording and now < settle_until
        if settling:
            status = "get ready"
        elif recording:
            status = f"SAVING {stop_at - now:.1f} s" if stop_at is not None else "SAVING (space stops)"
        else:
            status = "paused"
        colour = (0, 0, 255) if status.startswith("SAVING") else (200, 200, 200)
        cv2.putText(shown, f"{person}/{args.session}   label: {label}   {status}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, colour, 2)
        cv2.putText(shown, "  ".join(f"{k}:{v}" for k, v in counts.items()), (10, shown.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if status.startswith("SAVING"):
            cv2.circle(shown, (shown.shape[1] - VIEW - 30, 24), 10, (0, 0, 255), -1)
        cv2.imshow("capture (q to quit)", shown)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" "):
            recording, stop_at = not recording, None
            settle_until = now + SETTLE_S
        elif key in LABEL_KEYS:
            label = LABEL_KEYS[key]
            recording, settle_until = True, now + SETTLE_S
            stop_at = settle_until + args.burst

    cap.release()
    cv2.destroyAllWindows()
    print("Saved so far:", counts)


if __name__ == "__main__":
    main()
