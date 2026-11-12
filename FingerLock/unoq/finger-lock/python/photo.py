"""Small grey photos for the safe's alerts: a thumbnail of the whole camera
frame, encoded as PNG with numpy and zlib only (no OpenCV needed on the board)."""
import base64
import struct
import zlib

import numpy as np

from fingernet import shrink, to_grey

THUMB = (120, 160)      # height, width


def thumbnail(frame, size=THUMB):
    return np.clip(np.rint(shrink(to_grey(frame), size)), 0, 255).astype(np.uint8)


def aim_view(frame, frac, height=240, dim=1.0):
    """The whole camera frame, grey, with the network's square outlined (and
    everything outside it darkened to `dim` if below 1): for aiming the camera."""
    h, w = frame.shape[:2]
    img = thumbnail(frame, (height, max(1, round(height * w / h))))
    side = int(round(min(img.shape) * frac))
    top, left = (img.shape[0] - side) // 2, (img.shape[1] - side) // 2
    out = img.copy()
    if dim < 1:
        out = (img * dim).astype(np.uint8)
        out[top:top + side, left:left + side] = img[top:top + side, left:left + side]
    bottom, right = top + side - 1, left + side - 1
    out[[top, bottom], left:right + 1] = 255
    out[top:bottom + 1, [left, right]] = 255
    return out


def png_bytes(img):
    """8-bit grey image (H, W) -> PNG file bytes."""
    img = np.ascontiguousarray(img, dtype=np.uint8)
    h, w = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))     # filter type 0 on every row

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))     # 8-bit grey
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def png_base64(img):
    return base64.b64encode(png_bytes(img)).decode("ascii")
