"""UNO Q - Linux side of the activity wearable.

Drains the sketch's 100 Hz IMU samples, takes in the phone's (an iPhone in
the left pocket running ActivityWearable/phone/, over MQTT), and does two jobs
at once:
- Live: every 0.5 s it classifies the last 2 s with both models (models.json,
  trained by ActivityWearable/train.py) and publishes the answers for the
  laptop dashboard. The LED matrix shows Model 1's letter on the left and
  Model 2's on the right (S still, W walk, R run, B bike). It also counts
  steps with the neural net (steps_model.json, trained in PyTorch by
  ActivityWearable/train_steps.py, run here with numpy by steps.py).
- Recording: saves sessions as CSV in data/ (this app's folder on the board,
  mounted at /app) for ActivityWearable/record.py, with the countdown and
  progress on the matrix while it records. The phone's samples go in a
  second file, <session>_phone.csv, on the same clock.

The laptop starts a session with a command on ME193/Sam/wear/cmd. The board
then runs the countdown and the timed recording itself, so a session still
ends cleanly if Wi-Fi drops halfway down the hall.

Topics (must match ActivityWearable/common.py):
  .../cmd     laptop -> board  {"cmd": "record", ...} / {"cmd": "stop"} / {"cmd": "ping"}
                               / {"cmd": "model2", "kind": "tree" | "forest" | "knn"}
  .../status  board -> laptop  twice a second
  .../event   board -> laptop  recording / saved / aborted / error
  .../imu     board -> laptop  live samples, 10 messages a second (every 4th sample when not recording)
  .../live    board -> laptop  both models' answers, twice a second, plus the step count,
                               the current activity bout (duration, steps) and the last 6 bouts
  .../bout    board -> laptop  a bout that just ended
  .../phone   phone -> board   {"id": page, "n": batch, "s": [[phone ms, ax, ay, az, gx, gy, gz], ...]}
"""
import json
import os
import queue
import re
import threading
import time
from collections import deque
from datetime import datetime

import numpy as np
import paho.mqtt.client as mqtt
from arduino.app_utils import App, Bridge, Frame

import classify
import features as F
import steps as S

BROKER = "broker.emqx.io"   # test.mosquitto.org:1883 is unreachable from Tufts networks; broker.hivemq.com stalled ~8 s on 3 of 8 connects (2026-10-26)
PORT = 1883
TOPIC = "ME193/Sam/wear"
DATA_DIR = "/app/data"

RATE_HZ = 100
ACC_LSB_PER_G = 2048.0      # +-16 g
GYRO_LSB_PER_DPS = 16.4     # +-2000 deg/s
MAX_BATCH = 7               # must match the sketch
LIVE_EVERY = 0.1            # seconds between live-sample messages
STATUS_EVERY = 0.5
SAVED_SHOW_S = 3.0          # how long the matrix shows the check mark
SMOOTH = 3                  # live answer = most common of the last 3 (1.5 s), so it doesn't flicker
IDLE_EVERY_NTH = 4          # raw samples on .../imu when not recording: every 4th (25 Hz) is plenty for the display
ECHO_TIMEOUT_S = 8.0        # no echo of our own status through the broker for this long -> reconnect
BOARD_ID = f"wear-board-{int(time.time())}"

BOUT_CONFIRM = 2                # a new activity must hold for 2 answers (1 s) to start a new bout
RECENT_BOUTS = 6
STEP_RATE_S = 5.0               # the live step rate counts the steps in the last 5 s
PHONE_STALE_S = 1.0             # no phone samples for this long -> the phone is off
PHONE_WINDOW_S = 20.0           # the phone's clock offset is re-estimated over the last 20 s
MODELS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")
STEPS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steps_model.json")

AXES_NOTE = "+Y up the shin (toward the knee), +Z forward out of the shin, +X to the wearer's left"
COLUMNS = "t_s,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps"
PHONE_NOTE = ("iPhone in the left front pocket, in the phone's own axes (any angle); acceleration includes "
              "gravity; t_s is on the board's sample clock (estimated, see main.py Phone)")
