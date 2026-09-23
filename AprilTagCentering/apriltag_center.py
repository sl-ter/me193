"""
apriltag_center.py

Task: an AprilTag is taped to a tower on the LEGO car. The car drives back
and forth on a line parallel to your laptop screen/webcam. This script
watches the webcam, finds the tag, and drives the car so it always settles
in the horizontal center of the camera's view.

Usage:
    python apriltag_center.py                # drive the real Double Motor
    python apriltag_center.py --simulate      # no hardware needed, just
                                               # prints what it would send
    python apriltag_center.py --camera 1
    Press 'q' or Esc in the video window to quit.

See the README for the write-up on how the controller works, what happens
when the tag is lost, and how to get the "spring-loaded" overshoot.
"""

import argparse
import sys
import time

import cv2
import numpy as np

import legoeducation as le
from lelib import doubleMotor

# ---------------------------------------------------------------------------
# Tunable settings
# ---------------------------------------------------------------------------

TAG_DICT = cv2.aruco.DICT_APRILTAG_36h11  # must match generate_apriltag.py

MAX_SPEED = 60          # LEGO motor speed cap, 0-100
DEADZONE_PX = 12        # error smaller than this (in pixels) counts as "centered" -> stop

# Controller gains. speed = KP * error_px + KD * d(error_px)/dt
#   KP alone (KD = 0) -> a "bouncier", more spring-like response: the car
#       drives at full tilt toward center, and because of camera/BLE
#       latency + the car's own momentum it overshoots, then corrects back
#       the other way, oscillating a bit before settling. This is the
#       "spring-loaded" behavior the assignment asks about.
#   Adding KD damps that motion (D reacts to how fast the error is already
#       shrinking, and eases off the speed as it approaches zero) -> a
#       smoother, non-overshooting approach. Raise KD to calm the bounce
#       down; set KD = 0 to get the spring effect back.
KP = 0.9
KD = 0.15

# If the tag isn't seen for longer than this, stop the motors -- see the
# README's answer to "what does your code do if no tag is detected?"
NO_TAG_TIMEOUT = 0.5  # seconds

# The car moves along a line, so both wheels should always get the same
# speed and effective direction (pure translation, no turning). Flip this
# if positive `speed` ends up moving the tag the WRONG way across the frame
# on your hardware.
DIRECTION_SIGN = -1

# The two physical motors are usually mounted mirrored on the chassis, so
# sending the SAME "clockwise" command to both sides actually drives one
# wheel forward and the other backward -- the car spins in place instead of
# translating. Flip whichever side is spinning the wrong way. (Same fix as
# INVERT_RIGHT_MOTOR in arm_race.py.)
INVERT_LEFT_MOTOR = False
INVERT_RIGHT_MOTOR = True

DEFAULT_CAMERA_INDEX = 0


# ---------------------------------------------------------------------------
# AprilTag detection
# ---------------------------------------------------------------------------

def make_detector():
    if not hasattr(cv2, "aruco"):
        print(
            "cv2.aruco is not available in this OpenCV build.\n"
            "Try: pip install opencv-contrib-python"
        )
        sys.exit(1)
    dictionary = cv2.aruco.getPredefinedDictionary(TAG_DICT)
    params = cv2.aruco.DetectorParameters()
    return cv2.aruco.ArucoDetector(dictionary, params)


def find_tag(detector, frame_bgr):
    """Return (centroid_xy, corners) for the first detected tag, or (None, None)."""
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None or len(corners) == 0:
        return None, None
    quad = corners[0][0]  # (4, 2) array of corner points for the first tag seen
    centroid = quad.mean(axis=0)
    return centroid, quad


