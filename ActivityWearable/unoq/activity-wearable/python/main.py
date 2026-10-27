"""UNO Q - Linux side of the activity wearable.

Drains the sketch's 100 Hz IMU samples and does two jobs at once:
- Live: every 0.5 s it classifies the last 2 s with both models (models.json,
  trained by ActivityWearable/train.py) and publishes the answers for the
  laptop dashboard. The LED matrix shows Model 1's letter on the left and
  Model 2's on the right (S still, W walk, R run, B bike).
- Recording: saves sessions as CSV in data/ (this app's folder on the board,
  mounted at /app) for ActivityWearable/record.py, with the countdown and
  progress on the matrix while it records.

The laptop starts a session with a command on ME193/Sam/wear/cmd. The board
then runs the countdown and the timed recording itself, so a session still
ends cleanly if Wi-Fi drops halfway down the hall.

Topics (must match ActivityWearable/common.py):
  .../cmd     laptop -> board  {"cmd": "record", ...} / {"cmd": "stop"} / {"cmd": "ping"}
                               / {"cmd": "model2", "kind": "tree" | "forest" | "knn"}
  .../status  board -> laptop  twice a second
  .../event   board -> laptop  recording / saved / aborted / error
  .../imu     board -> laptop  live samples, 10 messages a second (every 4th sample when not recording)
  .../live    board -> laptop  both models' answers, twice a second, plus the current
                               activity bout (duration, strides) and the last 6 bouts
  .../bout    board -> laptop  a bout that just ended
"""
import json
import os
import queue
import re
import time
from collections import deque
from datetime import datetime

import numpy as np
import paho.mqtt.client as mqtt
from arduino.app_utils import App, Bridge, Frame

import classify
import features as F

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

# Stride counting: once per stride the shin swings forward fast, a peak in -gx.
# Count when -gx rises past STRIDE_ENTER, re-arm once it falls below
# STRIDE_LEAVE, and never count twice within STRIDE_GAP. Checked on all 27
# recorded sessions: median error ~3% against each session's stride rate, 0 on
# every still session. While air-biking, the same peak comes once per pedal turn.
STRIDE_ENTER_DPS = 120.0
STRIDE_LEAVE_DPS = 40.0
STRIDE_GAP = 55                 # samples (0.55 s): at most 1.8 strides a second
BOUT_CONFIRM = 2                # a new activity must hold for 2 answers (1 s) to start a new bout
RECENT_BOUTS = 6
MODELS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")

AXES_NOTE = "+Y up the shin (toward the knee), +Z forward out of the shin, +X to the wearer's left"
COLUMNS = "t_s,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps"

# ---- MQTT -------------------------------------------------------------------
commands = queue.Queue()


def on_connect(client, userdata, flags, reason_code, properties):
    client.subscribe(TOPIC + "/cmd")
    client.subscribe(TOPIC + "/status")   # to hear our own status come back (mqtt_watchdog)
    print(f"MQTT connected ({reason_code}), listening on {TOPIC}/cmd", flush=True)