PHONE_COLUMNS = COLUMNS + ",phone_ms"

# ---- MQTT -------------------------------------------------------------------
commands = queue.Queue()
phone_msgs = queue.Queue()      # (arrival time, message) from the phone


def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(TOPIC + "/cmd", qos=1)
    client.subscribe(TOPIC + "/status")   # to hear our own status come back (mqtt_watchdog)
    client.subscribe(TOPIC + "/phone")
    print(f"MQTT connected ({reason_code}), listening on {TOPIC}/cmd", flush=True)


last_echo = time.time()     # last time our own status came back through the broker
last_kick = 0.0
kicks = 0                   # reconnects in a row without an echo, for the backoff
restarting = threading.Event()


def on_message(client, userdata, msg):
    global last_echo
    try:
        data = json.loads(msg.payload)
    except ValueError:
        print("ignored a message that isn't JSON:", msg.payload[:80], flush=True)
        return
    if msg.topic.endswith("/status"):
        if data.get("board") == BOARD_ID:
            last_echo = time.time()
    elif msg.topic.endswith("/phone"):
        phone_msgs.put((time.time(), data))
    else:
        commands.put(data)


def start_mqtt():
    client.connect_async(BROKER, PORT, keepalive=15)   # retries in the background until Wi-Fi is up
    client.loop_start()


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=BOARD_ID)
client.on_connect = on_connect
client.on_message = on_message
client.reconnect_delay_set(min_delay=1, max_delay=5)
start_mqtt()


def mqtt_watchdog(now):
    """A Wi-Fi drop (e.g. switching access points down the hall) can leave the
    connection open but dead, with paho still queueing into it. Our own status
    echoing back through the broker proves the whole path works; if it stops,
    start the connection over, waiting longer each time (8, 16, 32 s) so a slow
    reconnect gets to finish."""
    global last_kick, kicks
    if now - last_echo < ECHO_TIMEOUT_S:
        kicks = 0
        return
    if restarting.is_set() or now - last_kick < ECHO_TIMEOUT_S * min(2 ** kicks, 4):
        return
    print(f"MQTT: no echo for {now - last_echo:.0f} s, reconnecting", flush=True)
    last_kick, kicks = now, kicks + 1
    restarting.set()
    threading.Thread(target=restart_mqtt, daemon=True).start()


def restart_mqtt():
    """In its own thread: loop_stop() waits for paho's network thread, which can
    sit in a connect or DNS lookup for many seconds while Wi-Fi is gone. Done on
    the main loop, that stopped sampling (1757 samples lost mid-walk, 2026-11-02)."""
    try:
        client.disconnect()
    except Exception:
        pass
    try:
        client.loop_stop()
    except Exception:
        pass
    start_mqtt()
    restarting.clear()


def publish(sub, payload, qos=0):
    client.publish(f"{TOPIC}/{sub}", json.dumps(payload), qos=qos)


# ---- LED matrix -------------------------------------------------------------
GLYPHS = {   # 5 wide x 7 tall
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
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
}
CHECK = ["0000000000000", "0000000000011", "0000000000110", "0000000001100",
         "1100000011000", "0110000110000", "0011001100000", "0001111000000"]
LABEL_LETTER = {"still": "S", "walk": "W", "run": "R", "bike": "B", "mixed": "M"}
BRIGHT = 7


def text_frame(text, progress=None):
    """Characters centred in rows 0-6; optional progress bar (0-1) on row 7."""
    arr = np.zeros((8, 13), dtype=np.uint8)
    width = len(text) * 6 - 1
    x0 = (13 - width) // 2
    for i, ch in enumerate(text):
        for y, row in enumerate(GLYPHS.get(ch, GLYPHS["?"])):
            for dx, bit in enumerate(row):
                if bit == "1":
                    arr[y, x0 + i * 6 + dx] = BRIGHT
    if progress is not None:
        arr[7, :int(round(13 * min(max(progress, 0.0), 1.0)))] = 3
    return arr


def rows_frame(rows):
    return np.array([[BRIGHT if c == "1" else 0 for c in row] for row in rows], dtype=np.uint8)