def draw_overlay(frame, corners, centroid, center_x, error_px, speed, tag_seen):
    h, w = frame.shape[:2]

    # Target centerline.
    cv2.line(frame, (center_x, 0), (center_x, h), (0, 255, 255), 1)

    if tag_seen:
        pts = corners.astype(int)
        cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=3)
        cx, cy = int(centroid[0]), int(centroid[1])
        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
        cv2.putText(frame, f"({cx}, {cy})", (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        status = f"error: {error_px:+.0f}px   speed: {speed:+.0f}"
    else:
        status = "No tag detected -- motors stopped"

    cv2.rectangle(frame, (0, 0), (w, 34), (30, 30, 30), -1)
    cv2.putText(frame, status, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255, 255, 255) if tag_seen else (0, 0, 255), 2)


# ---------------------------------------------------------------------------
# Car control
# ---------------------------------------------------------------------------

class Car:
    def __init__(self, simulate=False):
        self.simulate = simulate
        self.dm = None

    def connect(self):
        if self.simulate:
            print("[car] SIMULATE mode: not connecting to real hardware.")
            return
        self.dm = doubleMotor()
        print("[car] Scanning for the Double Motor hub...")
        self.dm.connect()  # no card filter -> first advertising Double Motor
        print("[car] Connected.")

    def drive(self, speed):
        """speed: signed, positive drives the tag rightward in the frame
        (before DIRECTION_SIGN is applied)."""
        # OpenCV's corner/centroid coordinates are numpy.float32, and that
        # "numpy-ness" propagates through all the arithmetic above (error,
        # KP*error, etc.), even though the result still looks like a normal
        # number when printed. legoeducation's speed check wants a genuine
        # Python int/float, so cast explicitly here, at the last moment
        # before it's sent to the hub.
        speed = float(DIRECTION_SIGN * speed)
        speed = max(-MAX_SPEED, min(MAX_SPEED, speed))
        if self.simulate:
            print(f"[car][sim] speed={speed:+.0f}")
            return
        # Drive each side independently (not MOTOR_BOTH) so the per-side
        # invert flags above can correct for mirrored motors -- otherwise
        # both wheels get the same raw direction and the car spins in place.
        self._drive_side(le.MOTOR_LEFT, -speed if INVERT_LEFT_MOTOR else speed)
        self._drive_side(le.MOTOR_RIGHT, -speed if INVERT_RIGHT_MOTOR else speed)

    def _drive_side(self, motor_side, speed):
        if abs(speed) < 1:
            self.dm.motor_stop(motor=motor_side)
        else:
            direction = (le.MOTOR_MOVE_DIRECTION_CLOCKWISE if speed > 0
                         else le.MOTOR_MOVE_DIRECTION_COUNTERCLOCKWISE)
            self.dm.motor_run(direction=direction, motor=motor_side,
                               speed=float(abs(speed)), blocking=False)

    def stop(self):
        self.drive(0)

    def disconnect(self):
        if self.simulate or self.dm is None:
            return
        try:
            self.dm.motor_stop(motor=le.MOTOR_BOTH)
            self.dm.disconnect()
        except Exception as exc:
            print(f"[car] Error while disconnecting: {exc}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Center a LEGO car under an AprilTag on a webcam")
    p.add_argument("--simulate", action="store_true",
                    help="Run without hardware; just print the commands that would be sent.")
    p.add_argument("--camera", type=int, default=DEFAULT_CAMERA_INDEX,
                    help=f"Webcam device index (default: {DEFAULT_CAMERA_INDEX})")
    return p.parse_args()


def main():
    args = parse_args()

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"Could not open camera index {args.camera}.")
        sys.exit(1)

    detector = make_detector()
    car = Car(simulate=args.simulate)
    try:
        car.connect()
    except Exception as exc:
        print(f"[car] {exc}")
        print("[car] Continuing in SIMULATE mode so you can still test detection.")
        car = Car(simulate=True)

    print("Press 'q' or Esc in the video window to quit.")

    prev_error = None
    prev_time = time.monotonic()
    last_seen_time = None

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to read from camera.")
                break

            h, w = frame.shape[:2]
            center_x = w // 2
            now = time.monotonic()
            dt = max(now - prev_time, 1e-3)
            prev_time = now

            centroid, corners = find_tag(detector, frame)
            tag_seen = centroid is not None

            if tag_seen:
                last_seen_time = now
                error_px = centroid[0] - center_x
                d_error = 0.0 if prev_error is None else (error_px - prev_error) / dt
                prev_error = error_px

                if abs(error_px) < DEADZONE_PX:
                    speed = 0.0
                else:
                    speed = KP * error_px + KD * d_error

                car.drive(speed)
            else:
                prev_error = None  # don't let the derivative spike when the tag reappears
                speed = 0.0
                error_px = 0.0
                # Grace period: keep the last command briefly (e.g. the tag
                # blinked out for one frame), then fail safe and stop.
                if last_seen_time is None or (now - last_seen_time) > NO_TAG_TIMEOUT:
                    car.stop()

            draw_overlay(frame, corners, centroid, center_x, error_px, speed, tag_seen)
            cv2.imshow("AprilTag Centering", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
    finally:
        car.stop()
        car.disconnect()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()