last_echo = time.time()     # last time our own status came back through the broker
last_kick = 0.0


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
    start the connection over."""
    global last_kick, last_echo
    if now - last_echo < ECHO_TIMEOUT_S or now - last_kick < ECHO_TIMEOUT_S:
        return
    print(f"MQTT: no echo for {now - last_echo:.0f} s, reconnecting", flush=True)
    last_kick = now
    try:
        client.disconnect()
    except Exception:
        pass
    client.loop_stop()
    start_mqtt()


def publish(sub, payload):
    client.publish(f"{TOPIC}/{sub}", json.dumps(payload))


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
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
}
CHECK = ["0000000000000", "0000000000011", "0000000000110", "0000000001100",
         "1100000011000", "0110000110000", "0011001100000", "0001111000000"]
LABEL_LETTER = {"still": "S", "walk": "W", "run": "R", "bike": "B"}
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
        self.state = "recording"
        self.t_record = time.time()
        self.drops_at_start = drops
        publish("event", {"type": "recording", "session": self.name, "seconds": self.seconds})
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

    def stats(self, drops):
        m = np.array(self.mags) if self.mags else np.zeros(1)
        return {"session": self.name, "file": os.path.basename(self.path or ""), "rows": self.rows,
                "expected": int(self.seconds * RATE_HZ), "gaps": self.gaps,
                "drops": drops - self.drops_at_start,
                "acc_mean_g": round(float(m.mean()), 3), "acc_std_g": round(float(m.std()), 3),
                "acc_peak_g": round(float(m.max()), 3),
                "gyro_rms_dps": round((self.gyro_sq / max(self.rows, 1)) ** 0.5, 1)}

    def finish(self, drops, aborted=False):
        stats = self.stats(drops)
        if self.file:
            self.file.write(f"# end rows={self.rows} gaps={self.gaps} drops={stats['drops']}"
                            f"{' ABORTED' if aborted else ''}\n")
            self.file.close()
            self.file = None
        if aborted and self.path:
            os.replace(self.path, self.path[:-4] + "_aborted.csv")
            stats["file"] = os.path.basename(self.path[:-4] + "_aborted.csv")
        publish("event", {"type": "aborted" if aborted else "saved", **stats})
        print(("aborted " if aborted else "saved ") + json.dumps(stats), flush=True)


# ---- Live classification ----------------------------------------------------
class Live:
    """Keeps the last 2 s of samples and classifies them every 0.5 s."""

    def __init__(self):
        self.models = classify.Models(MODELS_PATH) if os.path.exists(MODELS_PATH) else None
        self.kind = self.models.m["model2_default"] if self.models else None
        self.buf = deque(maxlen=F.WINDOW)
        self.last_seq = None
        self.since = 0
        self.hist1, self.hist2 = deque(maxlen=SMOOTH), deque(maxlen=SMOOTH)
        self.latest = None
        self.strides = 0                    # since the app started
        self.armed, self.last_stride = True, -10 ** 9
        self.bout, self.pending, self.bout_n = None, None, 0
        self.recent_bouts = deque(maxlen=RECENT_BOUTS)
        self.finished = None                # a bout that just ended, for main loop to publish
        print(f"live models: {'loaded, Model 2 = ' + self.kind if self.models else 'models.json missing'}", flush=True)

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
            swing = -v[3]                   # -gx, deg/s
            if self.armed and swing > STRIDE_ENTER_DPS and seq - self.last_stride >= STRIDE_GAP:
                self.strides += 1
                self.last_stride, self.armed = seq, False
            elif not self.armed and swing < STRIDE_LEAVE_DPS:
                self.armed = True
            if len(self.buf) == F.WINDOW and self.since >= F.STEP:
                self.since = 0
                due = True
        return due and self.models is not None

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
            "strides_total": self.strides, "bout": bout, "recent_bouts": list(self.recent_bouts),
        }
        return self.latest

    def update_bout(self, label, now):
        """A bout = one stretch of the same activity (Model 2's answer). It ends
        when a different answer holds for BOUT_CONFIRM answers in a row, so a
        brief flicker (a turnaround at the end of the hall) doesn't split it.
        Its strides are the ones counted while it lasted."""
        if self.bout is None:
            self.bout = {"id": 0, "label": label, "start": now, "strides0": self.strides}
        if label == self.bout["label"]:
            self.pending = None
        elif self.pending is None or self.pending["label"] != label:
            self.pending = {"label": label, "t": now, "strides": self.strides, "count": 1}
        else:
            self.pending["count"] += 1
        if self.pending and self.pending["count"] >= BOUT_CONFIRM:
            done = self.bout_summary(self.pending["t"], self.pending["strides"])
            self.recent_bouts.appendleft(done)
            self.finished = done
            self.bout_n += 1
            self.bout = {"id": self.bout_n, "label": self.pending["label"], "start": self.pending["t"],
                         "strides0": self.pending["strides"]}
            self.pending = None
        return self.bout_summary(now, self.strides)

    def bout_summary(self, end, strides_now):
        b = self.bout
        return {"id": b["id"], "label": b["label"], "start": round(b["start"], 1),
                "duration_s": round(end - b["start"], 1), "strides": strides_now - b["strides0"]}


live_model = None


# ---- Main loop --------------------------------------------------------------
session = None
imu_state = "?"
drops = errors = 0
live = []                      # samples waiting to go out on .../imu
recent = deque()               # arrival times of recent samples, for the measured rate
last_live = last_status = last_imu_check = 0.0
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
    global session
    kind = cmd.get("cmd")
    if kind == "record":
        if session is not None:
            publish("event", {"type": "error", "message": f"busy with {session.name}"})
            return
        session = Session(cmd)
        print(f"countdown for {session.name}", flush=True)
    elif kind == "stop" and session is not None:
        if session.state == "recording":
            session.finish(drops, aborted=True)
        else:
            publish("event", {"type": "aborted", "session": session.name, "rows": 0})
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
    global session, imu_state, last_live, last_status, last_imu_check, saved_until, started, live_model
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

    while not commands.empty():
        handle_command(commands.get(), now)

    if session is not None:
        if session.state == "countdown" and now - session.t_cmd >= session.countdown:
            session.start_recording(drops)
        elif session.state == "recording":
            full = any(session.add(seq, v) for seq, v in samples)
            stalled = now - session.t_record > session.seconds + 5   # no samples arriving (IMU lost?)
            if full or stalled:
                session.finish(drops)
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
