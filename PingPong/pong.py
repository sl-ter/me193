#!/usr/bin/env python3
"""
Virtual ping-pong against a wall, with a LEGO Double Motor as the paddle.

  pose (MediaPipe)  where your paddle hand is  -> paddle position on the court
  IMU (Double Motor) whether you're swinging   -> a hit needs a swing in time
  AprilTag           tag 1/2/3 = easy/medium/hard, starts the game; tag 0 = pause
  MQTT               record streak, as a float, to ME193/Rogers/Sam on every hit/miss
  spin               twist the paddle as you swing to curve the ball
  haptics            light rumble that speeds up as the ball approaches, a
                     stiff kick on contact, a long rumble on a miss

Run (from Terminal.app/iTerm2 -- the VS Code terminal loses camera permission):
  venv/bin/python pong.py                              # LEGO paddle, card orange 0994
  venv/bin/python pong.py --twist-axis y --twist-sign -1   # from check_paddle.py's twist test
  venv/bin/python pong.py --paddle keyboard --no-mqtt  # no hardware: space/z/x = swing

Keys: q/Esc quit, c recalibrate, p pause, 1/2/3 pick a level without a tag.
"""

import argparse
import sys
import time
from collections import deque

import cv2
import numpy as np

from game import HIT_Y, BALL_R, LEVELS, Game
from paddles import KeyboardPaddle, LegoPaddle
from swing import SwingDetector
from vision import PoseTracker, TagReader, open_camera

TOPIC = "ME193/Rogers/Sam"
CALIBRATE_S = 2.0
COUNTDOWN_S = 3.0

# Approach rumble: once the ball is RUMBLE_START seconds away, light ticks
# start every RUMBLE_SLOW s and speed up to every RUMBLE_FAST s at contact.
RUMBLE_START = 1.0
RUMBLE_SLOW, RUMBLE_FAST = 0.40, 0.09
PAUSE_TAG = 0

WIN_W, WIN_H = 1000, 720
COURT = (20, 20, 600, 680)          # x, y, w, h in window pixels
SIDE_X = 650
PREVIEW_W, PREVIEW_H = 330, 248

# colors (BGR)
BG = (28, 24, 22)
TABLE = (92, 60, 18)
LINE = (235, 235, 235)
WALL = (70, 70, 200)
BALL = (40, 200, 255)
PADDLE = (90, 210, 90)
PADDLE_OFF = (110, 110, 110)
SWING = (255, 255, 255)
TEXT = (235, 235, 235)
DIM = (150, 150, 150)
BAD = (80, 80, 240)
GOOD = (120, 230, 120)


# ---------------------------------------------------------------------------
# MQTT score
# ---------------------------------------------------------------------------

class Scoreboard:
    """Publishes the record streak as a float. Never lets a broker problem
    stop the game."""

    def __init__(self, topic, enabled=True):
        self.topic = topic
        self.client = None
        self.status = "off"
        if not enabled:
            return
        try:
            from mqttlib import MQTTClient
            self.client = MQTTClient()
            self.client.connect(timeout=5)
            self.status = f"-> {topic}"
        except Exception as e:
            print(f"MQTT unavailable ({e}); playing offline.")
            self.client = None
            self.status = "offline"

    def publish(self, record):
        if self.client is None:
            return
        try:
            self.client.publish(self.topic, str(float(record)))
        except Exception as e:
            self.status = f"error: {e}"

    def close(self):
        if self.client is not None:
            self.client.disconnect()


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def to_px(x, y):
    cx, cy, cw, ch = COURT
    return int(cx + x * cw), int(cy + y * ch)


