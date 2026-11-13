"""UNO Q - Linux side of the Infallible Safe.

Reads the USB webcam, runs the finger-counting network (fingernet.py, numpy)
on every frame, feeds its answers to the safe's rules (lock_policy.py) and
acts on what they say:
- LED matrix (leds.py): the count it sees, a bar that fills while you hold a
  digit, a dot per digit entered and a padlock. Full-screen icons when it
  opens, refuses a code, sees a stranger's hand, or locks out.
- Alerts over MQTT, each with a small grey photo from the camera (also saved
  in /app/intruders/, this app's folder on the board): a stranger's hand, a
  lockout after 3 wrong tries, and the duress code. The duress code opens the
  safe exactly like the real code, on the LED too; only the alert gives it away.
- Status twice a second: the state, how many digits are in, frames per second
  and the milliseconds per frame (for the UNO Q vs laptop comparison). The
  digits are never sent or printed. What the camera reads (count and owner
  probability) is only sent with "demo": true in codes.json, because anyone
  on the public broker who knew the topic could watch the code go in.

Until a trained network (fingernet_model.npz, from FingerLock/train.py) is
copied in, it runs a camera check instead: which camera code worked, frame
size and rate, the network's speed on this board (random weights), a test
picture in /app/check/, and once a second on .../check the whole camera frame
(the network's square outlined) plus the square itself, so
the dashboard shows what the board sees while you build the camera rig.

Topics (the base comes from codes.json, e.g. ME193/Sam/safe-1a2b3c4d):
  .../status  board -> dashboard  twice a second
  .../alert   board -> dashboard  {"kind": "stranger" | "lockout" | "duress", "time", "png": base64}
  .../live    board -> dashboard  demo mode only: count probabilities and owner probability
  .../check   board -> dashboard  camera check: the report, then the mat's view
  .../cmd     dashboard -> board  camera-check mode only: {"cmd": "servo", "angle": 0-180, or -1 to let go},
                               for finding the latch angles (settings.json). The working safe never listens.

The door latch: a micro servo on D9 (the sketch makes its pulses). It goes to
servo_locked (settings.json) when the safe starts and relocks, and to
servo_open when a code opens it, the duress code included.

The start button on D2 (the sketch counts presses; "button": true in
settings.json): the safe sleeps with its LEDs dark until it's pressed, then
takes one code (lock_policy.py rule 9). Pressing it while the safe is open
locks it at once. In camera-check mode presses are logged and counted in the
status, to test the wiring.
"""
import json
import os
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import paho.mqtt.client as mqtt

try:
    from arduino.app_utils import App, Bridge, Frame
except ImportError:          # on the laptop, for a dry run (see FingerLock/README.md)
    App = Bridge = Frame = None

import camera as C
import fingernet as FN
import leds
import lock_policy as LP
import photo

HERE = Path(__file__).resolve().parent
APP_DIR = Path(os.environ.get("FINGERLOCK_APP_DIR", "/app"))    # this app's folder on the board; dry runs set a scratch folder
INTRUDER_DIR = APP_DIR / "intruders"
CHECK_DIR = APP_DIR / "check"
MODEL_PATH = Path(os.environ.get("FINGERLOCK_MODEL", HERE / "fingernet_model.npz"))   # override: dry runs
CODES_PATH = HERE / "codes.json"
CODES_EXAMPLE = HERE / "codes.example.json"
SETTINGS_PATH = Path(os.environ.get("FINGERLOCK_SETTINGS", HERE / "settings.json"))   # servo angles etc. (not secret)

BROKER = "broker.emqx.io"   # same as the wearable: test.mosquitto.org:1883 is blocked on Tufts Wi-Fi
PORT = 1883
STATUS_EVERY = 0.5
LIVE_EVERY = 0.2
CHECK_EVERY = 1.0           # camera check: the camera's view once a second, for building the rig
FLASH_S = 1.5               # how long the wrong / stranger icon stays up
STRANGER_PHOTO_GAP_S = 10.0  # at most one stranger photo per 10 s
ECHO_TIMEOUT_S = 8.0
BOARD_ID = f"safe-board-{int(time.time())}"
FAKE_FRAMES = os.environ.get("FINGERLOCK_FAKE_FRAMES")      # dry run: a folder of pictures instead of the camera
MAX_FRAMES = int(os.environ.get("FINGERLOCK_MAX_FRAMES", "0"))
NO_MQTT = os.environ.get("FINGERLOCK_NO_MQTT") == "1"
FAKE_PRESS_EVERY = float(os.environ.get("FINGERLOCK_FAKE_PRESS_EVERY", "0"))   # dry run: a button press every N s


