"""
apriltag_center_mobile.py

Simplified version of apriltag_center.py for when the phone camera is
mounted ON the robot facing OUT TO THE SIDE (parallel to the wheel axle,
looking at a tag/wall to the side), rather than a stationary webcam
watching the robot from across the room.

Since the camera looks perpendicular to the direction the wheels drive,
driving forward/backward pans the camera's view sideways past the tag --
geometrically the same problem as apriltag_center.py (translate until the
tag is centered), just with the camera moving instead of the tag. No
steering, no distance/approach control -- just: is the tag centered
left-right in frame? If not, translate until it is.

Usage:
    python apriltag_center_mobile.py --stream http://<phone-ip>:8080/video
    python apriltag_center_mobile.py --stream http://<phone-ip>:8080/video --simulate
    python apriltag_center_mobile.py --camera 0   # test with a laptop webcam instead
    Press 'q' or Esc to quit.
"""

import argparse
import sys
import time

import cv2

import legoeducation as le
from lelib import doubleMotor

# ---------------------------------------------------------------------------
# Tunable settings
# ---------------------------------------------------------------------------

TAG_DICT = cv2.aruco.DICT_APRILTAG_36h11  # must match generate_apriltag.py

MAX_SPEED = 60
DEADZONE_PX = 12        # error smaller than this counts as "centered" -> stop

# speed = KP * error_px + KD * d(error_px)/dt -- see apriltag_center.py's
# README section for what KD=0 vs KD>0 does (spring-loaded vs damped).
KP = 0.35
KD = 0.05

NO_TAG_TIMEOUT = 0.5  # seconds with no tag seen before the car stops, failsafe

# Both wheels always get the same speed and direction (pure translation, no
# turning). Flip this if positive `speed` moves the tag the WRONG way
# across the frame on your hardware.
DIRECTION_SIGN = 1

# The two physical motors are usually mounted mirrored on the chassis, so
# sending the SAME "clockwise" command to both sides can drive one wheel
# forward and the other backward, spinning the car instead of translating
# it. Flip whichever side is wrong. (Same fix as in apriltag_center.py.)
INVERT_LEFT_MOTOR = False
INVERT_RIGHT_MOTOR = True

# If the phone is also physically rotated (not just facing sideways, but
# rolled 90 degrees), set this so the image comes out upright before any
# detection happens. None = no rotation needed.
#   cv2.ROTATE_90_CLOCKWISE / cv2.ROTATE_90_COUNTERCLOCKWISE / cv2.ROTATE_180
FRAME_ROTATION = cv2.ROTATE_90_COUNTERCLOCKWISE

DEFAULT_CAMERA_INDEX = 0  # used only if --stream isn't given


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
    quad = corners[0][0]
    centroid = quad.mean(axis=0)
    return centroid, quad


def draw_overlay(frame, corners, centroid, center_x, error_px, speed, tag_seen):
    h, w = frame.shape[:2]
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
        self.dm.connect()
        print("[car] Connected.")

    def drive(self, speed):
        """speed: signed, positive drives the tag rightward in the frame
        (before DIRECTION_SIGN is applied)."""
        # OpenCV's tag coordinates are numpy.float32, which propagates
        # through this math. Cast to native Python float before it reaches
        # legoeducation's speed check.
        speed = float(DIRECTION_SIGN * speed)
        speed = max(-MAX_SPEED, min(MAX_SPEED, speed))
        if self.simulate:
            print(f"[car][sim] speed={speed:+.0f}")
            return
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
    p = argparse.ArgumentParser(
        description="Center a robot-mounted, sideways-facing camera on an AprilTag by translating"
    )
    p.add_argument("--stream", default=None,
                    help="Phone camera stream URL, e.g. http://192.168.1.42:8080/video")
    p.add_argument("--camera", type=int, default=DEFAULT_CAMERA_INDEX,
                    help="Local webcam index to use instead of --stream")
    p.add_argument("--simulate", action="store_true",
                    help="Run without hardware; just print the commands that would be sent.")
    return p.parse_args()


def main():
    args = parse_args()

    source = args.stream if args.stream else args.camera
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Could not open video source: {source}")
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
                print("Failed to read a frame (stream dropped?). Retrying...")
                time.sleep(0.2)
                continue

            if FRAME_ROTATION is not None:
                frame = cv2.rotate(frame, FRAME_ROTATION)

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
                prev_error = None
                speed = 0.0
                error_px = 0.0
                if last_seen_time is None or (now - last_seen_time) > NO_TAG_TIMEOUT:
                    car.stop()

            draw_overlay(frame, corners, centroid, center_x, error_px, speed, tag_seen)
            cv2.imshow("AprilTag Centering (mobile camera)", frame)

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