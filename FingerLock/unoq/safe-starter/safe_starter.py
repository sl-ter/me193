#!/usr/bin/env python3
"""The Infallible Safe's starter, so the dashboard can start the safe without a laptop.

It runs on the UNO Q's own Linux, outside App Lab's containers, where it can
use arduino-app-cli. After a power cut the board boots into its status app,
not the safe. This keeps a connection to the same MQTT broker as the safe and
the dashboard and listens on <topic>/board for {"cmd": "start"}. Then it stops
whatever App Lab app is running and starts the safe: the same steps as
`python FingerLock/board.py start`.

Every 20 s it says it's alive on <topic>/starter (retained, so a dashboard that
opens later sees it at once): whether the safe is running, and the board's IP.
If the board loses power, the broker sends "offline" there for it.

The topic comes from the safe's own codes.json (only the topic is read), and
if it changes (set_codes.py --new-topic, then a deploy) the starter exits so
cron restarts it on the new one.

Installed by `python FingerLock/board.py install-starter`, into
~/safe-starter/ with the MQTT library (paho-mqtt) in lib/. A cron line runs it
every minute; a lock file keeps it to one copy, so it's always running, and it
comes back by itself after a power cut. No sudo needed.
"""
import fcntl
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import paho.mqtt.client as mqtt  # noqa: E402

APPS = Path("/home/arduino/ArduinoApps")
SAFE = APPS / "finger-lock"
CLI = "/usr/bin/arduino-app-cli"
BROKER, PORT = "broker.emqx.io", 1883
HEARTBEAT_S = 20
MIN_GAP_S = 30                      # a second start this soon after one is ignored
ENV = dict(os.environ, HOME="/home/arduino", PATH="/usr/local/bin:/usr/bin:/bin")   # cron's PATH is short


def log(*args):
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), *args, flush=True)


def read_topic():
    return json.loads((SAFE / "python" / "codes.json").read_text())["topic"]


def running_apps():
    r = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, env=ENV, timeout=30)
    return [n[:-len("-main-1")] for n in r.stdout.split() if n.endswith("-main-1")]


def board_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))          # no packet is sent; it just picks the outgoing address
            return s.getsockname()[0]
    except OSError:
        return None


def start_safe():
    running = running_apps()
    if "finger-lock" in running:
        return "already running"
    for name in running:                         # one app at a time: the status app after a reboot
        subprocess.run([CLI, "app", "stop", str(APPS / name)], env=ENV, capture_output=True, timeout=120)
    r = subprocess.run([CLI, "app", "start", str(SAFE)], env=ENV, capture_output=True, text=True, timeout=600)
    return "started" if r.returncode == 0 else "failed: " + (r.stderr or r.stdout).strip()[-200:]


def main():
    lock = open(HERE / "starter.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return                                   # already running: cron's every-minute try ends here, quietly

    topic = read_topic()
    asks = []

    def on_connect(client, userdata, flags, reason_code, properties=None):
        log(f"connected to {BROKER} ({reason_code})")
        client.subscribe(f"{topic}/board")

    def on_message(client, userdata, msg):
        try:
            d = json.loads(msg.payload)
        except ValueError:
            return
        if isinstance(d, dict) and d.get("cmd") == "start":
            asks.append(time.time())

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"safe-starter-{int(time.time())}")
    client.on_connect, client.on_message = on_connect, on_message
    client.will_set(f"{topic}/starter", json.dumps({"state": "offline"}), qos=1, retain=True)
    client.connect_async(BROKER, PORT, keepalive=30)
    client.loop_start()
    log(f"starter up, listening on {topic}/board")

    def say(state, **extra):
        client.publish(f"{topic}/starter", json.dumps({
            "state": state, "safe_running": "finger-lock" in running_apps(), "ip": board_ip(),
            "t": round(time.time()), **extra}), qos=1, retain=True)

    last_start, last_beat = 0.0, 0.0
    while True:
        now = time.time()
        if asks:
            asks.clear()
            if now - last_start < MIN_GAP_S:
                say("listening", last="ignored: a start ran under 30 s ago")
            else:
                last_start = now
                say("starting")
                log("start asked from the dashboard")
                result = start_safe()
                log("start:", result)
                say("listening", last=result)
            last_beat = time.time()
        elif now - last_beat >= HEARTBEAT_S:
            try:
                if read_topic() != topic:
                    log("the topic changed: exiting so cron restarts on the new one")
                    client.publish(f"{topic}/starter", json.dumps({"state": "moved"}), qos=1, retain=True)
                    time.sleep(1)
                    return
            except (OSError, ValueError, KeyError):
                pass
            say("listening")
            last_beat = now
        time.sleep(0.5)


if __name__ == "__main__":
    main()