def log(*args):
    print(f"{datetime.now():%H:%M:%S}", *args, flush=True)


# ---- Codes and topic -----------------------------------------------------------------------

USING_EXAMPLE = not CODES_PATH.exists()
CODES = json.loads((CODES_EXAMPLE if USING_EXAMPLE else CODES_PATH).read_text())
TOPIC = CODES["topic"]
SETTINGS = json.loads(SETTINGS_PATH.read_text()) if SETTINGS_PATH.exists() else {}
DEMO = bool(CODES.get("demo", False) or SETTINGS.get("demo", False))
SERVO_LOCKED = int(SETTINGS.get("servo_locked", 90))
SERVO_OPEN = int(SETTINGS.get("servo_open", 0))
# Camera check (and servo calibration) until there's a trained network, or while
# settings.json says "calibrate": true (so the servo can be set up with the model already copied in).
CHECK_MODE = not MODEL_PATH.exists() or bool(SETTINGS.get("calibrate", False))
commands = queue.Queue()                   # .../cmd messages, only listened to in check mode


# ---- MQTT (same pattern as the wearable: our own status echoing back proves the link works) ----

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=BOARD_ID)
last_echo = time.time()
last_kick, kicks = 0.0, 0
restarting = threading.Event()


def on_connect(cl, userdata, flags, reason_code, properties):
    cl.subscribe(TOPIC + "/status")
    if CHECK_MODE:
        cl.subscribe(TOPIC + "/cmd")       # servo calibration; the working safe never listens
    log(f"MQTT connected ({reason_code})")


def on_message(cl, userdata, msg):
    global last_echo
    try:
        data = json.loads(msg.payload)
    except ValueError:
        return
    if msg.topic.endswith("/cmd"):
        commands.put(data)
    elif data.get("board") == BOARD_ID:
        last_echo = time.time()


def start_mqtt():
    client.connect_async(BROKER, PORT, keepalive=15)
    client.loop_start()


def restart_mqtt():
    try:
        client.disconnect()
        client.loop_stop()
    except Exception:
        pass
    try:
        start_mqtt()
    finally:
        restarting.clear()


def mqtt_watchdog(now):
    global last_kick, kicks
    if NO_MQTT or now - last_echo < ECHO_TIMEOUT_S:
        kicks = 0
        return
    if restarting.is_set() or now - last_kick < ECHO_TIMEOUT_S * min(2 ** kicks, 4):
        return
    log(f"MQTT: no echo for {now - last_echo:.0f} s, reconnecting")
    last_kick, kicks = now, kicks + 1
    restarting.set()
    threading.Thread(target=restart_mqtt, daemon=True).start()


def publish(sub, payload, qos=0):
    if NO_MQTT:
        return
    try:
        client.publish(f"{TOPIC}/{sub}", json.dumps(payload), qos=qos)
    except Exception as e:
        log("publish failed:", e)


client.on_connect = on_connect
client.on_message = on_message


# ---- LED matrix -----------------------------------------------------------------------------

_last_led = None


def show(arr):
    global _last_led
    if Bridge is None or (_last_led is not None and np.array_equal(arr, _last_led)):
        return
    try:
        Bridge.call("draw", Frame(arr).to_board_bytes())
        _last_led = arr.copy()
    except Exception as e:
        log("LED draw failed:", e)


# ---- Servo (the door latch) ---------------------------------------------------------------

servo_angle = None


def servo(angle):
    """Move the latch servo (the sketch makes the pulses). A negative angle lets it go limp."""
    global servo_angle
    angle = int(angle)
    if Bridge is not None:
        try:
            Bridge.call("servo", angle)
        except Exception as e:
            log("servo failed:", e)
            return
    servo_angle = angle
    log(f"servo -> {angle}")


# ---- Start button (D2) ------------------------------------------------------------------------

button_total = 0
_button_err_t = -1e9
_last_fake_press = time.time()


def read_button(now):
    """How many times the start button was pressed since the last call (the
    sketch counts them, so a press between two frames isn't missed)."""
    global button_total, _button_err_t, _last_fake_press
    n = 0
    if Bridge is not None:
        try:
            n = int(Bridge.call("button") or 0)
        except Exception as e:
            if now - _button_err_t > 30:            # say so, but don't flood the log every frame
                log("button read failed:", e)
                _button_err_t = now
    elif FAKE_PRESS_EVERY and now - _last_fake_press >= FAKE_PRESS_EVERY:
        n, _last_fake_press = 1, now
    if n:
        button_total += n
        log(f"button pressed ({button_total} so far)")
    return n


