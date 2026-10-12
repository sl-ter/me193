#!/usr/bin/env python3
"""
Check the Double Motor paddle before playing. Three steps:

  1. Still + swing: live gyro x/y/z and magnitude, plus the notification rate.
     The resting vs. swinging magnitudes tell you whether pong.py's default
     --min-threshold (50) suits these raw units.
  2. Twist test: twist the paddle to the RIGHT (clockwise, like turning a
     doorknob) a few times. The axis that moves most is the twist axis, and
     its sign is set so right-twist = curve right. Prints the pong.py flags.
  3. --haptics: plays each pattern (rumble ticks slow -> fast, contact kick,
     sweet-spot kick, miss) so you can feel them and tune paddles.py.

  venv/bin/python check_paddle.py [--haptics] [--card-color orange --card-serial 0994]
"""

import argparse
import time

from paddles import LegoPaddle


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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--card-color", default="orange")
    p.add_argument("--card-serial", default="0994")
    p.add_argument("--haptic-motor", choices=["left", "right"], default="left")
    p.add_argument("--haptics", action="store_true", help="also play each haptic pattern")
    args = p.parse_args()

    paddle = LegoPaddle(args.card_serial, args.card_color, args.haptic_motor)
    paddle.start()
    try:
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

        input("\n[2/3] Twist test: press Enter, then twist the paddle to the RIGHT\n"
              "      (clockwise, like a doorknob) 3 times over 4 s, no big swing...")
        twist = read_for(paddle, 4, show=False)
        if twist:
            axes = []
            for i, name in enumerate("xyz"):
                vals = [g[i] for _, _, g in twist]
                biggest = max(vals, key=abs)
                axes.append((abs(biggest), name, 1 if biggest > 0 else -1))
            axes.sort(reverse=True)
            for amp, name, sign in axes:
                print(f"  axis {name}: peak {amp * sign:+.0f}")
            amp, name, sign = axes[0]
            print(f"\n  -> twist axis {name}, sign {sign:+d}. Play with:")
            print(f"     venv/bin/python pong.py --twist-axis {name} --twist-sign {sign}")
            if axes[1][0] > 0.7 * amp:
                print("  ! two axes moved about equally: twist more purely and run it again")

        if args.haptics:
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
    finally:
        paddle.stop()


if __name__ == "__main__":
    main()
