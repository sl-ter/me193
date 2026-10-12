#!/usr/bin/env python3
"""
Check the Double Motor paddle before playing. Three steps:

  1. Still + swing: live gyro x/y/z and magnitude, plus the notification rate.
     The resting vs. swinging magnitudes tell you whether pong.py's default
     --min-threshold (50) suits these raw units.
  2. Twist (roll) test: with the paddle's nose pointed at the screen, roll it
     RIGHT (clockwise as you see it, right wing down) and back, a few times.
     Roll, not yaw: the swing itself is mostly yaw, so spin has to be a
     different rotation or every swing would count as spin. Finds the roll
     axis (any direction, see swing.find_twist_axis), signed so a right roll
     curves the ball right.
  3. Haptics: plays each pattern (rumble ticks slow -> fast, contact kick,
     sweet-spot kick, miss) so you can feel them and tune paddles.py.

Steps 1-2 are saved to paddle_calib.json, which pong.py loads automatically.

  venv/bin/python check_paddle.py                  # all three steps
  venv/bin/python check_paddle.py --haptics-only   # just step 3
  venv/bin/python check_paddle.py --skip-haptics   # just steps 1-2
"""

import argparse
import json
import os
import time

from paddles import LegoPaddle
from swing import find_twist_axis

CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paddle_calib.json")


def read_for(paddle, seconds, show=True):
    """Collect samples for `seconds`, printing a live line ~10x per second."""
    out = []
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        time.sleep(0.1)
        samples = paddle.poll()
        out += samples
        if show and samples:
            _, mag, (gx, gy, gz) = samples[-1]
            print(f"  {paddle.sample_rate:5.1f} Hz  gyro x {gx:7.0f} y {gy:7.0f} z {gz:7.0f}  |w| {mag:7.1f}")
    return out



def calibrate(paddle):
    """Steps 1-2: swing and roll, saved to paddle_calib.json."""
    input("\n[1/3] Hold the paddle still, press Enter, keep it still for 3 s...")
    rest = read_for(paddle, 3)
    input("      Now press Enter and take 3-4 normal swings over 5 s...")
    swing = read_for(paddle, 5)
    rest_peak = max(m for _, m, _ in rest) if rest else 0
    swing_peak = max(m for _, m, _ in swing) if swing else 0
    print(f"\n  IMU rate {paddle.sample_rate:.0f} Hz (asked for 50)")
    print(f"  |w| resting peak {rest_peak:.0f}, swinging peak {swing_peak:.0f}")
    if swing_peak < 3 * max(rest_peak, 1):
        print("  ! swings barely stand out from rest: check the IMU is streaming")
    elif swing_peak < 2 * 50:
        print("  ! swings are small in these units: try pong.py --min-threshold "
              f"{max(rest_peak * 2, swing_peak / 4):.0f}")

    calib = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "imu_rate_hz": round(paddle.sample_rate, 1),
        "rest_peak": round(rest_peak, 1),
        "swing_peak": round(swing_peak, 1),
    }

    input("\n[2/3] Roll test: nose of the paddle pointed at the screen, press Enter,\n"
          "      then ROLL RIGHT (clockwise as you see it, right wing down) and back,\n"
          "      3 times over 4 s. Wrist only, arm still, no yaw. The first move must\n"
          "      be the roll to the right...")
    twist = read_for(paddle, 4, show=False)
    try:
        axis, purity = find_twist_axis([g for _, _, g in twist])
    except ValueError as e:
        print(f"  ! twist test failed ({e}): run it again and twist harder")
    else:
        print(f"  roll axis (x, y, z) = ({axis[0]:+.2f}, {axis[1]:+.2f}, {axis[2]:+.2f}), "
              f"purity {purity:.0%}")
        if purity < 0.75:
            print("  ! the roll was mixed with other motion: keep the arm still, "
                  "roll only the wrist, and run it again (--skip-haptics)")
        calib["twist_axis"] = [round(v, 4) for v in axis]
        calib["twist_purity"] = round(purity, 3)

    with open(CALIB_PATH, "w") as f:
        json.dump(calib, f, indent=2)
    print(f"\n  Saved {os.path.basename(CALIB_PATH)}; pong.py will use it automatically.")


def haptics_demo(paddle):
    """Step 3: play each haptic pattern."""
    print("\n[3/3] Haptics")
    print("  approach rumble (slow -> fast):")
    for gap in [0.40, 0.30, 0.22, 0.15, 0.10, 0.09, 0.09]:
        paddle.haptic("tick")
        time.sleep(gap)
    time.sleep(0.5)
    for kind in ["hit", "sweet", "miss", "start"]:
        print(f"  {kind}")
        paddle.haptic(kind)
        time.sleep(2.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--card-color", default="orange")
    p.add_argument("--card-serial", default="0994")
    p.add_argument("--haptic-motor", choices=["left", "right"], default="left")
    p.add_argument("--skip-haptics", action="store_true", help="steps 1-2 only")
    p.add_argument("--haptics-only", action="store_true", help="step 3 only")
    args = p.parse_args()

    paddle = LegoPaddle(args.card_serial, args.card_color, args.haptic_motor)
    paddle.start()
    try:
        if not args.haptics_only:
            calibrate(paddle)
        if args.skip_haptics:
            print("\n[3/3] Haptics skipped.")
        else:
            haptics_demo(paddle)
    finally:
        paddle.stop()


if __name__ == "__main__":
    main()