# ---- Camera -------------------------------------------------------------------------------

class FolderCamera:
    """Dry run on the laptop: pictures from a folder, in a loop, instead of the camera."""

    def __init__(self, folder):
        import cv2
        self.cv2 = cv2
        self.files = sorted(Path(folder).rglob("*.png")) + sorted(Path(folder).rglob("*.jpg"))
        self.k, self.kind, self.log = 0, f"FolderCamera({folder})", []
        if not self.files:
            raise SystemExit(f"No pictures in {folder}")

    def read(self):
        f = self.cv2.imread(str(self.files[self.k % len(self.files)]), self.cv2.IMREAD_COLOR)
        self.k += 1
        time.sleep(0.05)
        return f


class Stats:
    """Frames per second and milliseconds per frame, smoothed."""

    def __init__(self):
        self.t_last, self.fps, self.prep_ms, self.net_ms, self.no_frame = None, 0.0, 0.0, 0.0, 0

    def add(self, now, prep_ms, net_ms, a=0.1):
        if self.t_last is not None and now > self.t_last:
            self.fps = (1 - a) * self.fps + a / (now - self.t_last) if self.fps else 1 / (now - self.t_last)
        self.t_last = now
        self.prep_ms = (1 - a) * self.prep_ms + a * prep_ms if self.prep_ms else prep_ms
        self.net_ms = (1 - a) * self.net_ms + a * net_ms if self.net_ms else net_ms

    def as_dict(self):
        return {"fps": round(self.fps, 2), "prep_ms": round(self.prep_ms, 2), "net_ms": round(self.net_ms, 2)}


CAMERA_RETRY_S = 10.0       # no camera (unplugged, or plugged in after the app started): look again this often
NO_FRAME_LIMIT = 30         # this many failed reads in a row means the camera is gone

cam = FolderCamera(FAKE_FRAMES) if FAKE_FRAMES else C.BoardCamera()
stats = Stats()
frames_seen = 0
last_status = 0.0
_last_cam_try = time.time()


def camera_lost():
    """Too many failed reads in a row: close the camera and start looking for one again."""
    log(f"camera stopped giving frames: closing it, looking again every {CAMERA_RETRY_S:.0f} s")
    try:
        cam.close()
    except Exception:
        pass
    cam.kind = None
    stats.no_frame = 0


def find_camera(now):
    """Look for a camera again, at most every CAMERA_RETRY_S. True once there is one."""
    global cam, _last_cam_try
    if cam.kind is not None:
        return True
    if FAKE_FRAMES or now - _last_cam_try < CAMERA_RETRY_S:
        return False
    _last_cam_try = now
    new = C.BoardCamera()
    if new.kind is None:
        log(f"still no camera; video devices: {C.devices()}")
        return False
    cam = new
    log(f"camera found: {cam.kind}")
    return True


# ---- Camera check (no trained network yet) -----------------------------------------------------

def camera_report():
    report = {"board": BOARD_ID, "camera": cam.kind, "log": cam.log, "devices": C.devices()}
    try:
        import cv2
        report["cv2"] = cv2.__version__
    except Exception as e:
        report["cv2"] = f"not available: {e!r}"
    try:
        from importlib import metadata
        report["packages"] = sorted(f"{d.metadata['Name']}=={d.version}" for d in metadata.distributions()
                                    if "arduino" in (d.metadata["Name"] or "").lower())
    except Exception as e:
        report["packages"] = repr(e)
    if not cam.kind:
        return report
    frames, t0 = [], time.time()
    for _ in range(45):
        f = cam.read()
        if f is not None:
            frames.append(f)
    if not frames:
        report["error"] = "the camera opened, then stopped giving frames"
        return report
    f = frames[-1]
    report.update(shape=list(f.shape), dtype=str(f.dtype), fps=round(len(frames) / (time.time() - t0), 1),
                  brightness=round(float(FN.to_grey(f).mean()), 1))
    net = FN.FingerNet(weights=FN.random_weights())
    prep, run = [], []
    for _ in range(20):
        t0 = time.perf_counter()
        x = FN.prepare(f)
        t1 = time.perf_counter()
        net.forward(x)
        prep.append((t1 - t0) * 1000)
        run.append((time.perf_counter() - t1) * 1000)
    report.update(prepare_ms=round(float(np.median(prep)), 2), net_ms_random_weights=round(float(np.median(run)), 2))
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    (CHECK_DIR / "frame.png").write_bytes(photo.png_bytes(photo.thumbnail(f, (240, 320))))
    (CHECK_DIR / "crop.png").write_bytes(photo.png_bytes(FN.crop_for_saving(f)))
    report["saved"] = [str(CHECK_DIR / "frame.png"), str(CHECK_DIR / "crop.png")]
    return report


