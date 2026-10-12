#!/usr/bin/env python3
"""
Virtual ping-pong against a wall, with a LEGO Double Motor as the paddle.

  pose (MediaPipe)  where your paddle hand is  -> paddle position on the court
  IMU (Double Motor) whether you're swinging   -> a hit needs a swing in time
  AprilTag           tag 1/2/3 = easy/medium/hard, starts the game; tag 0 = pause
  MQTT               record streak, as a float, to ME193/Rogers/Sam on every hit/miss
  spin               twist the paddle as you swing to curve the ball
  haptics            light rumble that builds as the ball approaches, a pulse
                     on contact (longer on the sweet spot), a wobble on a miss,
                     and a big wobble to start and end the game

Run (from Terminal.app/iTerm2 -- the VS Code terminal loses camera permission):
  venv/bin/python pong.py                              # LEGO paddle, card orange 0994
  (run check_paddle.py first: it saves paddle_calib.json with the twist axis)
  venv/bin/python pong.py --paddle keyboard --no-mqtt  # no hardware: space/z/x = swing

Keys: q/Esc quit, c recalibrate, p pause, 1/2/3 pick a level without a tag.
"""

import argparse
import json
import math
import os
import sys
import time
from collections import deque

import cv2

from game import LEVELS, Game
from paddles import KeyboardPaddle, LegoPaddle
from swing import SwingDetector
from ui import Renderer
from vision import PoseTracker, TagReader, VisionWorker, open_camera

TOPIC = "ME193/Rogers/Sam"
CALIB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paddle_calib.json")
CALIBRATE_S = 2.0
COUNTDOWN_S = 3.0

# Approach rumble: once the ball is RUMBLE_START seconds away, light ticks
# start every RUMBLE_SLOW s and speed up to every RUMBLE_FAST s at contact.
# Each tick keeps the motor busy ~60 ms (+~60 ms Bluetooth), hence the floor.
RUMBLE_START = 1.0
RUMBLE_SLOW, RUMBLE_FAST = 0.45, 0.17
PAUSE_TAG = 0

FPS = 60                # drawing rate; the camera + pose run at their own ~30
PADDLE_EASE = 0.045     # s; the drawn paddle glides toward each new pose reading


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
        self.ok = False
        if not enabled:
            return
        try:
            from mqttlib import MQTTClient
            self.client = MQTTClient()
            self.client.connect(timeout=5)
            self.status = topic
            self.ok = True
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
            self.ok = False

    def close(self):
        if self.client is not None:
            self.client.disconnect()


def spin_label(spin):
    if spin == 0:
        return "flat"
    return f"{'right' if spin > 0 else 'left'} {abs(spin):.0%}"


def rumble_interval(time_to_paddle):
    """Seconds between approach-rumble ticks, or None for no rumble yet."""
    if time_to_paddle is None or time_to_paddle > RUMBLE_START:
        return None
    return RUMBLE_FAST + (RUMBLE_SLOW - RUMBLE_FAST) * time_to_paddle / RUMBLE_START


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
    p.add_argument("--twist-axis", choices=["x", "y", "z"], default=None,
                   help="override paddle_calib.json with a single gyro axis")
    p.add_argument("--twist-sign", type=int, choices=[1, -1], default=1,
                   help="with --twist-axis: -1 if twisting right curves the ball left")
    p.add_argument("--hand", choices=["right", "left"], default="right", help="your paddle hand")
    p.add_argument("--reach", type=float, default=0.7,
                   help="fraction of the camera width that spans the whole court")
    p.add_argument("--camera", type=int, default=None)
    p.add_argument("--k", type=float, default=6.0, help="swing threshold = rest mean + k * rest std")
    p.add_argument("--min-threshold", type=float, default=50.0, help="swing threshold floor (raw gyro units)")
    p.add_argument("--topic", default=TOPIC)
    p.add_argument("--no-mqtt", action="store_true")
    return p.parse_args()


