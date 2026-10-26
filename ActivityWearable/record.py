#!/usr/bin/env python3
"""Guided recording session for the activity wearable (laptop side).

Walks one person through the recording protocol (common.PROTOCOL): fit check,
orientation check, then each timed activity. For each step it shows what to
do, starts the recording on the board, counts down, shows the time left,
live motion and on-screen cues (no sound), and sanity-checks the result.

    python ActivityWearable/record.py --person SL
    python ActivityWearable/record.py --person SL --start 6    # resume at step 6

Keys: Enter = start / next, r = redo, s = skip, b = back, x = abort a recording,
q = quit. The board keeps its own copy of every session (pull_data.py copies
them over); this script also saves what it received over MQTT in data/live/
and logs every session in data/session_log.csv (redone ones as "discarded").
"""
import argparse
import csv
import json
import os
import queue
import select
import sys
import termios
import time
import tty
from collections import deque
from datetime import datetime

import paho.mqtt.client as mqtt

from common import BROKER, LIVE_DIR, PORT, PROTOCOL, RATE_HZ, SESSION_LOG, TOPIC

COUNTDOWN_S = 5

BOLD, DIM, RESET = "\x1b[1m", "\x1b[2m", "\x1b[0m"
GREEN, RED, YELLOW, CYAN = "\x1b[32m", "\x1b[31m", "\x1b[33m", "\x1b[36m"
OK, BAD, WARN = f"{GREEN}✓{RESET}", f"{RED}✗{RESET}", f"{YELLOW}!{RESET}"


# ---- MQTT link --------------------------------------------------------------
class Board:
    def __init__(self):
        self.status = {}
        self.status_at = 0.0
        self.events = queue.Queue()
        self.samples = deque(maxlen=RATE_HZ * 5)   # (seq, ax, ay, az, gx, gy, gz)
        self.capture = None                        # list while a session is recording
        self.connected = False
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wear-laptop-{os.getpid()}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = lambda *a: setattr(self, "connected", False)
        self.client.on_message = self._on_message
        self.client.connect_async(BROKER, PORT, keepalive=30)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = True
        client.subscribe(TOPIC + "/status")
        client.subscribe(TOPIC + "/event")
        client.subscribe(TOPIC + "/imu")

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except ValueError:
            return
        kind = msg.topic.rsplit("/", 1)[-1]
        if kind == "status":
            self.status, self.status_at = data, time.time()
        elif kind == "event":
            if data.get("type") == "recording":
                self.capture = []
            self.events.put(data)
        elif kind == "imu":
            for s in data.get("s", []):
                self.samples.append(s)
                if self.capture is not None:
                    self.capture.append(s)

    def online(self):
        return time.time() - self.status_at < 3

    def send(self, payload):
        self.client.publish(TOPIC + "/cmd", json.dumps(payload))

    def drain_events(self):
        out = []
        while not self.events.empty():
            out.append(self.events.get())
        return out


# ---- Keys, screen -----------------------------------------------------------
class Keys:
    """Single keypresses without Enter (cbreak mode), restored on exit."""
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        self.old = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        sys.stdout.write("\x1b[?1049h\x1b[?25l")   # alternate screen, hide cursor
        return self

    def __exit__(self, *exc):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()

    def get(self, timeout=0.1):
        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if not ready:
            return None
        ch = sys.stdin.read(1)
        return "enter" if ch in ("\n", "\r") else ch.lower()


def render(lines):
    sys.stdout.write("\x1b[H" + "".join(line + "\x1b[K\n" for line in lines) + "\x1b[J")
    sys.stdout.flush()


FONT = {   # 5x7, for the big countdown and labels
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    " ": ["00000"] * 7,
}


def big(text, color=BOLD):
    rows = []
    for y in range(7):
        row = "  ".join("".join("██" if b == "1" else "  " for b in FONT.get(ch, FONT[" "])[y])
                        for ch in text.upper())
        rows.append(f"  {color}{row}{RESET}")
    return rows


def bar(fraction, width=40, color=CYAN):
    n = int(round(width * min(max(fraction, 0.0), 1.0)))
    return f"{color}{'█' * n}{RESET}{DIM}{'░' * (width - n)}{RESET}"


# ---- Live numbers and checks ------------------------------------------------
def recent(board, seconds):
    n = int(seconds * RATE_HZ)
    return list(board.samples)[-n:]