_last_check = 0.0
_reported = False


def send_report():
    """The camera check report: printed, and sent on .../check."""
    global _reported
    report = camera_report()
    log("camera check:\n" + json.dumps(report, indent=2))
    publish("check", {"board": BOARD_ID, "report": report}, qos=1)
    _reported = cam.kind is not None


def publish_check_status(now, state):
    """Status in check mode too: the dashboard shows it, and its echo keeps the MQTT watchdog happy."""
    global last_status
    if now - last_status >= STATUS_EVERY:
        publish("status", {"board": BOARD_ID, "platform": "UNO Q", "state": state, "camera": cam.kind,
                           "servo_angle": servo_angle, "button_presses": button_total, **stats.as_dict(),
                           "example_codes": USING_EXAMPLE})
        last_status = now


BUTTON_LIT_S = 1.5
_button_lit_until = 0.0


def check_screen(now, name):
    """The camera check's LED screen, or for a moment after a button press the
    safe's awake screen (what the LEDs show when the button wakes the safe)."""
    if now < _button_lit_until:
        return leds.render({"state": "locked", "entered": 0, "code_len": len(CODES["code"]),
                            "hold": 0.0, "need_clear": True})
    return leds.screen(name)


def check_loop():
    """Camera check mode: once a second, the whole camera frame (with the
    network's square outlined) and what the network would get, for aiming."""
    global _last_check, frames_seen
    now = time.time()
    frames_seen += 1
    while not commands.empty():                 # servo calibration from the dashboard
        c = commands.get()
        if c.get("cmd") == "servo" and isinstance(c.get("angle"), (int, float)):
            servo(max(-1, min(180, c["angle"])))
    global _button_lit_until
    if read_button(now):                        # testing the button's wiring: logged, counted, LEDs light up
        _button_lit_until = now + BUTTON_LIT_S
    if cam.kind is None:
        if find_camera(now):
            send_report()
        show(check_screen(now, "no_camera"))
        publish_check_status(now, "camera check: no camera")
        mqtt_watchdog(now)
        time.sleep(0.2)
        return
    f = cam.read()
    if f is None:
        stats.no_frame += 1
        if stats.no_frame > NO_FRAME_LIMIT:
            camera_lost()
        time.sleep(0.05)
        mqtt_watchdog(now)
        return
    stats.no_frame = 0
    if not _reported:
        send_report()
    stats.add(now, 0.0, 0.0)
    if now - _last_check >= CHECK_EVERY:
        publish("check", {"board": BOARD_ID, "camera": cam.kind, **stats.as_dict(),
                          "shape": list(f.shape),
                          "frame_png": photo.png_base64(photo.aim_view(f, FN.CROP_FRAC)),
                          "png": photo.png_base64(FN.crop_for_saving(f))})
        _last_check = now
    show(check_screen(now, "check_ok"))
    publish_check_status(now, "camera check")
    mqtt_watchdog(now)


# ---- The safe ---------------------------------------------------------------------------------

flash_kind, flash_until = None, 0.0
last_stranger_photo = 0.0
last_live = 0.0
policy = net = None


def alert(kind, frame, detail=None):
    """Photo + MQTT alert. Stranger photos at most every STRANGER_PHOTO_GAP_S."""
    global last_stranger_photo
    now = time.time()
    if kind == "stranger":
        if now - last_stranger_photo < STRANGER_PHOTO_GAP_S:
            return
        last_stranger_photo = now
    thumb = photo.thumbnail(frame)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        INTRUDER_DIR.mkdir(parents=True, exist_ok=True)
        (INTRUDER_DIR / f"{stamp}_{kind}.png").write_bytes(photo.png_bytes(thumb))
    except OSError as e:
        log("couldn't save the photo:", e)
    publish("alert", {"board": BOARD_ID, "kind": kind, "time": datetime.now().isoformat(timespec="seconds"),
                      "detail": detail or {}, "png": photo.png_base64(thumb)}, qos=1)
    log(f"ALERT {kind}")


