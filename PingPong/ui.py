"""
Everything pong.py draws. Look: broadcast sports graphics, not an app.
Dark ink background, a competition-blue table with crisp white lines, one
warm accent (the orange of a real ping-pong ball) for the ball and the best
score, azure for anything sweet-spot (the same colour the paddle's light
flashes on a sweet-spot hit), red only for misses. SF Pro throughout: small
tracked uppercase labels, big confident numbers.

The static parts (background, table, card backgrounds) are drawn once into a
cached layer; each frame copies it and draws the moving parts on top, so the
whole thing runs at ~60 fps in plain OpenCV.
"""

import math
import os

import cv2
import numpy as np

from game import BALL_R, HIT_Y, MAX_SPEED, SWEET_SPOT

# ---------------------------------------------------------------------------
# Type
# ---------------------------------------------------------------------------

_SF = "/System/Library/Fonts/SFNS.ttf"
_FONT = cv2.FontFace(_SF) if os.path.exists(_SF) and hasattr(cv2, "FontFace") else None


def text_w(s, size, weight=400):
    if _FONT is None:
        (w, _), _ = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, size / 30, 1)
        return w
    return cv2.getTextSize((0, 0), s, (0, 0), _FONT, size, weight, 0)[2]


def txt(img, s, org, size, color, weight=400, align="left"):
    """Text with its baseline at org. align: left | center | right."""
    x, y = int(org[0]), int(org[1])
    if align != "left":
        w = text_w(s, size, weight)
        x -= w // 2 if align == "center" else w
    if _FONT is None:
        cv2.putText(img, s, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size / 30, color,
                    max(1, weight // 400), cv2.LINE_AA)
    else:
        cv2.putText(img, s, (x, y), color, _FONT, size, weight)


def label(img, s, org, color=None, size=11, align="left", tracking=1.6):
    """Small uppercase label with letter spacing, the broadcast-graphics way."""
    color = color or LABEL
    s = s.upper()
    widths = [text_w(c, size, 650) for c in s]
    total = sum(widths) + tracking * (len(s) - 1)
    x = org[0] - (total / 2 if align == "center" else total if align == "right" else 0)
    for c, w in zip(s, widths):
        if c != " ":
            txt(img, c, (x, org[1]), size, color, 650)
        x += w + tracking


# ---------------------------------------------------------------------------
# Palette (BGR) and layout
# ---------------------------------------------------------------------------

def _hex(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


INK = _hex("0A0C0F")
PANEL = _hex("12151A")
EDGE = _hex("1E232B")
LABEL = _hex("7D8794")
MUTED = _hex("4A525E")
TEXT = _hex("EEF1F4")
TABLE_TOP, TABLE_BOT = _hex("1A4E7C"), _hex("113657")
LINES = _hex("E9EEF2")
WALL = _hex("0B2238")
BALL = _hex("FF8A3D")
PADDLE = _hex("F1EEE8")
AZURE = _hex("3FC5F0")
RED = _hex("FF4D4F")
GREEN = _hex("3DDC97")

WIN_W, WIN_H = 1120, 740
M = 24
COURT = (M, M, 620, WIN_H - 2 * M)                  # x, y, w, h
SIDE_X = M + 620 + 28
SIDE_W = WIN_W - SIDE_X - M
CAM = (SIDE_X, M, SIDE_W, 265)


def to_px(x, y):
    cx, cy, cw, ch = COURT
    return int(round(cx + x * cw)), int(round(cy + y * ch))


def lerp(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def rounded_rect(img, rect, r, color, thickness=-1):
    x, y, w, h = map(int, rect)
    r = int(max(0, min(r, w // 2, h // 2)))
    if thickness < 0:
        cv2.rectangle(img, (x + r, y), (x + w - r, y + h), color, -1)
        cv2.rectangle(img, (x, y + r), (x + w, y + h - r), color, -1)
        for cx, cy in ((x + r, y + r), (x + w - r, y + r), (x + r, y + h - r), (x + w - r, y + h - r)):
            cv2.circle(img, (cx, cy), r, color, -1, cv2.LINE_AA)
    else:
        t = thickness
        for p0, p1 in (((x + r, y), (x + w - r, y)), ((x + r, y + h), (x + w - r, y + h)),
                       ((x, y + r), (x, y + h - r)), ((x + w, y + r), (x + w, y + h - r))):
            cv2.line(img, p0, p1, color, t, cv2.LINE_AA)
        for (cx, cy), a in (((x + r, y + r), 180), ((x + w - r, y + r), 270),
                            ((x + w - r, y + h - r), 0), ((x + r, y + h - r), 90)):
            cv2.ellipse(img, (cx, cy), (r, r), a, 0, 90, color, t, cv2.LINE_AA)


def blend(img, rect, draw, alpha):
    """Run draw(overlay, ox, oy) on a copy of img[rect] and blend it back
    with the given alpha. Keeps translucent effects cheap: only the
    rectangle is touched. draw gets the rect's origin to offset coordinates."""
    x, y, w, h = map(int, rect)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return
    roi = img[y0:y1, x0:x1]
    over = roi.copy()
    draw(over, x0, y0)
    cv2.addWeighted(over, alpha, roi, 1 - alpha, 0, dst=roi)


def pill(img, center, s, size, fg, bg, weight=650, pad=(12, 7)):
    w = text_w(s, size, weight)
    cx, cy = center
    rect = (cx - w / 2 - pad[0], cy - size / 2 - pad[1], w + 2 * pad[0], size + 2 * pad[1])
    rounded_rect(img, rect, (size + 2 * pad[1]) // 2, bg)
    txt(img, s, (cx, cy + size * 0.36), size, fg, weight, "center")


def arc(img, center, r, frac, color, thickness=4, track=None):
    if track is not None:
        cv2.circle(img, center, r, track, thickness, cv2.LINE_AA)
    if frac > 0:
        cv2.ellipse(img, center, (r, r), -90, 0, 360 * min(1.0, frac), color, thickness, cv2.LINE_AA)


def keycap(img, x, y, key, desc):
    w = max(22, text_w(key, 12, 650) + 12)
    rounded_rect(img, (x, y - 15, w, 21), 5, EDGE)
    txt(img, key, (x + w / 2, y), 12, TEXT, 650, "center")
    txt(img, desc, (x + w + 7, y), 12, LABEL, 500)
    return x + w + 7 + text_w(desc, 12, 500) + 16


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self):
        self.static = self._static_layer()
        cw, ch = CAM[2], CAM[3]
        mask = np.zeros((ch, cw), np.uint8)
        rounded_rect(mask, (0, 0, cw - 1, ch - 1), 12, 255)
        self.cam_mask = cv2.merge([mask] * 3).astype(np.float32) / 255.0
        self.fx = []                     # transient effects: dicts with "t0"
        self._last = {}                  # value -> (previous, time it changed), for number pops

    # -- static ---------------------------------------------------------------

    def _static_layer(self):
        img = np.full((WIN_H, WIN_W, 3), INK, np.uint8)
        cx, cy, cw, ch = COURT

        # table: vertical gradient, rounded, with a soft vignette
        grad = np.linspace(0, 1, ch)[:, None, None]
        table = (np.array(TABLE_TOP) * (1 - grad) + np.array(TABLE_BOT) * grad)
        table = np.repeat(table, cw, axis=1)
        yy, xx = np.mgrid[0:ch, 0:cw]
        d = np.sqrt(((xx - cw / 2) / (cw / 2)) ** 2 + ((yy - ch / 2) / (ch / 2)) ** 2)
        table *= (1 - 0.18 * np.clip(d - 0.55, 0, 1))[:, :, None]
        mask = np.zeros((ch, cw), np.uint8)
        rounded_rect(mask, (0, 0, cw - 1, ch - 1), 14, 255)
        m = (mask.astype(np.float32) / 255.0)[:, :, None]
        self.court_mask = m
        region = img[cy:cy + ch, cx:cx + cw].astype(np.float32)
        img[cy:cy + ch, cx:cx + cw] = (table * m + region * (1 - m)).astype(np.uint8)

        # the wall (the opponent) along the top
        wall_h = 18
        cv2.rectangle(img, (cx + 14, cy), (cx + cw - 14, cy + wall_h), WALL, -1)
        cv2.rectangle(img, (cx, cy + 14), (cx + cw, cy + wall_h), WALL, -1)
        rounded_rect(img, (cx, cy, cw, wall_h + 6), 14, WALL)
        cv2.rectangle(img, (cx, cy + wall_h), (cx + cw, cy + wall_h + 6), WALL, -1)
        cv2.line(img, (cx + 14, cy + wall_h + 6), (cx + cw - 14, cy + wall_h + 6), lerp(WALL, LINES, 0.35), 1, cv2.LINE_AA)
        label(img, "Wall", (cx + cw / 2, cy + 18), lerp(WALL, LINES, 0.45), 10, "center", 3)

        # white table lines: border inset, centre line
        inset = 10
        rounded_rect(img, (cx + inset, cy + wall_h + 6 + inset, cw - 2 * inset,
                           ch - wall_h - 6 - 2 * inset), 6, lerp(TABLE_BOT, LINES, 0.85), 2)
        blend(img, (cx, cy, cw, ch), lambda o, ox, oy: cv2.line(
            o, (cx + cw // 2 - ox, cy + wall_h + 6 + inset - oy), (cx + cw // 2 - ox, cy + ch - inset - oy),
            LINES, 1, cv2.LINE_AA), 0.35)

        # hitting line: fine dashes
        y = to_px(0, HIT_Y)[1]
        for x0 in range(cx + inset + 4, cx + cw - inset - 4, 14):
            cv2.line(img, (x0, y), (min(x0 + 6, cx + cw - inset - 4), y), lerp(TABLE_BOT, LINES, 0.45), 1, cv2.LINE_AA)

        # sidebar cards
        rounded_rect(img, (CAM[0] - 1, CAM[1] - 1, CAM[2] + 2, CAM[3] + 2), 13, EDGE)
        rounded_rect(img, (SIDE_X, 305, SIDE_W, WIN_H - 305 - 62), 14, PANEL)
        return img

    # -- per frame ----------------------------------------------------------------

    def _pop(self, key, value, now):
        """Size multiplier that kicks up briefly whenever value changes."""
        prev, t = self._last.get(key, (value, -10.0))
        if value != prev:
            t = now if value > prev else -10.0     # only pop on increases
            self._last[key] = (value, t)
        return 1 + 0.22 * math.exp(-(now - t) / 0.12)

    def add_hit(self, x, sweet, spin, now):
        self.fx.append({"kind": "burst", "x": x, "color": AZURE if sweet else PADDLE, "t0": now,
                        "big": sweet})
        s = "Sweet spot" if sweet else "Hit"
        if spin:
            s += f"  ·  curve {'right' if spin > 0 else 'left'} {abs(spin):.0%}"
        self.fx.append({"kind": "toast", "text": s, "color": AZURE if sweet else TEXT, "t0": now})

    def add_miss(self, reason, now):
        self.fx.append({"kind": "missline", "t0": now})
        self.fx.append({"kind": "toast", "text": f"Miss  ·  {reason}", "color": RED, "t0": now})

    def draw(self, v):
        """v: dict of everything to show (see pong.py)."""
        img = self.static.copy()
        now = v["now"]
        self.fx = [f for f in self.fx if now - f["t0"] < 1.6]
        self._court(img, v, now)
        self._camera(img, v, now)
        self._stats(img, v, now)
        self._footer(img)
        self._overlay(img, v, now)
        return img

    # -- court ----------------------------------------------------------------------

    def _court(self, img, v, now):
        game = v["game"]
        cx, cy, cw, ch = COURT
        r = max(5, int(BALL_R * cw))

        # miss: the hitting line flashes red
        for f in self.fx:
            if f["kind"] == "missline":
                a = 1 - (now - f["t0"]) / 0.6
                if a > 0:
                    y = to_px(0, HIT_Y)[1]
                    blend(img, (cx, y - 3, cw, 7), lambda o, ox, oy: cv2.rectangle(
                        o, (10, 0), (cw - 10, 6), RED, -1), 0.8 * a)

        # trail: fades into the table
        trail = [(min(1.0, max(0.0, tx)), min(1.0, max(0.03, ty))) for tx, ty in v["trail"]]
        for i in range(1, len(trail)):
            t = i / len(trail)
            p0, p1 = to_px(*trail[i - 1]), to_px(*trail[i])
            base = lerp(TABLE_TOP, TABLE_BOT, min(1, max(0, trail[i][1])))
            cv2.line(img, p0, p1, lerp(base, BALL, 0.55 * t), max(1, int(r * 1.3 * t)), cv2.LINE_AA)

        # ball: soft shadow, glow, core, highlight
        if game.in_play:
            bx, by = to_px(game.x, min(game.y, 1.0))
            blend(img, (bx - 2 * r, by - r, 5 * r, 4 * r),
                  lambda o, ox, oy: cv2.ellipse(o, (bx + 3 - ox, by + 6 - oy), (int(r * 0.9), int(r * 0.6)), 0, 0, 360,
                                                (0, 0, 0), -1, cv2.LINE_AA), 0.28)
            cv2.circle(img, (bx, by), r, BALL, -1, cv2.LINE_AA)
            cv2.circle(img, (bx - r // 3, by - r // 3), max(1, r // 3), lerp(BALL, (255, 255, 255), 0.6), -1, cv2.LINE_AA)

        # contact bursts: an expanding ring where the ball met the paddle
        for f in self.fx:
            if f["kind"] == "burst":
                t = (now - f["t0"]) / (0.55 if f["big"] else 0.4)
                if t < 1:
                    px, py = to_px(f["x"], HIT_Y)
                    rad = int(r + (70 if f["big"] else 40) * ease_out(t))
                    blend(img, (px - rad - 4, py - rad - 4, 2 * rad + 8, 2 * rad + 8),
                          lambda o, ox, oy, rad=rad, f=f: cv2.circle(
                              o, (px - ox, py - oy), rad, f["color"], 3 if f["big"] else 2, cv2.LINE_AA),
                          0.9 * (1 - t))

        # paddle: shadow, body, sweet-spot band, swing glow
        half = game.level.paddle_w / 2
        seen = v["paddle_seen"]
        x0, y0 = to_px(v["paddle_x"] - half, HIT_Y + 0.010)
        x1, y1 = to_px(v["paddle_x"] + half, HIT_Y + 0.030)
        h = y1 - y0
        swing = max(0.0, 1 - v["swing_age"] / 0.22)
        blend(img, (x0, y0 + 2, x1 - x0 + 4, h + 6),
              lambda o, ox, oy: rounded_rect(o, (x0 + 2 - ox, y0 + 4 - oy, x1 - x0, h), h // 2, (0, 0, 0)), 0.25)
        if swing > 0 and seen:
            grow = int(4 + 8 * (1 - swing))
            blend(img, (x0 - 16, y0 - 16, x1 - x0 + 32, h + 32),
                  lambda o, ox, oy: rounded_rect(o, (x0 - grow - ox, y0 - grow - oy, x1 - x0 + 2 * grow, h + 2 * grow),
                                                 (h + 2 * grow) // 2, PADDLE, 2), 0.8 * swing)
        body = PADDLE if seen else MUTED
        rounded_rect(img, (x0, y0, x1 - x0, h), h // 2, body)
        sw = (x1 - x0) * SWEET_SPOT / 2
        mid = (x0 + x1) / 2
        cv2.line(img, (int(mid - sw), y0 + h // 2), (int(mid + sw), y0 + h // 2),
                 AZURE if seen else LABEL, 3, cv2.LINE_AA)
        if not seen:
            pill(img, (cx + cw // 2, y1 + 36), "Hand not visible", 13, TEXT, lerp(INK, RED, 0.55))

        # event toasts, top of the court, drifting up as they fade
        toasts = [f for f in self.fx if f["kind"] == "toast"]
        if toasts:
            f = toasts[-1]
            t = (now - f["t0"]) / 1.5
            if t < 1:
                a = min(1.0, 4 * (1 - t))
                y = cy + 70 - int(10 * ease_out(t))
                w = text_w(f["text"], 15, 650) + 32
                blend(img, (cx + cw / 2 - w / 2 - 2, y - 18, w + 4, 38),
                      lambda o, ox, oy: (rounded_rect(o, (cx + cw / 2 - w / 2 - ox, y - 16 - oy, w, 32), 16, INK),
                                         txt(o, f["text"], (cx + cw / 2 - ox, y + 5 - oy), 15, f["color"], 650,
                                             "center")), 0.92 * a)

    # -- camera card ------------------------------------------------------------------

    def _camera(self, img, v, now):
        x, y, w, h = CAM
        frame = v["frame"]
        if frame is None:
            label(img, "Starting camera", (x + w / 2, y + h / 2), LABEL, 11, "center")
            return
        view = cv2.flip(frame, 1)
        fh, fw = view.shape[:2]
        crop_h = int(fw * h / w)
        top = max(0, (fh - crop_h) // 2)
        view = view[top:top + crop_h]
        sx, sy = w / fw, h / view.shape[0]

        small = cv2.resize(view, (w, h), interpolation=cv2.INTER_AREA)
        small = cv2.convertScaleAbs(small, alpha=0.85, beta=-6)    # sit the feed back a little

        def cam_pt(px, py):
            return int((fw - px) * sx), int((py - top) * sy)

        for tag_id, quad in v["tags_visible"]:
            pts = np.array([cam_pt(px, py) for px, py in quad], np.int32)
            cv2.polylines(small, [pts], True, BALL, 2, cv2.LINE_AA)
            top_y = int(pts[:, 1].min())
            c = pts.mean(axis=0).astype(int)
            pill(small, (int(c[0]), max(14, top_y - 16)), f"Tag {tag_id}", 12, INK, BALL)
        if v["wrist_px"] is not None:
            wx, wy = v["wrist_px"]                    # already in the mirrored frame
            p = (int(wx * sx), int((wy - top) * sy))
            cv2.circle(small, p, 13, PADDLE, 2, cv2.LINE_AA)
            cv2.circle(small, p, 3, PADDLE, -1, cv2.LINE_AA)

        region = img[y:y + h, x:x + w].astype(np.float32)
        img[y:y + h, x:x + w] = (small * self.cam_mask + region * (1 - self.cam_mask)).astype(np.uint8)

        # status chip, top left
        ok = v["pose_ok"]
        chip = "Tracking hand" if ok else "No hand"
        cw_ = text_w(chip, 12, 600) + 34
        blend(img, (x + 10, y + 10, cw_, 26), lambda o, ox, oy: rounded_rect(
            o, (x + 10 - ox, y + 10 - oy, cw_, 26), 13, INK), 0.75)
        cv2.circle(img, (x + 24, y + 23), 4, GREEN if ok else RED, -1, cv2.LINE_AA)
        txt(img, chip, (x + 34, y + 28), 12, TEXT, 600)

        # tag being held: progress along the bottom edge of the card
        held = v["tag_progress"]
        if held is not None:
            tag_id, frac = held
            cv2.line(img, (x + 12, y + h - 8), (x + 12 + int((w - 24) * frac), y + h - 8), BALL, 4, cv2.LINE_AA)

    # -- stats card ------------------------------------------------------------------

    def _stats(self, img, v, now):
        game = v["game"]
        x, y = SIDE_X + 22, 305
        col2 = SIDE_X + SIDE_W // 2 + 8

        # streak / best
        label(img, "Streak", (x, y + 32))
        label(img, "Best", (col2, y + 32))
        s = self._pop("streak", game.streak, now)
        txt(img, str(game.streak), (x - 2, y + 98), int(64 * s), TEXT, 700)
        s = self._pop("record", game.record, now)
        txt(img, str(game.record), (col2 - 2, y + 98), int(64 * s), BALL, 700)

        # sweet-spot streak
        y2 = y + 132
        cv2.line(img, (x, y2 - 14), (SIDE_X + SIDE_W - 22, y2 - 14), EDGE, 1)
        label(img, "Sweet-spot streak", (x, y2 + 12))
        s = self._pop("sweet", game.sweet_streak, now)
        txt(img, str(game.sweet_streak), (x - 1, y2 + 58), int(40 * s), AZURE, 700)
        nw = text_w(str(game.sweet_streak), int(40 * s), 700)
        txt(img, f"best {game.sweet_record}", (x + nw + 12, y2 + 57), 14, LABEL, 500)

        # level
        label(img, "Level", (col2, y2 + 12))
        pill(img, (col2 + 40, y2 + 44), game.level.name.capitalize(), 14, INK, TEXT, 700)

        # speed + spin meters
        y3 = y2 + 92
        bar_w = SIDE_W // 2 - 44
        label(img, "Ball speed", (x, y3))
        frac = game.speed / MAX_SPEED if game.in_play else 0
        rounded_rect(img, (x, y3 + 12, bar_w, 6), 3, EDGE)
        if frac > 0:
            rounded_rect(img, (x, y3 + 12, max(6, int(bar_w * min(1, frac))), 6), 3, BALL)
        txt(img, f"{game.speed:.2f}" if game.in_play else "–", (x + bar_w, y3), 12, LABEL, 500, "right")

        spin = game.last_hit["spin"] if game.last_hit else 0.0
        label(img, "Last spin", (col2, y3))
        mid = col2 + bar_w // 2
        rounded_rect(img, (col2, y3 + 12, bar_w, 6), 3, EDGE)
        cv2.line(img, (mid, y3 + 9), (mid, y3 + 21), MUTED, 1)
        if spin:
            end = int(mid + spin * bar_w / 2)
            rounded_rect(img, (min(mid, end), y3 + 12, max(6, abs(end - mid)), 6), 3, AZURE)
        spin_s = "flat" if not spin else f"{'R' if spin > 0 else 'L'} {abs(spin):.0%}"
        txt(img, spin_s, (col2 + bar_w, y3), 12, LABEL, 500, "right")

        # sensors / links
        y4 = y3 + 48
        cv2.line(img, (x, y4 - 10), (SIDE_X + SIDE_W - 22, y4 - 10), EDGE, 1)
        rows = [
            ("Paddle", v["paddle_name"], v["imu_rate"] > 0 or v["paddle_name"].startswith("keyboard")),
            ("IMU", f"{v['imu_rate']:.0f} Hz  ·  swing threshold {v['threshold']}", v["imu_rate"] > 0),
            ("MQTT", v["mqtt_status"], v["mqtt_ok"]),
        ]
        for i, (k, val, ok) in enumerate(rows):
            yy = y4 + 14 + i * 24
            cv2.circle(img, (x + 3, yy - 4), 3, GREEN if ok else MUTED, -1, cv2.LINE_AA)
            label(img, k, (x + 14, yy), LABEL, 10, tracking=1.4)
            txt(img, val, (x + 82, yy), 13, TEXT, 500)

    def _footer(self, img):
        x, y = SIDE_X + 4, WIN_H - M - 6
        for key, desc in (("Q", "quit"), ("C", "recalibrate"), ("P", "pause"), ("1–3", "level")):
            x = keycap(img, x, y, key, desc)

    # -- modal overlays ------------------------------------------------------------------

    def _overlay(self, img, v, now):
        state = v["state"]
        if state not in ("WAIT_TAG", "CALIBRATE", "COUNTDOWN", "PAUSED"):
            return
        cx, cy, cw, ch = COURT
        court = img[cy:cy + ch, cx:cx + cw]
        small = cv2.resize(court, (cw // 4, ch // 4), interpolation=cv2.INTER_AREA)
        small = cv2.GaussianBlur(small, (0, 0), 2.5)
        blurred = cv2.convertScaleAbs(cv2.resize(small, (cw, ch), interpolation=cv2.INTER_LINEAR), alpha=0.55)
        court[:] = blurred
        k = 16                              # only the rounded corners need the mask
        for ys in (slice(0, k), slice(ch - k, ch)):
            for xs in (slice(0, k), slice(cw - k, cw)):
                m = self.court_mask[ys, xs]
                court[ys, xs] = (blurred[ys, xs] * m + self.static[cy:cy + ch, cx:cx + cw][ys, xs] * (1 - m)).astype(np.uint8)

        card = (cx + 50, cy + ch // 2 - 150, cw - 100, 300)
        mx, my = cx + cw // 2, cy + ch // 2
        blend(img, card, lambda o, ox, oy: rounded_rect(o, (card[0] - ox, card[1] - oy, card[2], card[3]), 18, PANEL), 0.94)
        rounded_rect(img, card, 18, EDGE, 1)
        elapsed = now - v["state_t"]

        if state == "WAIT_TAG":
            label(img, "Ping-pong", (mx, my - 100), BALL, 12, "center", 3)
            txt(img, "Show a tag to start", (mx, my - 52), 32, TEXT, 700, "center")
            txt(img, "Hold it up to the camera for a second", (mx, my - 22), 15, LABEL, 500, "center")
            held = v["tag_progress"]
            chips = [("1", "Easy"), ("2", "Medium"), ("3", "Hard")]
            for i, (n, name) in enumerate(chips):
                bx = mx + (i - 1) * 132
                rect = (bx - 56, my + 12, 112, 74)
                rounded_rect(img, rect, 12, EDGE)
                active = held is not None and held[0] == int(n)
                if active:
                    fill = int(112 * held[1])
                    blend(img, rect, lambda o, ox, oy: cv2.rectangle(
                        o, (rect[0] - ox, rect[1] - oy), (rect[0] + fill - ox, rect[1] + 74 - oy), BALL, -1), 0.25)
                    rounded_rect(img, rect, 12, BALL, 2)
                txt(img, n, (bx, my + 50), 28, BALL if active else TEXT, 700, "center")
                label(img, name, (bx, my + 72), TEXT if active else LABEL, 10, "center")
            txt(img, "Tag 0 pauses during play", (mx, my + 122), 13, MUTED, 500, "center")

        elif state == "CALIBRATE":
            frac = elapsed / v["calibrate_s"]
            arc(img, (mx, my - 30), 46, frac, BALL, 5, EDGE)
            txt(img, f"{max(0.0, v['calibrate_s'] - elapsed):.1f}", (mx, my - 20), 26, TEXT, 700, "center")
            txt(img, "Hold the paddle still", (mx, my + 62), 26, TEXT, 700, "center")
            txt(img, "Measuring the gyro at rest to set the swing threshold", (mx, my + 92), 14, LABEL, 500, "center")

        elif state == "COUNTDOWN":
            left = v["countdown_s"] - elapsed
            n = int(left) + 1
            label(img, v["game"].level.name, (mx, my - 100), BALL, 12, "center", 3)
            arc(img, (mx, my - 18), 62, 1 - (left % 1), TEXT, 4, EDGE)
            sub = left % 1
            s = 1 + 0.25 * ease_out(max(0.0, sub - 0.75) * 4)
            txt(img, str(n), (mx, my + 4), int(62 * s), TEXT, 800, "center")
            txt(img, "Move your hand to move the paddle. Swing to hit.", (mx, my + 92), 14, LABEL, 500, "center")

        elif state == "PAUSED":
            label(img, "Paused", (mx, my - 60), BALL, 12, "center", 3)
            txt(img, "Take a breather", (mx, my - 10), 32, TEXT, 700, "center")
            txt(img, "Show tag 0 or press P to resume", (mx, my + 24), 15, LABEL, 500, "center")