last_frame = None


def show(arr):
    global last_frame
    data = Frame(arr).to_board_bytes()
    if data == last_frame:
        return
    try:
        Bridge.call("draw", data)
        last_frame = data
    except Exception as e:
        print("matrix draw failed:", e, flush=True)


# ---- Sessions ---------------------------------------------------------------
def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(text))[:80]


class Session:
    def __init__(self, cmd):
        self.name = safe_name(cmd.get("session") or f"session_{datetime.now():%Y%m%d-%H%M%S}")
        self.person = safe_name(cmd.get("person", "unknown"))
        self.leg = safe_name(cmd.get("leg", "right"))
        self.activity = safe_name(cmd.get("activity", "unknown"))
        self.label = safe_name(cmd.get("label", "unknown"))
        self.seconds = float(cmd.get("seconds", 30))
        self.countdown = float(cmd.get("countdown", 5))
        # The board's clock isn't NTP-synced, so the start time comes from the laptop.
        self.started_at = re.sub(r"[^0-9T:.+-]", "", str(cmd.get("laptop_time", "")))[:32]
        self.t_cmd = time.time()
        self.state = "countdown"
        self.file = None
        self.path = None
        self.phone_file = None
        self.phone_rows = 0
        self.first_seq = None
        self.last_seq = None
        self.t_record = None
        self.rows = 0
        self.gaps = 0
        self.drops_at_start = 0
        self.mags = []
        self.gyro_sq = 0.0

    def remaining(self, now):
        if self.state == "countdown":
            return max(0.0, self.countdown - (now - self.t_cmd))
        if self.first_seq is None or self.last_seq is None:
            return self.seconds
        return max(0.0, self.seconds - (self.last_seq - self.first_seq + 1) / RATE_HZ)

    def start_recording(self, drops):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.path = os.path.join(DATA_DIR, self.name + ".csv")
        self.file = open(self.path, "w")
        self.file.write(f"# person={self.person} leg={self.leg} activity={self.activity} label={self.label} "
                        f"rate_hz={RATE_HZ} accel_range_g=16 gyro_range_dps=2000 seconds={self.seconds:g} "
                        f"start={self.started_at or 'unknown'}\n")
        self.file.write(f"# axes: {AXES_NOTE}\n")
        self.file.write(COLUMNS + "\n")
        self.phone_file = open(self.path[:-4] + "_phone.csv", "w")
        self.phone_file.write(f"# person={self.person} start={self.started_at or 'unknown'}\n")
        self.phone_file.write(f"# phone: {PHONE_NOTE}\n")
        self.phone_file.write(PHONE_COLUMNS + "\n")
        self.state = "recording"
        self.t_record = time.time()
        self.drops_at_start = drops
        publish("event", {"type": "recording", "session": self.name, "seconds": self.seconds}, qos=1)
        print(f"recording {self.name} ({self.seconds:g} s)", flush=True)

    def add(self, seq, v):
        """Add one sample; returns True once the session has its full length."""
        if self.first_seq is None:
            self.first_seq = seq
        elif seq != self.last_seq + 1:
            self.gaps += seq - self.last_seq - 1
        self.last_seq = seq
        t = (seq - self.first_seq) / RATE_HZ
        if t >= self.seconds:
            return True
        self.file.write(f"{t:.2f},{v[0]:.4f},{v[1]:.4f},{v[2]:.4f},{v[3]:.2f},{v[4]:.2f},{v[5]:.2f}\n")
        self.rows += 1
        self.mags.append((v[0] ** 2 + v[1] ** 2 + v[2] ** 2) ** 0.5)
        self.gyro_sq += v[3] ** 2 + v[4] ** 2 + v[5] ** 2
        return False

    def add_phone(self, seq, v, phone_ms):
        """One phone sample, at its (fractional) seq on the board's clock."""
        if self.first_seq is None:
            return
        t = (seq - self.first_seq) / RATE_HZ
        if 0 <= t < self.seconds:
            self.phone_file.write(f"{t:.3f},{v[0]:.4f},{v[1]:.4f},{v[2]:.4f},{v[3]:.2f},{v[4]:.2f},{v[5]:.2f},"
                                  f"{phone_ms:.1f}\n")
            self.phone_rows += 1

    def stats(self, drops):
        m = np.array(self.mags) if self.mags else np.zeros(1)
        return {"session": self.name, "file": os.path.basename(self.path or ""), "rows": self.rows,
                "first_seq": self.first_seq, "phone_rows": self.phone_rows,
                "expected": int(self.seconds * RATE_HZ), "gaps": self.gaps,
                "drops": drops - self.drops_at_start,
                "acc_mean_g": round(float(m.mean()), 3), "acc_std_g": round(float(m.std()), 3),
                "acc_peak_g": round(float(m.max()), 3),
                "gyro_rms_dps": round((self.gyro_sq / max(self.rows, 1)) ** 0.5, 1)}

    def finish(self, drops, aborted=False):
        stats = self.stats(drops)
        if self.file:
            self.file.write(f"# end rows={self.rows} gaps={self.gaps} drops={stats['drops']} first_seq={self.first_seq}"
                            f"{' ABORTED' if aborted else ''}\n")
            self.file.close()
            self.file = None
        if self.phone_file:
            self.phone_file.close()
            self.phone_file = None
        if aborted and self.path:
            os.replace(self.path, self.path[:-4] + "_aborted.csv")
            if os.path.exists(self.path[:-4] + "_phone.csv"):
                os.replace(self.path[:-4] + "_phone.csv", self.path[:-4] + "_phone_aborted.csv")
            stats["file"] = os.path.basename(self.path[:-4] + "_aborted.csv")
        result = {"type": "aborted" if aborted else "saved", **stats}
        publish("event", result, qos=1)
        print(("aborted " if aborted else "saved ") + json.dumps(stats), flush=True)
        return result


