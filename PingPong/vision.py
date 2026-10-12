"""
Camera-side sensing.

PoseTracker  MediaPipe Pose Landmarker (same model and setup as PoseRaceCar)
             -> where the paddle hand is, as a court x position.
TagReader    AprilTag 36h11 via cv2.aruco (as in AprilTagCentering), extended
             to report tag IDs, with a hold time so a tag has to be shown on
             purpose (~0.6 s) before it counts.
open_camera  copied from CustomRobotCentering/common.py: prefers the laptop
             camera over a nearby iPhone and checks it really gives frames.
"""

import os
import time
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions, vision

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "models", "pose_landmarker_lite.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task")

FRAME_W, FRAME_H = 640, 480


# ---------------------------------------------------------------------------
# Pose: wrist -> paddle x
# ---------------------------------------------------------------------------

class PoseTracker:
    def __init__(self, hand="right", reach=0.7, smoothing=0.6, min_visibility=0.5):
        """hand: the player's paddle hand. reach: how much of the camera's
        width maps onto the full court (smaller = less arm movement needed).
        smoothing: EMA weight on the newest reading (1 = no smoothing)."""
        if not os.path.exists(MODEL_PATH):
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            print(f"Downloading MediaPipe pose model to {MODEL_PATH} ...")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.PoseLandmarker.create_from_options(options)
        # MediaPipe's left/right are the person's own, and we run it on the
        # un-mirrored frame so that stays true.
        self.wrist = (vision.PoseLandmark.RIGHT_WRIST if hand == "right"
                      else vision.PoseLandmark.LEFT_WRIST).value
        self.reach = reach
        self.alpha = smoothing
        self.min_visibility = min_visibility
        self.court_x = None
        self.wrist_px = None        # (x, y) in the mirrored frame, for drawing
        self._last_ts = 0

    def update(self, frame_bgr):
        """Run pose on an un-mirrored frame. Returns the court x of the paddle
        hand in [0, 1], or None if the hand isn't visible."""
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts = max(int(time.monotonic() * 1000), self._last_ts + 1)   # must increase
        self._last_ts = ts
        result = self.landmarker.detect_for_video(image, ts)

        if not result.pose_landmarks:
            self.court_x = self.wrist_px = None
            return None
        p = result.pose_landmarks[0][self.wrist]
        if (p.visibility or 0) < self.min_visibility:
            self.court_x = self.wrist_px = None
            return None

        x = 1.0 - p.x                       # mirror: move right, paddle goes right
        h, w = frame_bgr.shape[:2]
        self.wrist_px = (int(x * w), int(p.y * h))
        target = (x - (0.5 - self.reach / 2)) / self.reach
        target = min(1.0, max(0.0, target))
        if self.court_x is None:
            self.court_x = target
        else:
            self.court_x += self.alpha * (target - self.court_x)
        return self.court_x

    def close(self):
        self.landmarker.close()


# ---------------------------------------------------------------------------
# AprilTags: level cards and pause
# ---------------------------------------------------------------------------

class TagReader:
    def __init__(self, hold=0.6):
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        self.detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
        self.hold = hold
        self.visible = []           # [(id, quad)] in the current frame
        self._candidate = None
        self._since = 0.0
        self._fired = False

    def update(self, frame_bgr, now):
        """Detect tags. Returns a tag ID once, when it has been held in view
        for `hold` seconds. Showing it again requires taking it away first."""
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)
        self.visible = [] if ids is None else [(int(i), c[0]) for i, c in zip(ids.flatten(), corners)]

        seen = self.visible[0][0] if self.visible else None
        if seen != self._candidate:
            self._candidate, self._since, self._fired = seen, now, False
            return None
        if seen is not None and not self._fired and now - self._since >= self.hold:
            self._fired = True
            return seen
        return None

    def progress(self, now):
        """(tag id, 0..1 of the hold time) for the tag being held, for the HUD."""
        if self._candidate is None or self._fired:
            return None
        return self._candidate, min(1.0, (now - self._since) / self.hold)


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------

def list_cameras():
    """[(index, name, is_builtin)] in OpenCV's macOS order (see
    CustomRobotCentering/common.py for why). [] if it can't tell."""
    try:
        import AVFoundation as avf
    except ImportError:
        return []
    devs = list(avf.AVCaptureDevice.devicesWithMediaType_(avf.AVMediaTypeVideo) or []) + \
        list(avf.AVCaptureDevice.devicesWithMediaType_(avf.AVMediaTypeMuxed) or [])
    devs.sort(key=lambda d: str(d.uniqueID()))
    out = []
    for i, d in enumerate(devs):
        name, kind = str(d.localizedName()), str(d.deviceType())
        try:
            phone = bool(d.isContinuityCamera())
        except Exception:
            phone = "Continuity" in kind
        builtin = not phone and ("FaceTime" in name or "BuiltIn" in kind)
        out.append((i, name, builtin))
    return out


def open_camera(index=None):
    cams = list_cameras()
    names = {i: n for i, n, _ in cams}
    if index is not None:
        indices = [index]
    else:
        builtin = [i for i, _, b in cams if b]
        indices = list(dict.fromkeys(builtin + [0, 1, 2, 3]))
    for idx in indices:
        cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)
        for _ in range(40):
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"Using camera {idx}" + (f" ({names[idx]})" if idx in names else ""))
                return cap
            time.sleep(0.05)
        print(f"Camera {idx} opened but produced no frames, trying next...")
        cap.release()
    raise RuntimeError("No camera delivered frames. Check System Settings -> "
                       "Privacy & Security -> Camera for your terminal app "
                       "(use Terminal.app or iTerm2, not the VS Code terminal).")
