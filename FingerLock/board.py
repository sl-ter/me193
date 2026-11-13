#!/usr/bin/env python3
"""The Infallible Safe on the UNO Q, from the laptop, one command each.

    cd ~/Code/Projects/me193 && source venv/bin/activate
    python FingerLock/board.py start     # after the board restarts: start the safe (a few seconds)
    python FingerLock/board.py deploy    # after changing code, settings.json or the model: copy it all, then start
    python FingerLock/board.py status    # what the safe says right now
    python FingerLock/board.py logs      # the safe's last log lines
    python FingerLock/board.py stop      # stop the safe
    python FingerLock/board.py latch     # the board only moves the latch, for laptop_lock.py --latch
                                         # (deploy puts the safe back)
    python FingerLock/board.py install-starter   # once: lets the dashboard's "Start the safe" button work

The starter (unoq/safe-starter/safe_starter.py) lives on the board's own
Linux and keeps itself running (a cron line, no sudo), so after a power cut
the dashboard's "Start the safe" button starts the safe without this laptop.

After a power cut the board boots into its status app (the IP scrolls on the
LEDs), not the safe. Once the IP scrolls, run start. It copies nothing, so it
needs the safe to have been deployed once; use deploy after any change.

Everything goes through tools/deploy.py, which finds the board over USB or
Wi-Fi (the addresses in tools/board_secrets.py). status listens to the safe's
MQTT status, so it works from anywhere with internet.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEPLOY = ROOT / "tools" / "deploy.py"
APPS = "/home/arduino/ArduinoApps"
SAFE = f"{APPS}/finger-lock"

# The board runs one app at a time: stop whichever app is running (the status
# app after a reboot), then start the safe. Same steps as deploy.py, minus the copying.
STOP_ALL = ("for n in $(docker ps --format '{{.Names}}' | grep -- '-main-1$' | sed 's/-main-1$//'); do "
            f"arduino-app-cli app stop {APPS}/$n; done")


def on_board(cmd):
    return subprocess.run([sys.executable, str(DEPLOY), "--cmd", cmd]).returncode


def status(seconds=4.0):
    """The safe's own status messages for a few seconds (never the code)."""
    import paho.mqtt.client as mqtt
    sys.path.insert(0, str(HERE))
    from common import BROKER, PORT, load_codes
    _, _, topic = load_codes(quiet=True)
    last = {}

    def on_message(client, userdata, msg):
        try:
            last.update(json.loads(msg.payload))
        except ValueError:
            pass

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"safe-status-{int(time.time())}")
    c.on_message = on_message
    c.connect(BROKER, PORT, keepalive=15)
    c.subscribe(f"{topic}/status")
    c.loop_start()
    time.sleep(seconds)
    c.loop_stop()
    if not last:
        print("No status from the safe. Is it running? Try: python FingerLock/board.py start")
        return 1
    if str(last.get("state", "")).startswith("camera check"):
        print(f"Board: calibration (latch) mode, {last['state']}; it moves the latch on MQTT servo commands, "
              f"last at {last.get('servo_angle')}")
        return 0
    state = {"idle": "asleep, waiting for the button", "locked": "awake, taking a code"}.get(last.get("state"), last.get("state"))
    print(f"Safe: {state}")
    print(f"  {last.get('code_len', '?')}-digit code, {last.get('entered', 0)} in, {last.get('fails', 0)} wrong in a row"
          + (f", {last.get('left_s')} s left" if last.get("left_s") else ""))
    print(f"  {last.get('fps', '?')} frames/s, prepare {last.get('prep_ms', '?')} ms, network {last.get('net_ms', '?')} ms")
    return 0


def install_starter():
    """Copy the starter and its MQTT library (the laptop venv's paho, pure Python) to
    ~/safe-starter on the board, add its every-minute cron line, start it, and
    check it says it's alive."""
    sys.path.insert(0, str(ROOT / "tools"))
    import deploy as D
    import paho
    home = "/home/arduino/safe-starter"
    board = D.find_board()
    D.remote(board, f"mkdir -p {home}/lib")
    D.push(board, [str(HERE / "unoq" / "safe-starter" / "safe_starter.py")], home)
    D.push(board, [str(Path(paho.__file__).parent)], f"{home}/lib")
    line = f"* * * * * /usr/bin/python3 {home}/safe_starter.py >> {home}/starter.log 2>&1"
    # Keep the crontab's other lines (Board Status's IP script), replace any old starter line.
    D.remote(board, f"(crontab -l 2>/dev/null | grep -v 'safe-starter/safe_starter.py'; echo '{line}') | crontab - "
                    "&& crontab -l")
    # Restart it on the new script. The [s] keeps pkill from matching this command itself.
    D.remote(board, "pkill -f 'safe-starter/[s]afe_starter.py'", check=False)
    time.sleep(1)
    D.remote(board, f"setsid nohup /usr/bin/python3 {home}/safe_starter.py >> {home}/starter.log 2>&1 < /dev/null &")
    time.sleep(6)
    D.remote(board, f"tail -3 {home}/starter.log", check=False)
    return starter_status()


def starter_status(seconds=4.0):
    """The starter's last word (retained on <topic>/starter)."""
    import paho.mqtt.client as mqtt
    sys.path.insert(0, str(HERE))
    from common import BROKER, PORT, load_codes
    _, _, topic = load_codes(quiet=True)
    got = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"starter-check-{int(time.time())}")
    c.on_message = lambda cl, u, m: got.update(json.loads(m.payload))
    c.connect(BROKER, PORT, keepalive=15)
    c.subscribe(f"{topic}/starter")
    c.loop_start()
    time.sleep(seconds)
    c.loop_stop()
    if got.get("state") in ("listening", "starting"):
        print(f"Starter: {got['state']}, safe {'running' if got.get('safe_running') else 'not running'}, "
              f"board at {got.get('ip')}, {round(time.time() - got.get('t', 0))} s ago")
        return 0
    print(f"Starter: {got.get('state', 'no word yet')}")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["start", "deploy", "status", "logs", "stop", "latch", "install-starter"])
    args = ap.parse_args()
    if args.what == "start":
        rc = on_board(f"{STOP_ALL}; arduino-app-cli app start {SAFE}")
        if rc == 0:
            time.sleep(8)
            rc = status()
    elif args.what == "deploy":
        rc = subprocess.run([sys.executable, str(DEPLOY), str(HERE / "unoq" / "finger-lock")]).returncode
        if rc == 0:
            time.sleep(5)
            rc = status()
    elif args.what == "status":
        rc = status()
    elif args.what == "latch":
        # Calibration mode, set in the board's copy of settings.json only: it listens for servo
        # commands (the laptop safe's --latch, the dashboard slider). The next deploy overwrites it.
        rc = on_board(f"sed -i 's/\"calibrate\": *false/\"calibrate\": true/' {SAFE}/python/settings.json; "
                      f"grep -o '\"calibrate\": *[a-z]*' {SAFE}/python/settings.json; {STOP_ALL}; arduino-app-cli app start {SAFE}")
        if rc == 0:
            time.sleep(8)
            rc = status()
            print("Latch mode: run python FingerLock/laptop_lock.py --camera 0 --latch (deploy puts the safe back).")
    elif args.what == "install-starter":
        rc = install_starter()
    elif args.what == "logs":
        rc = on_board(f"arduino-app-cli app logs {SAFE} --tail 40")
    else:
        rc = on_board(f"arduino-app-cli app stop {SAFE}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