# ---- Phone ------------------------------------------------------------------
class Phone:
    """The iPhone in the left pocket. Its samples come stamped with the phone's
    own clock; this puts them on the board's sample clock (seq).

    For each message, arrival time - phone time = (difference between the two
    clocks) + (how long the message took). The smallest value over the last
    PHONE_WINDOW_S is the clock difference plus the quickest delivery, so a
    sample placed at phone time + that is late by at most the quickest
    delivery (tens of ms). The same happens while recording and live, so the
    network trains on exactly what it sees live.
    """

    def __init__(self):
        self.page = None
        self.diffs = deque()        # (arrival, arrival - phone time of the newest sample in it)
        self.arrivals = deque()     # arrival time of each recent sample, for the rate
        self.newest_seq = None      # the newest sample's seq on the board's clock
        self.last_at = 0.0

    def add(self, arrival, msg, anchor):
        """anchor = (board time, seq) of the newest shin sample. Returns
        [(seq, values, phone ms)] on the board's clock."""
        rows = msg.get("s") or []
        if not rows or anchor is None:
            return []
        if msg.get("id") != self.page:          # the page was reloaded: its clock started over
            self.page = msg.get("id")
            self.diffs.clear()
        self.diffs.append((arrival, arrival - rows[-1][0] / 1000.0))
        while self.diffs and arrival - self.diffs[0][0] > PHONE_WINDOW_S:
            self.diffs.popleft()
        offset = min(d for _, d in self.diffs)
        t_anchor, seq_anchor = anchor
        out = []
        for r in rows:
            if len(r) != 7:
                continue
            seq = seq_anchor + (r[0] / 1000.0 + offset - t_anchor) * RATE_HZ
            out.append((seq, tuple(float(x) for x in r[1:]), float(r[0])))
        self.arrivals.extend([arrival] * len(out))
        self.last_at = arrival
        if out:
            self.newest_seq = out[-1][0]
        return out

    def on(self, now):
        return now - self.last_at < PHONE_STALE_S

    def status(self, now, seq_now):
        while self.arrivals and now - self.arrivals[0] > 2.0:
            self.arrivals.popleft()
        on = self.on(now)
        return {"on": on, "rate_hz": round(len(self.arrivals) / 2.0, 1),
                "behind_ms": round((seq_now - self.newest_seq) * 1000 / RATE_HZ) if on and seq_now is not None else None}