def motion(board):
    s = recent(board, 0.5)
    if not s:
        return None
    mags = [(r[1] ** 2 + r[2] ** 2 + r[3] ** 2) ** 0.5 for r in s]
    gyro = [(r[4] ** 2 + r[5] ** 2 + r[6] ** 2) ** 0.5 for r in s]
    return max(mags), sum(gyro) / len(gyro)


def orientation(board):
    """Mean accel over the last second, plus (ok, text) checks."""
    s = recent(board, 1.0)
    if len(s) < 50:
        return None, [(False, "Waiting for live data from the wearable...")]
    ax, ay, az = (sum(r[i] for r in s) / len(s) for i in (1, 2, 3))
    mags = [(r[1] ** 2 + r[2] ** 2 + r[3] ** 2) ** 0.5 for r in s]
    mean = sum(mags) / len(mags)
    jitter = (sum((m - mean) ** 2 for m in mags) / len(mags)) ** 0.5
    checks = []
    if jitter > 0.05:
        checks.append((False, "You're moving: stand still for a second."))
    if ay > 0.85:
        checks.append((True, f"Y = {ay:+.2f} g: +Y points up (USB-C toward the knee)."))
    elif ay < -0.5:
        checks.append((False, f"Y = {ay:+.2f} g: it's upside down. USB-C must point UP to the knee."))
    else:
        checks.append((False, f"Y = {ay:+.2f} g: the shin axis isn't vertical. Are you standing up straight?"))
    checks.append((abs(az) < 0.35, f"Z = {az:+.2f} g: " + (
        "sensor sits flat on the front of the shin." if abs(az) < 0.35 else
        "tilted forward/back. Is it on the FRONT of the shin, sitting flat?")))
    checks.append((abs(ax) < 0.3, f"X = {ax:+.2f} g: " + (
        "not rotated around the leg." if abs(ax) < 0.3 else
        "rotated around the leg. Turn the sleeve so the pocket faces straight forward.")))
    return (ax, ay, az), checks


def quality(step, st):
    """Rough sanity checks on a saved session (not the model!)."""
    out = []
    expected = st.get("expected") or step.seconds * RATE_HZ
    missing = expected - st.get("rows", 0)
    if missing > 0.02 * expected or st.get("gaps", 0) > 0.01 * expected:
        out.append((False, f"Missing data: {st.get('rows', 0)}/{expected:.0f} samples, "
                           f"{st.get('gaps', 0)} gaps. Redo it."))
    else:
        out.append((True, f"{st.get('rows', 0)} samples, {st.get('gaps', 0)} gaps."))
    std, peak, gyro = st.get("acc_std_g", 0), st.get("acc_peak_g", 0), st.get("gyro_rms_dps", 0)
    if step.label == "still":
        if std < 0.15:
            out.append((True, f"Motion looks like standing/lying still (std {std:.2f} g)."))
        else:
            out.append((False, f"A lot of motion for 'still' (std {std:.2f} g). Redo if you took steps."))
    elif step.label == "walk":
        # No upper limit on the peak: heel strikes at the shin reach 7-9 g for a
        # tall walker (Sam, 2026-10-26), overlapping running. That overlap is a
        # finding for Model 1, not a bad recording.
        if std < 0.12:
            out.append((False, f"Very little motion (std {std:.2f} g). Were you walking?"))
        else:
            out.append((True, f"Looks like walking (std {std:.2f} g, peak {peak:.1f} g)."))
    elif step.label == "run":
        out.append((peak >= 2.5, f"Peak {peak:.1f} g " + ("looks like running." if peak >= 2.5 else
                                                       "is low for running. Run with more bounce?")))
    elif step.label == "bike":
        out.append((gyro >= 60, f"Leg rotation {gyro:.0f} deg/s " + (
            "looks like pedalling." if gyro >= 60 else "is low. Pedal bigger, full circles.")))
    return out


def save_live_copy(board, name, seconds):
    rows = board.capture or []
    board.capture = None
    if not rows:
        return
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    first = rows[0][0]
    with open(LIVE_DIR / f"{name}.csv", "w") as f:
        f.write("t_s,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps\n")
        for r in rows:
            t = (r[0] - first) / RATE_HZ
            if t < seconds:
                f.write(f"{t:.2f}," + ",".join(str(x) for x in r[1:]) + "\n")


