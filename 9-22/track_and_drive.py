"""
AprilTag centering: the car drives back and forth on a track parallel to
the screen, with an AprilTag (see generate_tag.py) taped to a tower on it.
This script watches the webcam, finds the tag, and drives the car so it
always comes to rest in the horizontal middle of the camera frame.

Install first:
    pip install opencv-contrib-python legoeducation
Then copy lelib.py into this project's folder (already done here).

Controller: at every camera frame,
    error   = frame_center_x - tag_centroid_x      (pixels)
    speed   = Kp * error - Kd * d(error)/dt
speed (clamped to +-MAX_SPEED, in percent) is the only thing commanded --
there's no separate "drive to position" call. Kp alone already gives the
"faster when far, slower when close" behavior the assignment asks for,
since speed scales with how far off-center the tag is. Kd adds damping on
top of that: see SPRING_LOADED below.
"""

import time

import cv2
import legoeducation as le

from lelib import doubleMotor

# --- Bluetooth card info for your hardware ----------------------------------
# Same Connection Card as the rest of this kit (see 9-10/, 9-17/).
CARD_COLOR = le.LEGO_COLOR_ORANGE
CARD_SERIAL = '0994'

TAG_ID = 0                # must match generate_tag.py's default
CAMERA_INDEX = 0
MAX_SPEED = 100            # speed cap sent to the Double Motor, in percent
DEAD_ZONE_PX = 15         # error smaller than this is treated as "centered"
                            # so the car doesn't buzz back and forth at zero

# Sign of the commanded speed is arbitrary until tested on real hardware --
# it depends on which way "forward" happens to be wired/oriented on your
# car. If the car drives away from center instead of toward it, flip this.
DRIVE_SIGN = 1

# Spring-loaded mode (see question 3 in the README): with little/no
# damping, the car behaves like a mass on a spring pulling it toward
# center -- it overshoots and oscillates back before settling. Turning
# damping up removes the overshoot and eases it in instead.
SPRING_LOADED = True
KP = 0.30
KD = 0.0 if SPRING_LOADED else 0.20


def main():
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {CAMERA_INDEX}")

    dm = doubleMotor()
    print("Connecting to Double Motor...")
    dm.connect(card_serial=CARD_SERIAL, card_color=CARD_COLOR)
    print("Connected.")

    # Derivative state. Reset whenever the tag is lost so reacquiring it
    # doesn't produce a derivative-kick spike from the gap in error history.
    prev_error = None
    prev_time = time.monotonic()

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            center_x = w / 2.0

            corners, ids, _ = detector.detectMarkers(frame)

            now = time.monotonic()
            dt = now - prev_time
            prev_time = now

            cx = None
            if ids is not None:
                for i, marker_id in enumerate(ids.flatten()):
                    if marker_id == TAG_ID:
                        pts = corners[i].reshape((4, 2))
                        cv2.polylines(frame, [pts.astype(int)], isClosed=True,
                                      color=(0, 0, 255), thickness=3)
                        cx, cy = pts.mean(axis=0)
                        cv2.circle(frame, (int(cx), int(cy)), 6, (0, 0, 255), -1)
                        cv2.putText(frame, f"({int(cx)}, {int(cy)})", (int(cx) + 10, int(cy) - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        break

            if cx is not None:
                error = center_x - cx
                d_error = 0.0 if prev_error is None or dt <= 0 else (error - prev_error) / dt
                speed = KP * error - KD * d_error
                if abs(error) < DEAD_ZONE_PX:
                    speed = 0.0
                speed = max(-MAX_SPEED, min(MAX_SPEED, speed)) * DRIVE_SIGN
                dm.run(speed=int(round(speed)))
                prev_error = error
                status = f"error: {error:+6.1f}px  speed: {speed:+6.1f}%"
            else:
                dm.stop()
                prev_error = None
                status = "NO TAG DETECTED - stopped"
                cv2.putText(frame, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.line(frame, (int(center_x), 0), (int(center_x), h), (255, 255, 0), 1)
            cv2.putText(frame, status, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("AprilTag centering", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        dm.stop()
        dm.disconnect()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