phone = Phone()


# ---- Live classification and step counting ---------------------------------
class Live:
    """Keeps the last 2 s of samples and classifies them every 0.5 s, and
    counts steps with the neural net (StepCounter in steps.py)."""

    def __init__(self):
        self.models = classify.Models(MODELS_PATH) if os.path.exists(MODELS_PATH) else None
        self.kind = self.models.m["model2_default"] if self.models else None
        self.buf = deque(maxlen=F.WINDOW)
        self.last_seq = None
        self.since = 0
        self.hist1, self.hist2 = deque(maxlen=SMOOTH), deque(maxlen=SMOOTH)
        self.latest = None
        self.steps = S.StepCounter(STEPS_PATH) if os.path.exists(STEPS_PATH) else None
        self.step_total = 0                 # since the app started
        self.step_seqs = deque()            # recent steps, for the live rate
        self.bout, self.pending, self.bout_n = None, None, 0
        self.recent_bouts = deque(maxlen=RECENT_BOUTS)
        self.finished = None                # a bout that just ended, for main loop to publish
        print(f"live models: {'loaded, Model 2 = ' + self.kind if self.models else 'models.json missing'}; "
              f"step net: {'loaded' if self.steps else 'steps_model.json missing'}", flush=True)

    def add(self, samples):
        """Feed new samples; returns True if a new answer is due."""
        due = False
        for seq, v in samples:
            if self.last_seq is not None and seq != self.last_seq + 1:   # a gap: start the window over
                self.buf.clear()
                self.since = 0
            self.last_seq = seq
            self.buf.append(v)
            self.since += 1
            if self.steps:
                self.steps.add_shin(seq, v)
            if len(self.buf) == F.WINDOW and self.since >= F.STEP:
                self.since = 0
                due = True
        return due and self.models is not None

    def add_phone(self, seq, v):
        if self.steps:
            self.steps.add_phone(seq, v)

    def count_steps(self, ready):
        """Run the step net on whatever is due (ready = the newest seq whose
        phone data is in, or the newest sample when there's no phone)."""
        if not self.steps:
            return
        new = self.steps.update(ready)
        self.step_total += len(new)
        self.step_seqs.extend(new)
        while self.step_seqs and self.step_seqs[0] < self.last_seq - STEP_RATE_S * RATE_HZ:
            self.step_seqs.popleft()

    def classify(self, now):
        w = np.array(self.buf)
        m1, p1 = self.models.model1(w)
        m2, p2 = self.models.model2(w, self.kind)
        self.hist1.append(m1)
        self.hist2.append(m2)
        f = F.features(w)
        m1cfg = self.models.m["model1"]
        bout = self.update_bout(max(set(self.hist2), key=list(self.hist2).count), now)
        self.latest = {
            "t": now, "seq": self.last_seq,
            "m1": max(set(self.hist1), key=list(self.hist1).count), "m1_raw": m1,
            "m1_direction": m1cfg["direction"], "m1_thresholds": m1cfg["thresholds_g"],
            "m1_peak": round(F.peak(w, m1cfg["direction"]), 3),
            "m2": max(set(self.hist2), key=list(self.hist2).count), "m2_raw": m2, "m2_kind": self.kind,
            "m2_proba": {c: round(float(x), 3) for c, x in zip(self.models.classes, p2)},
            "cadence_hz": round(f["cadence_hz"], 2), "cadence_share": round(f["cadence_share"], 2),
            "acc_y_mean": round(f["acc_y_mean"], 3), "gyro_x_std": round(f["gyro_x_std"], 1),
            "steps_total": self.step_total if self.steps else None,
            "step_rate_spm": round(len(self.step_seqs) * 60 / STEP_RATE_S) if self.steps else None,
            "step_net": self.steps.spec.get("summary") if self.steps else None,
            "phone": phone.status(now, self.last_seq),
            "bout": bout, "recent_bouts": list(self.recent_bouts),
        }
        return self.latest

    def update_bout(self, label, now):
        """A bout = one stretch of the same activity (Model 2's answer). It ends
        when a different answer holds for BOUT_CONFIRM answers in a row, so a
        brief flicker (a turnaround at the end of the hall) doesn't split it.
        Its steps are the ones counted while it lasted (the step net answers
        about 1.3 s late, about as late as the activity answer)."""
        if self.bout is None:
            self.bout = {"id": 0, "label": label, "start": now, "steps0": self.step_total}
        if label == self.bout["label"]:
            self.pending = None
        elif self.pending is None or self.pending["label"] != label:
            self.pending = {"label": label, "t": now, "steps": self.step_total, "count": 1}
        else:
            self.pending["count"] += 1
        if self.pending and self.pending["count"] >= BOUT_CONFIRM:
            done = self.bout_summary(self.pending["t"], self.pending["steps"])
            self.recent_bouts.appendleft(done)
            self.finished = done
            self.bout_n += 1
            self.bout = {"id": self.bout_n, "label": self.pending["label"], "start": self.pending["t"],
                         "steps0": self.pending["steps"]}
            self.pending = None
        return self.bout_summary(now, self.step_total)

    def bout_summary(self, end, steps_now):
        b = self.bout
        return {"id": b["id"], "label": b["label"], "start": round(b["start"], 1),
                "duration_s": round(end - b["start"], 1), "steps": steps_now - b["steps0"]}