def load_twist_axis(args):
    """The gyro direction that means "twist right": from --twist-axis if
    given, else paddle_calib.json (written by check_paddle.py), else +x."""
    if args.twist_axis is not None:
        vec = [0.0, 0.0, 0.0]
        vec["xyz".index(args.twist_axis)] = float(args.twist_sign)
        return vec
    if args.paddle == "lego" and os.path.exists(CALIB_PATH):
        with open(CALIB_PATH) as f:
            calib = json.load(f)
        if "twist_axis" in calib:
            print(f"Twist axis {calib['twist_axis']} from {os.path.basename(CALIB_PATH)}")
            return calib["twist_axis"]
    if args.paddle == "lego":
        print("No paddle_calib.json: spin uses gyro x. Run check_paddle.py to calibrate.")
    return [1.0, 0.0, 0.0]


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
    vision = VisionWorker(cap, pose, tags)
    vision.start()
    detector = SwingDetector(k=args.k, min_threshold=args.min_threshold)
    board = Scoreboard(args.topic, enabled=not args.no_mqtt)
    game = Game(LEVELS[1])
    ui = Renderer()

    state = "WAIT_TAG"
    state_t = time.monotonic()
    last_t = state_t
    swing_flash = -10.0
    last_tick = -1.0
    twist_vec = load_twist_axis(args)
    trail = deque(maxlen=18)
    paddle_draw_x = 0.5             # eased paddle position (also what the hit rule uses)
    key = 255

    def go(new_state, now):
        nonlocal state, state_t
        state, state_t = new_state, now
        if new_state == "CALIBRATE":
            detector.start_calibration()

    def pick_level(tag_id, now):
        if state in ("RALLY", "PAUSED"):
            paddle.haptic("end")            # switching level ends this game
        game.set_level(LEVELS[tag_id])
        trail.clear()
        go("CALIBRATE" if detector.threshold is None else "COUNTDOWN", now)

    cv2.namedWindow("Ping-pong", cv2.WINDOW_AUTOSIZE)
    try:
        while True:
            now = time.monotonic()
            dt = min(now - last_t, 0.05)    # a hiccup shouldn't teleport the ball
            last_t = now
            if vision.error:
                print(vision.error, file=sys.stderr)
                break

            # --- sensors -------------------------------------------------------
            frame, target_x, wrist_px, visible, tag_events = vision.snapshot()
            if target_x is not None:
                paddle_draw_x += (target_x - paddle_draw_x) * (1 - math.exp(-dt / PADDLE_EASE))
            paddle_x = paddle_draw_x if target_x is not None else None
            tag = tag_events[-1] if tag_events else None
            for t, mag, gyro in paddle.poll():
                if state == "CALIBRATE":
                    detector.add_calibration(mag)
                elif (swing := detector.update(t, mag, sum(a * b for a, b in zip(gyro, twist_vec)))) is not None:
                    swing_flash = now
                    if state == "RALLY":
                        game.add_swing(swing)

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
                        ui.add_hit(game.x, event[1]["sweet"], event[1]["spin"], now)
                    elif event[0] == "miss":
                        paddle.haptic("miss")
                        board.publish(game.record)
                        ui.add_miss(event[1], now)
                        trail.clear()
                if game.in_play:
                    trail.append((game.x, min(game.y, 1.0)))
                tta = game.time_to_paddle()
                gap = rumble_interval(tta)
                if not args.no_rumble and gap is not None and now - last_tick >= gap:
                    paddle.haptic("tick", strength=1.0 - tta / RUMBLE_START)
                    last_tick = now

            # --- draw -----------------------------------------------------------
            img = ui.draw({
                "now": now, "state": state, "state_t": state_t,
                "calibrate_s": CALIBRATE_S, "countdown_s": COUNTDOWN_S,
                "game": game, "trail": list(trail),
                "paddle_x": paddle_draw_x, "paddle_seen": paddle_x is not None,
                "swing_age": now - swing_flash,
                "frame": frame, "wrist_px": wrist_px, "tags_visible": visible,
                "tag_progress": tags.progress(now), "pose_ok": target_x is not None,
                "paddle_name": paddle.name, "imu_rate": getattr(paddle, "sample_rate", 0.0),
                "threshold": "–" if detector.threshold is None else f"{detector.threshold:.0f}",
                "mqtt_status": board.status, "mqtt_ok": board.ok,
            })
            cv2.imshow("Ping-pong", img)
            key = cv2.waitKey(1) & 0xFF
            spare = 1 / FPS - (time.monotonic() - now)
            if spare > 0:
                time.sleep(spare)
    except KeyboardInterrupt:
        pass
    finally:
        print(f"Record streak: {game.record}  (sweet-spot streak record: {game.sweet_record})")
        if state in ("RALLY", "PAUSED"):
            paddle.haptic("end")            # stop() waits for it to play
        vision.stop()
        cap.release()
        cv2.destroyAllWindows()
        pose.close()
        board.close()
        paddle.stop()


if __name__ == "__main__":
    main()