def handle(e, frame):
    global flash_kind, flash_until
    note = {k: v for k, v in e.detail.items() if k in ("fails", "owner_avg")}
    if e.kind == "digit":
        log(f"digit accepted ({e.detail.get('n')} in)", note)       # never the digit itself
    else:
        log(e.kind, note)
    if e.kind in ("wrong", "stranger"):
        flash_kind, flash_until = e.kind, e.t + FLASH_S
    if e.kind == "open":
        servo(SERVO_OPEN)           # the duress code opens it exactly the same way
    elif e.kind == "relock":
        servo(SERVO_LOCKED)
    if e.kind == "stranger":
        alert("stranger", frame, note)
    elif e.kind == "lockout":
        alert("lockout", frame, note)
    elif e.kind == "open" and e.duress:
        alert("duress", frame)      # silent: the LED shows an ordinary opening


def safe_loop():
    global last_status, last_live, frames_seen
    now = time.time()
    frames_seen += 1
    if cam.kind is None:
        find_camera(now)
        show(leds.screen("no_camera"))
        if now - last_status >= STATUS_EVERY:
            publish("status", {"board": BOARD_ID, "platform": "UNO Q", "state": "no camera", **stats.as_dict()})
            last_status = now
        mqtt_watchdog(now)
        time.sleep(0.2)
        return
    frame = cam.read()
    if frame is None:
        stats.no_frame += 1
        if stats.no_frame > NO_FRAME_LIMIT:
            camera_lost()
        time.sleep(0.05)
        mqtt_watchdog(now)
        return
    stats.no_frame = 0
    t0 = time.perf_counter()
    x = FN.prepare(frame)
    t1 = time.perf_counter()
    probs, owner_p, _ = net.forward(x)
    stats.add(now, (t1 - t0) * 1000, (time.perf_counter() - t1) * 1000)

    events = policy.press(now) if read_button(now) else []
    for e in events + policy.update(now, probs, owner_p):
        handle(e, frame)
    status = policy.status(now)
    show(leds.render(status, flash_kind if now < flash_until else None))

    if now - last_status >= STATUS_EVERY:
        public = {k: v for k, v in status.items() if DEMO or k not in ("reading", "conf", "owner_p", "hold")}
        publish("status", {"board": BOARD_ID, "platform": "UNO Q", **public, **stats.as_dict(),
                           "example_codes": USING_EXAMPLE, "demo": DEMO})
        last_status = now
    if DEMO and now - last_live >= LIVE_EVERY:
        publish("live", {"board": BOARD_ID, "probs": [round(float(p), 3) for p in probs],
                         "owner_p": round(owner_p, 3)})
        last_live = now
    mqtt_watchdog(now)


# ---- Start ------------------------------------------------------------------------------------

log(f"camera: {cam.kind}")
for line in cam.log:
    log("  ", line)
if USING_EXAMPLE:
    log("WARNING: no codes.json, using the EXAMPLE codes. Run  python FingerLock/set_codes.py  on the laptop and redeploy.")
if not NO_MQTT:
    start_mqtt()

if not CHECK_MODE:
    net = FN.FingerNet(MODEL_PATH)
    meta = net.meta
    policy = LP.make_policy(CODES["code"], CODES.get("duress"), meta, SETTINGS)
    log(f"network from {meta.get('trained', '?')} ({meta.get('photos', '?')} photos), owner threshold {policy.owner_t} "
        f"({'settings.json' if SETTINGS.get('owner_threshold') is not None else 'trained'}, judged per code), "
        f"bar {policy.conf:.0%}, open {policy.open_s:g} s, lockout {policy.lockout_s:g} s, servo locked {SERVO_LOCKED} / open {SERVO_OPEN}, "
        f"{'waits for the button' if policy.button else 'no button'}, {policy.code_len}-digit code, "
        f"demo {'on' if DEMO else 'off'}")
    servo(SERVO_LOCKED)
    loop = safe_loop
else:
    log("Calibration mode (settings.json)" if MODEL_PATH.exists() else "No fingernet_model.npz yet",
        ": running the camera check and listening for servo commands.")
    time.sleep(1.0)     # give MQTT a moment to connect
    send_report()
    loop = check_loop


def run_limited():
    """Dry runs on the laptop: no App Lab, maybe a frame limit."""
    while not MAX_FRAMES or frames_seen < MAX_FRAMES:
        loop()


if App is not None:
    App.run(user_loop=loop)
else:
    run_limited()