live_model = None


# ---- Main loop --------------------------------------------------------------
session = None
recent_sessions = deque(maxlen=20)   # names already started, so a repeated record command is ignored
# The last session's saved/aborted result, repeated in every status message: the
# one-off event can be lost while the laptop's Wi-Fi blips (it's walking too).
last_result = None
imu_state = "?"
drops = errors = 0
live = []                      # samples waiting to go out on .../imu
recent = deque()               # arrival times of recent samples, for the measured rate
last_live = last_status = last_imu_check = 0.0
anchor = None                  # (board time, seq) of the newest sample, to put phone samples on the seq clock
saved_until = 0.0
started = False


def drain():
    """Pull every waiting sample from the sketch: [(seq, (ax, ay, az, gx, gy, gz)), ...]."""
    global drops, errors
    out = []
    for _ in range(40):        # 40 x 7 samples is far more than ever piles up
        first, drops, errors, hexdata = Bridge.call("imu_batch").split(",")
        drops, errors, first = int(drops), int(errors), int(first)
        n = len(hexdata) // 24
        if n:
            raw = np.frombuffer(bytes.fromhex(hexdata), dtype=">i2").reshape(n, 6).astype(float)
            raw[:, :3] /= ACC_LSB_PER_G
            raw[:, 3:] /= GYRO_LSB_PER_DPS
            out.extend((first + i, tuple(raw[i])) for i in range(n))
        if n < MAX_BATCH:
            break
    return out


def handle_command(cmd, now):
    global session, last_result
    kind = cmd.get("cmd")
    if kind == "record":
        # record.py resends the command until it hears back, and QoS 1 can
        # deliver it twice: a repeat of one already started is ignored.
        if safe_name(cmd.get("session") or "") in recent_sessions:
            return
        if session is not None:
            publish("event", {"type": "error", "message": f"busy with {session.name}"}, qos=1)
            return
        session = Session(cmd)
        recent_sessions.append(session.name)
        print(f"countdown for {session.name}", flush=True)
    elif kind == "stop" and session is not None:
        if session.state == "recording":
            last_result = session.finish(drops, aborted=True)
        else:
            last_result = {"type": "aborted", "session": session.name, "rows": 0}
            publish("event", last_result, qos=1)
        session = None
    elif kind == "ping":
        publish_status(now)
    elif kind == "model2" and live_model and live_model.models:
        if cmd.get("kind") in live_model.models.m["model2"]:
            live_model.kind = cmd["kind"]
            live_model.hist2.clear()
            print("Model 2 is now", live_model.kind, flush=True)
        publish_status(now)


