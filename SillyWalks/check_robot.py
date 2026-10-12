"""
Check the robot before training: is yaw reading the right axis, in degrees,
with the right sign, and do the motor commands do what the action names say?

    python check_robot.py            # part 1 only: watch the IMU while you turn the robot by hand
    python check_robot.py --drive    # part 1, then part 2: short crawls (straight, A0, A4)

Whatever this finds goes into the settings at the top of crawler.py.
"""

import argparse
import time

import legoeducation as le

from crawler import RealCrawler, speeds_for
from qlearn import STEP_TIME

FACES = {"top": le.DEVICE_FACE_TOP, "bottom": le.DEVICE_FACE_BOTTOM,
         "front": le.DEVICE_FACE_FRONT, "back": le.DEVICE_FACE_BACK,
         "left": le.DEVICE_FACE_LEFT, "right": le.DEVICE_FACE_RIGHT}


def watch_imu(robot, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        imu = robot.dm.imu_device
        print(f"\r  yaw {robot.yaw():+7.1f}   (raw yaw {imu.yaw:+6}  pitch {imu.pitch:+6}  "
              f"roll {imu.roll:+6})   ", end="", flush=True)
        time.sleep(0.1)
    print()


def crawl(robot, diff, seconds):
    robot.reset_heading()
    left, right = speeds_for(diff)
    print(f"  crawling: diff {diff:+d} -> left {left}%, right {right}% for {seconds}s")
    robot.drive(diff)
    time.sleep(seconds)
    robot.stop()
    time.sleep(0.3)
    return robot.yaw()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", action="store_true", help="also run the motor tests")
    ap.add_argument("--face", choices=FACES, help="try a different yaw face than crawler.YAW_FACE")
    ap.add_argument("--seconds", type=float, default=2.0, help="length of each test crawl")
    args = ap.parse_args()

    robot = RealCrawler()
    try:
        if args.face:
            robot.dm.imu_set_yaw_face(FACES[args.face])
            print(f"Yaw face set to {args.face} (put it in crawler.YAW_FACE if it's the right one)")

        print("\nPART 1 -- sensor. Robot flat on the floor. Yaw is zeroed now.")
        print("Over the next 10 s, slowly turn it about 90 deg CLOCKWISE (seen from above), then back.")
        robot.reset_heading()
        watch_imu(robot, 10)
        print("Expect: yaw went to about +90.")
        print("  - went to about -90       -> set YAW_SIGN = -1")
        print("  - went to about +/-900    -> set YAW_SCALE = 0.1")
        print("  - barely moved, but pitch/roll did -> the motor is on its side; rerun with")
        print("    --face top/front/... until yaw follows, and set YAW_FACE to match")

        if not args.drive:
            return

        input("\nPART 2 -- motors. Put it on the floor with room ahead, Enter to crawl straight: ")
        y = crawl(robot, 0, args.seconds)
        print(f"  yaw change {y:+.1f} deg")
        print("  - did it move BACKWARD? -> set FORWARD = -1")
        print(f"  - this yaw change is the robot's natural drift over {args.seconds}s; "
              "it's what the training has to learn to cancel")

        input("\nEnter to try A0 (-40, should turn RIGHT / yaw goes +): ")
        y0 = crawl(robot, -40, args.seconds)
        print(f"  yaw change {y0:+.1f} deg")

        input("\nEnter to try A4 (+40, should turn LEFT / yaw goes -): ")
        y4 = crawl(robot, 40, args.seconds)
        print(f"  yaw change {y4:+.1f} deg")

        print("\nSummary:")
        if y0 > y4:
            print("  A0 turns right of A4 -- action names match the robot. Good.")
        else:
            print("  A0 turned LEFT of A4 -- set SWAP_SIDES = True in crawler.py (or check YAW_SIGN first).")
        spread = abs(y0 - y4)
        print(f"  A0 vs A4 differ by {spread:.0f} deg over {args.seconds}s "
              f"(~{spread / 2 * STEP_TIME / args.seconds:.1f} deg per {STEP_TIME}s step each way).")
        if spread < 10:
            print("  That's a small effect -- consider a bigger BASE_SPEED or larger ACTIONS in qlearn.py.")
    finally:
        robot.close()


if __name__ == "__main__":
    main()