def log_session(row):
    SESSION_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not SESSION_LOG.exists()
    with open(SESSION_LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


# ---- Screens ----------------------------------------------------------------
class Recorder:
    def __init__(self, args, board, keys):
        self.args, self.board, self.keys = args, board, keys
        self.recorded = []

    def header(self, i):
        b, st = self.board, self.board.status
        if not b.connected:
            link = f"{RED}○ no connection to the MQTT broker ({BROKER}){RESET}"
        elif b.online():
            imu_ok = st.get("imu") not in (None, "not found")
            link = (f"{GREEN}● wearable online{RESET}  {st.get('rate_hz', 0):.0f} Hz  "
                    f"IMU {st.get('imu') if imu_ok else RED + 'NOT FOUND' + RESET}  "
                    f"drops {st.get('drops', 0)}  sessions on board {st.get('sessions_on_board', 0)}")
        else:
            ago = f"{time.time() - b.status_at:.0f} s ago" if b.status_at else "never"
            link = (f"{RED}○ wearable offline{RESET} (last heard {ago}). Is it on the power bank "
                    f"and is your phone hotspot on?")
        step = PROTOCOL[i]
        return [f"{BOLD}Activity wearable · {self.args.person} · {self.args.leg} leg · "
                f"step {i + 1}/{len(PROTOCOL)}{RESET}", link, "─" * 78,
                f"{BOLD}{CYAN}{step.title}{RESET}" +
                (f"   {DIM}label '{step.label}', {step.seconds:g} s{RESET}" if step.label else ""), ""]

    def run(self):
        i = self.args.start - 1
        while 0 <= i < len(PROTOCOL):
            result = self.step(i)
            if result == "quit":
                return
            i = i - 1 if result == "back" else i + 1
            i = max(i, 0)
        self.done()

    def step(self, i):
        step = PROTOCOL[i]
        while True:
            lines = self.header(i) + [f"  • {h}" for h in step.how] + [""]
            if step.key == "orient":
                _, checks = orientation(self.board)
                lines += [f"  {OK if ok else BAD} {text}" for ok, text in checks] + [""]
            if step.label:
                lines.append(f"{BOLD}Enter{RESET} start ({COUNTDOWN_S} s countdown)   "
                             f"{DIM}s skip · b back · q quit{RESET}")
                if not self.board.online():
                    lines.append(f"{RED}The wearable is offline: it can't record yet.{RESET}")
            else:
                lines.append(f"{BOLD}Enter{RESET} continue   {DIM}b back · q quit{RESET}")
            render(lines)
            key = self.keys.get(0.2)
            if key == "q":
                return "quit"
            if key == "b":
                return "back"
            if key == "s" and step.label:
                return "next"
            if key == "enter":
                if not step.label:
                    return "next"
                if self.board.online():
                    result = self.record(i)
                    if result != "redo":
                        return result

    def record(self, i):
        step, b = PROTOCOL[i], self.board
        name = f"{self.args.person}_{step.key}_{datetime.now():%Y%m%d-%H%M%S}"
        b.drain_events()
        b.capture = None
        b.send({"cmd": "record", "session": name, "person": self.args.person, "leg": self.args.leg,
                "activity": step.key, "label": step.label, "seconds": step.seconds,
                "countdown": COUNTDOWN_S, "laptop_time": datetime.now().isoformat(timespec="seconds")})

        # Countdown: the board runs its own; this mirrors it.
        t0, t_rec = time.time(), None
        while t_rec is None:
            left = COUNTDOWN_S - (time.time() - t0)
            n = max(1, int(left) + 1)
            render(self.header(i) + [f"  Get into position: {step.how[0]}", ""] +
                   big(str(n) if left > 0 else "GO", YELLOW) + ["", f"{DIM}x abort{RESET}"])
            for ev in b.drain_events():
                if ev.get("type") == "recording" and ev.get("session") == name:
                    t_rec = time.time()
                elif ev.get("type") == "error":
                    return self.problem(i, f"The board refused: {ev.get('message')}")
            if self.keys.get(0.05) == "x":
                b.send({"cmd": "stop"})
                return "redo"
            if left < -4:
                b.send({"cmd": "stop"})
                return self.problem(i, "The board never started recording. Is it still online?")

        stats = None
        while stats is None:
            elapsed = time.time() - t_rec
            left = step.seconds - elapsed
            m = motion(b)
            live = (f"  peak |a| {m[0]:5.2f} g {bar(m[0] / 8, 25, YELLOW)}   gyro {m[1]:6.0f} °/s"
                    if m else f"  {YELLOW}no live data (Wi-Fi?), the board is still recording{RESET}")
            current = [text for t, text in step.cues if t <= elapsed]
            render(self.header(i) + big(step.label, GREEN) + [
                "", f"  {BOLD}{YELLOW if left <= 10 else ''}{max(left, 0):4.0f} s left{RESET}  "
                    f"{bar(elapsed / step.seconds)}",
                f"  {step.how[0]}" if not current else f"  {BOLD}{YELLOW}{current[-1]}{RESET}",
                "", live, "", f"{DIM}x abort{RESET}"])
            for ev in b.drain_events():
                if ev.get("session") == name and ev.get("type") in ("saved", "aborted"):
                    stats = ev
            key = self.keys.get(0.1)
            if key == "x":
                b.send({"cmd": "stop"})
            if left < -8 and stats is None:
                return self.problem(i, "The recording should have finished but the board didn't "
                                       "confirm it. Its own copy is probably fine; check pull_data.py.")

        save_live_copy(b, name, step.seconds)
        aborted = stats.get("type") == "aborted"
        checks = [] if aborted else quality(step, stats)
        while True:
            lines = self.header(i) + ([f"  {YELLOW}Aborted: not saved as a good session.{RESET}"] if aborted else
                                      [f"  Saved {stats.get('file')}", ""] +
                                      [f"  {OK if ok else WARN} {text}" for ok, text in checks] +
                                      ["", f"  {DIM}(rough checks, not the model){RESET}"])
            lines += ["", f"{BOLD}Enter{RESET} keep and go on   {BOLD}r{RESET} redo   {DIM}q quit{RESET}"]
            render(lines)
            key = self.keys.get(0.2)
            if key in ("enter", "r", "q"):
                keep = key != "r" and not aborted
                log_session({"session": name, "person": self.args.person, "leg": self.args.leg,
                             "activity": step.key, "label": step.label, "seconds": step.seconds,
                             "rows": stats.get("rows", 0), "gaps": stats.get("gaps", 0),
                             "checks_ok": all(ok for ok, _ in checks),
                             "status": "kept" if keep else "discarded",
                             "laptop_time": datetime.now().isoformat(timespec="seconds")})
                if keep:
                    self.recorded.append(step.key)
                return "redo" if key == "r" or (aborted and key == "enter") else (
                    "quit" if key == "q" else "next")

    def problem(self, i, message):
        while True:
            render(self.header(i) + [f"  {RED}{message}{RESET}", "",
                                     f"{BOLD}Enter{RESET} back to this step   {DIM}q quit{RESET}"])
            key = self.keys.get(0.2)
            if key == "enter":
                return "redo"
            if key == "q":
                return "quit"

    def done(self):
        todo = [s.key for s in PROTOCOL if s.label and s.key not in self.recorded]
        while True:
            render([f"{BOLD}Done with {self.args.person}.{RESET}", "",
                    f"  Kept this run: {', '.join(self.recorded) or 'nothing'}",
                    f"  Not recorded:  {', '.join(todo) or 'nothing'}", "",
                    "  Next: copy the sessions to the laptop over Wi-Fi (no need to unplug; the",
                    "  board keeps them on its storage even if it loses power):",
                    f"    {BOLD}UNOQ_HOST=<board ip> python ActivityWearable/pull_data.py{RESET}", "",
                    f"{DIM}q quit{RESET}"])
            if self.keys.get(0.3) in ("q", "enter"):
                return


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--person", required=True, help="initials or an ID, never a full name (e.g. SL)")
    p.add_argument("--leg", default="right")
    p.add_argument("--start", type=int, default=1, help=f"step to start at, 1-{len(PROTOCOL)}")
    args = p.parse_args()
    args.person = "".join(c for c in args.person if c.isalnum()).upper() or "X"
    if not sys.stdin.isatty():
        sys.exit("Run this in a terminal (it reads single keypresses).")

    board = Board()
    try:
        with Keys() as keys:
            Recorder(args, board, keys).run()
    except KeyboardInterrupt:
        pass
    finally:
        if board.status.get("state") in ("countdown", "recording"):
            board.send({"cmd": "stop"})
            time.sleep(0.3)
        board.client.loop_stop()
    print(f"Session log: {SESSION_LOG}")


if __name__ == "__main__":
    main()