def publish_status(now):
    while recent and now - recent[0] > 2.0:
        recent.popleft()
    saved = len([f for f in os.listdir(DATA_DIR) if f.endswith(".csv")]) if os.path.isdir(DATA_DIR) else 0
    publish("status", {
        "board": BOARD_ID, "t": now, "state": session.state if session else "idle",
        "session": session.name if session else None,
        "remaining": round(session.remaining(now), 1) if session else None,
        "imu": imu_state, "rate_hz": round(len(recent) / 2.0, 1),
        "drops": drops, "errors": errors, "sessions_on_board": saved,
        "model2_kind": live_model.kind if live_model else None,
        "model2_kinds": list(live_model.models.m["model2"]) if live_model and live_model.models else [],
        "phone": phone.status(now, anchor[1] if anchor else None),
        "last": last_result,
    })


def update_matrix(now):
    if session is None:
        if now < saved_until:
            show(rows_frame(CHECK))
        elif imu_state == "not found":
            show(text_frame("E!"))
        elif live_model and live_model.latest and now - live_model.latest["t"] < 2:
            # Left letter = Model 1, right letter = Model 2.
            show(text_frame(LABEL_LETTER[live_model.latest["m1"]] + LABEL_LETTER[live_model.latest["m2"]]))
        else:
            show(text_frame("OK"))
    elif session.state == "countdown":
        show(text_frame(str(int(session.remaining(now)) + 1)))
    else:
        done = 1 - session.remaining(now) / session.seconds
        show(text_frame(LABEL_LETTER.get(session.label, "?"), progress=done))


def loop():
    global session, imu_state, last_live, last_status, last_imu_check, saved_until, started, live_model, anchor, last_result
    now = time.time()
    if live_model is None:
        live_model = Live()
    try:
        if not started or now - last_imu_check > 5:
            imu_state = Bridge.call("imu_status")
            last_imu_check = now
            if not started:
                print("IMU:", imu_state, flush=True)
                started = True
        samples = drain()
    except Exception as e:
        print("Bridge error:", e, flush=True)
        time.sleep(0.5)
        return

    recent.extend([now] * len(samples))
    if samples:
        anchor = (now, samples[-1][0])
    recording = session is not None and session.state == "recording"
    live.extend(samples if recording else [x for x in samples if x[0] % IDLE_EVERY_NTH == 0])
    if live_model.add(samples):
        try:
            publish("live", live_model.classify(now))
            if live_model.finished:
                publish("bout", live_model.finished)
                live_model.finished = None
        except Exception as e:
            print("live classify failed:", e, flush=True)

    while not phone_msgs.empty():
        arrival, msg = phone_msgs.get()
        for seq, v, phone_ms in phone.add(arrival, msg, anchor):
            live_model.add_phone(seq, v)
            if session is not None and session.state == "recording":
                session.add_phone(seq, v, phone_ms)
    if anchor:
        # With the phone streaming, wait for its data (it arrives a little after the
        # shin's), up to just before its newest sample so there's one either side.
        ready = min(anchor[1], int(phone.newest_seq) - 1) if phone.on(now) and phone.newest_seq else anchor[1]
        try:
            live_model.count_steps(ready)
        except Exception as e:
            print("step net failed:", e, flush=True)

    while not commands.empty():
        handle_command(commands.get(), now)

    if session is not None:
        if session.state == "countdown" and now - session.t_cmd >= session.countdown:
            session.start_recording(drops)
        elif session.state == "recording":
            full = any(session.add(seq, v) for seq, v in samples)
            stalled = now - session.t_record > session.seconds + 5   # no samples arriving (IMU lost?)
            if full or stalled:
                last_result = session.finish(drops)
                session = None
                saved_until = now + SAVED_SHOW_S

    if now - last_live >= LIVE_EVERY and live:
        publish("imu", {"s": [[seq] + [round(x, 3) for x in v] for seq, v in live]})
        live.clear()
        last_live = now
    if now - last_status >= STATUS_EVERY:
        publish_status(now)
        last_status = now
    mqtt_watchdog(now)

    update_matrix(now)
    time.sleep(0.02)


App.run(user_loop=loop)