def text(img, s, org, scale=0.6, color=TEXT, thick=1, center=False):
    if center:
        (w, h), _ = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        org = (org[0] - w // 2, org[1] + h // 2)
    cv2.putText(img, s, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def draw_court(img, game, paddle_x, swing_flash, trail, now):
    cx, cy, cw, ch = COURT
    cv2.rectangle(img, (cx, cy), (cx + cw, cy + ch), TABLE, -1)
    cv2.rectangle(img, (cx, cy), (cx + cw, cy + ch), LINE, 2)
    cv2.line(img, (cx + cw // 2, cy), (cx + cw // 2, cy + ch), (130, 100, 60), 1)
    # the wall / opponent
    cv2.rectangle(img, (cx, cy), (cx + cw, cy + 14), WALL, -1)
    text(img, "WALL", (cx + cw // 2, cy + 30), 0.5, DIM, center=True)
    # hitting line
    y = to_px(0, HIT_Y)[1]
    for x0 in range(cx, cx + cw, 20):
        cv2.line(img, (x0, y), (min(x0 + 10, cx + cw), y), DIM, 1)

    # ball trail + ball
    r = max(4, int(BALL_R * cw))
    for i, (bx, by) in enumerate(trail):
        fade = (i + 1) / (len(trail) + 1)
        cv2.circle(img, to_px(bx, min(by, 1.0)), int(r * fade), tuple(int(c * fade) for c in BALL), -1)
    if game.in_play:
        cv2.circle(img, to_px(game.x, min(game.y, 1.0)), r, BALL, -1, cv2.LINE_AA)

    # paddle
    half = game.level.paddle_w / 2
    seen = paddle_x is not None
    px = paddle_x if seen else 0.5
    color = SWING if now - swing_flash < 0.15 else (PADDLE if seen else PADDLE_OFF)
    p0, p1 = to_px(px - half, HIT_Y + 0.008), to_px(px + half, HIT_Y + 0.03)
    cv2.rectangle(img, p0, p1, color, -1)
    sweet = game.level.paddle_w * 0.25 / 2
    cv2.line(img, to_px(px - sweet, HIT_Y + 0.03), to_px(px + sweet, HIT_Y + 0.03), GOOD if seen else DIM, 3)
    if not seen:
        text(img, "hand not visible", to_px(0.5, HIT_Y + 0.07), 0.55, BAD, center=True)


def draw_preview(img, frame, pose, tags, now):
    view = cv2.flip(frame, 1)
    h, w = view.shape[:2]
    for tag_id, quad in tags.visible:
        q = quad.copy()
        q[:, 0] = w - q[:, 0]
        cv2.polylines(view, [q.astype(np.int32)], True, (0, 255, 255), 3)
        c = q.mean(axis=0).astype(int)
        text(view, f"tag {tag_id}", (c[0] - 30, c[1]), 0.8, (0, 255, 255), 2)
    if pose.wrist_px is not None:
        cv2.circle(view, pose.wrist_px, 14, PADDLE, 3)
    small = cv2.resize(view, (PREVIEW_W, PREVIEW_H))
    img[20:20 + PREVIEW_H, SIDE_X:SIDE_X + PREVIEW_W] = small
    cv2.rectangle(img, (SIDE_X, 20), (SIDE_X + PREVIEW_W, 20 + PREVIEW_H), DIM, 1)
    held = tags.progress(now)
    if held is not None:
        tag_id, frac = held
        y = 20 + PREVIEW_H + 6
        cv2.rectangle(img, (SIDE_X, y), (SIDE_X + int(PREVIEW_W * frac), y + 6), (0, 255, 255), -1)


def draw_hud(img, game, state, paddle, detector, board, note):
    x, y = SIDE_X, 20 + PREVIEW_H + 40
    lv = game.level
    text(img, f"Level: {lv.name}", (x, y), 0.7)
    text(img, f"Streak: {game.streak}", (x, y + 45), 1.1, GOOD, 2)
    text(img, f"Record: {game.record}", (x, y + 90), 1.1, BALL, 2)
    text(img, f"Ball speed: {game.speed:.2f}" if game.in_play else "Ball speed: -", (x, y + 122), 0.55, DIM)
    rate = getattr(paddle, "sample_rate", 0.0)
    text(img, f"Paddle: {paddle.name}", (x, y + 178), 0.5, DIM)
    thr = "-" if detector.threshold is None else f"{detector.threshold:.0f}"
    text(img, f"IMU {rate:.0f} Hz   swing threshold {thr}", (x, y + 201), 0.5, DIM)
    text(img, f"MQTT {board.status}", (x, y + 224), 0.5, DIM)
    if note:
        text(img, note, (x, y + 262), 0.6, note_color(note))
    spin = game.last_hit["spin"] if game.last_hit else 0.0
    text(img, f"Last spin: {spin_label(spin)}", (x, y + 145), 0.55, DIM)
    text(img, "q quit  c recalibrate  p pause", (x, WIN_H - 20), 0.45, DIM)


def spin_label(spin):
    if spin == 0:
        return "flat"
    return f"{'right' if spin > 0 else 'left'} {abs(spin):.0%}"


def rumble_interval(time_to_paddle):
    """Seconds between approach-rumble ticks, or None for no rumble yet."""
    if time_to_paddle is None or time_to_paddle > RUMBLE_START:
        return None
    return RUMBLE_FAST + (RUMBLE_SLOW - RUMBLE_FAST) * time_to_paddle / RUMBLE_START


def note_color(note):
    return BAD if note.startswith("Miss") else GOOD


def banner(img, lines):
    cx, cy, cw, ch = COURT
    overlay = img.copy()
    cv2.rectangle(overlay, (cx + 40, cy + ch // 2 - 110), (cx + cw - 40, cy + ch // 2 + 110), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.65, img, 0.35, 0, img)
    for i, (s, scale) in enumerate(lines):
        text(img, s, (cx + cw // 2, cy + ch // 2 - 70 + i * 50), scale, TEXT, 2 if scale > 0.8 else 1, center=True)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--paddle", choices=["lego", "keyboard"], default="lego")
    p.add_argument("--card-color", default="orange", help="Double Motor connection card color")
    p.add_argument("--card-serial", default="0994", help="Double Motor connection card serial")
    p.add_argument("--haptic-motor", choices=["left", "right"], default="left",
                   help="which Double Motor output has the off-center weight")
    p.add_argument("--no-haptics", action="store_true")
    p.add_argument("--no-rumble", action="store_true", help="keep contact/miss haptics, drop the approach rumble")
    p.add_argument("--twist-axis", choices=["x", "y", "z"], default="x",
                   help="gyro axis along the paddle handle (check_paddle.py finds it)")
    p.add_argument("--twist-sign", type=int, choices=[1, -1], default=1,
                   help="-1 if twisting right curves the ball left")
    p.add_argument("--hand", choices=["right", "left"], default="right", help="your paddle hand")
    p.add_argument("--reach", type=float, default=0.7,
                   help="fraction of the camera width that spans the whole court")
    p.add_argument("--camera", type=int, default=None)
    p.add_argument("--k", type=float, default=6.0, help="swing threshold = rest mean + k * rest std")
    p.add_argument("--min-threshold", type=float, default=50.0, help="swing threshold floor (raw gyro units)")
    p.add_argument("--topic", default=TOPIC)
    p.add_argument("--no-mqtt", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    if args.paddle == "lego":
        paddle = LegoPaddle(args.card_serial, args.card_color, args.haptic_motor,
                            haptics=not args.no_haptics)
    else:
        paddle = KeyboardPaddle()
    paddle.start()

    cap = open_camera(args.camera)
    pose = PoseTracker(hand=args.hand, reach=args.reach)
    tags = TagReader()
    detector = SwingDetector(k=args.k, min_threshold=args.min_threshold)
    board = Scoreboard(args.topic, enabled=not args.no_mqtt)
    game = Game(LEVELS[1])

    state = "WAIT_TAG"
    state_t = time.monotonic()
    last_t = state_t
    swing_flash = -1.0
    last_tick = -1.0
    twist_i = "xyz".index(args.twist_axis)
    note, note_t = "", 0.0
    trail = deque(maxlen=10)

    def go(new_state, now):
        nonlocal state, state_t
        state, state_t = new_state, now
        if new_state == "CALIBRATE":
            detector.start_calibration()

    def pick_level(tag_id, now):
        game.set_level(LEVELS[tag_id])
        trail.clear()
        go("CALIBRATE" if detector.threshold is None else "COUNTDOWN", now)

    cv2.namedWindow("Ping-pong", cv2.WINDOW_AUTOSIZE)
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera stopped delivering frames.", file=sys.stderr)
                break
            now = time.monotonic()
            dt = min(now - last_t, 0.05)    # a slow frame shouldn't teleport the ball
            last_t = now

            # --- sensors -------------------------------------------------------
            paddle_x = pose.update(frame)
            tag = tags.update(frame, now)
            for t, mag, gyro in paddle.poll():
                if state == "CALIBRATE":
                    detector.add_calibration(mag)
                elif (swing := detector.update(t, mag, args.twist_sign * gyro[twist_i])) is not None:
                    swing_flash = now
                    if state == "RALLY":
                        game.add_swing(swing)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            paddle.on_key(key)
            if key in (ord("1"), ord("2"), ord("3")):
                tag = key - ord("0")
            elif key == ord("p"):
                tag = PAUSE_TAG
            elif key == ord("c"):
                go("CALIBRATE", now)

            # --- AprilTags: level select / pause ---------------------------------
            if tag in LEVELS:
                pick_level(tag, now)
            elif tag == PAUSE_TAG and state in ("RALLY", "PAUSED"):
                go("PAUSED" if state == "RALLY" else "RALLY", now)

            # --- state machine ------------------------------------------------------
            if state == "CALIBRATE" and now - state_t >= CALIBRATE_S:
                thr = detector.finish_calibration()
                print(f"Swing threshold: {thr:.1f} (raw gyro units)")
                go("COUNTDOWN", now)
            elif state == "COUNTDOWN" and now - state_t >= COUNTDOWN_S:
                game.serve(now)
                paddle.haptic("start")
                board.publish(game.record)
                go("RALLY", now)
            elif state == "RALLY":
                for event in game.step(dt, now, paddle_x, paddle_x is not None):
                    if event[0] == "hit":
                        paddle.haptic("sweet" if event[1]["sweet"] else "hit")
                        board.publish(game.record)
                        note = "Sweet spot!" if event[1]["sweet"] else "Hit!"
                        if event[1]["spin"]:
                            note += f"  curve {spin_label(event[1]['spin'])}"
                        note_t = now
                    elif event[0] == "miss":
                        paddle.haptic("miss")
                        board.publish(game.record)
                        note, note_t = f"Miss: {event[1]}", now
                        trail.clear()
                if game.in_play:
                    trail.append((game.x, game.y))
                gap = rumble_interval(game.time_to_paddle())
                if not args.no_rumble and gap is not None and now - last_tick >= gap:
                    paddle.haptic("tick")
                    last_tick = now

            # --- draw -----------------------------------------------------------
            img = np.full((WIN_H, WIN_W, 3), BG, np.uint8)
            draw_court(img, game, paddle_x, swing_flash, trail, now)
            draw_preview(img, frame, pose, tags, now)
            draw_hud(img, game, state, paddle, detector, board, note if now - note_t < 1.5 else "")
            if state == "WAIT_TAG":
                banner(img, [("Show an AprilTag to start", 0.9),
                             ("tag 1 = easy   tag 2 = medium   tag 3 = hard", 0.6),
                             ("tag 0 = pause", 0.55)])
            elif state == "CALIBRATE":
                left = max(0.0, CALIBRATE_S - (now - state_t))
                banner(img, [("Hold the paddle still", 0.9), (f"calibrating swing sensor... {left:.1f}", 0.6)])
            elif state == "COUNTDOWN":
                n = int(COUNTDOWN_S - (now - state_t)) + 1
                banner(img, [(f"{game.level.name}", 0.9), (f"{n}", 1.6),
                             ("move your hand to move the paddle, swing to hit", 0.55)])
            elif state == "PAUSED":
                banner(img, [("Paused", 1.0), ("show tag 0 (or p) to resume", 0.6)])
            cv2.imshow("Ping-pong", img)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"Record streak: {game.record}")
        cap.release()
        cv2.destroyAllWindows()
        pose.close()
        board.close()
        paddle.stop()


if __name__ == "__main__":
    main()
