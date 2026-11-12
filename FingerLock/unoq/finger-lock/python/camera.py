"""The board's USB webcam: App Lab's own camera class if it works, else OpenCV.

Which one works isn't settled yet (2026-11-08): forum posts describe a Camera
class in arduino.app_peripherals used as Camera("usb:0", resolution=(640, 480),
fps=15), then start() and capture() returning a numpy array or None, but the
installed package version decides the details. So this tries a few spellings,
then OpenCV on /dev/video*, and keeps a log of every attempt (main.py's camera
check prints it) so the first deploy shows what this board actually has.

Sources (community posts, not Arduino's docs):
- https://community.element14.com/challenges-projects/design-challenges/ez-ev-challenge/f/forum/57183/hall-w-ev---post-4---giving-it-eyes
- https://forum.arduino.cc/t/unable-to-connect-arduino-uno-q-to-webcam/1449124
"""
import glob
import importlib
import time

import numpy as np

APPLAB_CLASSES = [("arduino.app_peripherals.camera", "Camera"),
                  ("arduino.app_peripherals", "Camera"),
                  ("arduino.app_peripherals.usb_camera", "USBCamera")]


class BoardCamera:
    def __init__(self, width=640, height=480, fps=15):
        self.kind, self.cam, self.cap, self.log = None, None, None, []
        if not self._open_applab(width, height, fps):
            self._open_opencv(width, height)

    # ---- App Lab -----------------------------------------------------------------------

    def _open_applab(self, width, height, fps):
        for mod_name, cls_name in APPLAB_CLASSES:
            try:
                cls = getattr(importlib.import_module(mod_name), cls_name)
            except Exception as e:
                self.log.append(f"{mod_name}.{cls_name}: {e!r}")
                continue
            for args, kwargs in [(("usb:0",), {"resolution": (width, height), "fps": fps}),
                                 ((0,), {"resolution": (width, height), "fps": fps}),
                                 ((), {})]:
                label = f"{mod_name}.{cls_name}({', '.join(map(repr, args))})"
                try:
                    cam = cls(*args, **kwargs)
                    if hasattr(cam, "start"):
                        cam.start()
                    frame = self._first_frame(lambda: self._applab_read(cam))
                    if frame is not None:
                        self.cam, self.kind = cam, label
                        self.log.append(f"{label}: OK, {frame.shape}")
                        return True
                    self.log.append(f"{label}: opened but gave no frames")
                    self._close(cam)
                except Exception as e:
                    self.log.append(f"{label}: {e!r}")
        return False

    @staticmethod
    def _applab_read(cam):
        f = cam.capture() if hasattr(cam, "capture") else cam.read()
        if isinstance(f, tuple):            # (ok, frame), OpenCV style
            f = f[1]
        if f is None:
            return None
        if isinstance(f, (bytes, bytearray)):   # an encoded image
            import cv2
            f = cv2.imdecode(np.frombuffer(f, np.uint8), cv2.IMREAD_COLOR)
        return np.asarray(f)

    # ---- OpenCV ------------------------------------------------------------------------

    def _open_opencv(self, width, height):
        try:
            import cv2
        except Exception as e:
            self.log.append(f"cv2: {e!r}")
            return False
        # USB cameras by name first: on the UNO Q, /dev/video0 is the Qualcomm video
        # encoder (qcom-venus-encoder), not a camera. The webcam is e.g.
        # /dev/v4l/by-id/usb-icSpring_icspring_camera_..-video-index0 (seen 2026-11-09).
        usb = sorted(glob.glob("/dev/v4l/by-id/usb-*-video-index0"))
        for dev in usb + [0, 1, 2] + sorted(glob.glob("/dev/video*")):
            label = f"cv2.VideoCapture({dev!r})"
            try:
                cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap.release()
                    self.log.append(f"{label}: didn't open")
                    continue
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                frame = self._first_frame(lambda: cap.read()[1])
                if frame is not None:
                    self.cap, self.kind = cap, label
                    self.log.append(f"{label}: OK, {frame.shape}")
                    return True
                cap.release()
                self.log.append(f"{label}: opened but gave no frames")
            except Exception as e:
                self.log.append(f"{label}: {e!r}")
        return False

    # ---- common ------------------------------------------------------------------------

    @staticmethod
    def _first_frame(read, tries=40):
        for _ in range(tries):
            f = read()
            if f is not None and getattr(f, "size", 0):
                return f
            time.sleep(0.05)
        return None

    @staticmethod
    def _close(cam):
        for name in ("stop", "close", "release"):
            if hasattr(cam, name):
                try:
                    getattr(cam, name)()
                except Exception:
                    pass
                return

    def read(self):
        """One frame as a numpy array (H, W, 3), or None."""
        try:
            if self.cam is not None:
                return self._applab_read(self.cam)
            if self.cap is not None:
                ok, f = self.cap.read()
                return f if ok else None
        except Exception as e:
            self.log.append(f"read: {e!r}")
        return None

    def close(self):
        if self.cam is not None:
            self._close(self.cam)
        if self.cap is not None:
            self.cap.release()


def devices():
    """What the kernel sees, for the camera check."""
    return {"video": sorted(glob.glob("/dev/video*")), "by_id": sorted(glob.glob("/dev/v4l/by-id/*"))}
