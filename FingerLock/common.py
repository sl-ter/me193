"""Shared paths, settings and helpers for the laptop side of the Infallible Safe
(capture.py, train.py, laptop_lock.py, bench.py, movie/render.py).

The network and the rules live in the board app's python folder
(unoq/finger-lock/python/fingernet.py and lock_policy.py), like the wearable's
steps.py, so the laptop and the board run the very same code. Importing this
module puts that folder on the path.
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOARD_PY = HERE / "unoq" / "finger-lock" / "python"
sys.path.insert(0, str(BOARD_PY))

DATA_DIR = Path(os.environ.get("FINGERLOCK_DATA", HERE / "data"))   # gitignored: hand photos
FIG_DIR = HERE / "figures"
RUNS_DIR = HERE / "runs"                 # gitignored: laptop timing logs
INTRUDER_DIR = HERE / "intruders"        # gitignored: photos the laptop safe takes
CHECK_DIR = HERE / "check"               # gitignored: aiming snapshots (capture.py --aim)
MODEL_PATH = BOARD_PY / "fingernet_model.npz"
CODES_PATH = BOARD_PY / "codes.json"     # gitignored: your two codes + the MQTT topic
CODES_EXAMPLE = BOARD_PY / "codes.example.json"
SETTINGS_PATH = BOARD_PY / "settings.json"   # servo angles, owner threshold: shared with the board

OWNER = "SAM"             # the person folder in data/ whose hand opens the safe

BROKER = "broker.emqx.io"             # same broker as the wearable (test.mosquitto.org is blocked on Tufts Wi-Fi)
PORT = 1883

CAMERA_INDEX = 0
FRAME_W, FRAME_H = 640, 480


def load_codes(path=CODES_PATH, quiet=False):
    """The real code, the duress code and the MQTT topic, from codes.json.
    Falls back to codes.example.json (with a warning) so things still run
    before you've set your own with set_codes.py."""
    path = Path(path)
    if not path.exists():
        if not quiet:
            print(f"WARNING: {path.name} not found, using the EXAMPLE codes. "
                  "Run  python FingerLock/set_codes.py  to set yours.", flush=True)
        path = CODES_EXAMPLE
    with open(path) as f:
        c = json.load(f)
    return c["code"], c.get("duress"), c["topic"]


def load_settings(path=SETTINGS_PATH):
    """The board's settings.json (servo angles, owner threshold), or {} if missing."""
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else {}


def list_cameras():
    """[(index, name)] as OpenCV numbers the cameras on macOS, or [] if it can't
    tell. Same ordering trick as CustomRobotCentering/common.py: OpenCV sorts
    macOS cameras by their unique ID. Uses AVFoundation if pyobjc has it, else
    macOS's own camera list (system_profiler), which gives the same names and IDs.
    An iPhone nearby shows up too (Continuity Camera) and can take an index."""
    try:
        import AVFoundation as avf
        devs = list(avf.AVCaptureDevice.devicesWithMediaType_(avf.AVMediaTypeVideo) or []) + \
            list(avf.AVCaptureDevice.devicesWithMediaType_(avf.AVMediaTypeMuxed) or [])
        devs.sort(key=lambda d: str(d.uniqueID()))
        return [(i, str(d.localizedName())) for i, d in enumerate(devs)]
    except ImportError:
        pass
    try:
        import subprocess
        out = subprocess.run(["system_profiler", "SPCameraDataType", "-json"], capture_output=True,
                             text=True, timeout=20).stdout
        cams = sorted(json.loads(out).get("SPCameraDataType", []), key=lambda c: c.get("spcamera_unique-id", ""))
        return [(i, c.get("_name", "?")) for i, c in enumerate(cams)]
    except Exception:
        return []


def open_camera(index=CAMERA_INDEX, width=FRAME_W, height=FRAME_H, quiet=False):
    """Open camera `index` and make sure it really delivers frames (macOS opens
    Continuity Cameras and permission-denied devices 'successfully' without
    ever producing one). Returns the cv2.VideoCapture."""
    import cv2
    cap = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(index)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        for _ in range(40):
            ok, frame = cap.read()
            if ok and frame is not None:
                if not quiet:
                    names = dict(list_cameras())
                    print(f"Camera {index}" + (f" ({names[index]})" if index in names else "")
                          + f": {frame.shape[1]}x{frame.shape[0]}", flush=True)
                return cap
            time.sleep(0.05)
    cap.release()
    raise RuntimeError(f"Camera {index} gave no frames. Try  python FingerLock/capture.py --list, "
                       "and check System Settings > Privacy & Security > Camera for your terminal.")
