"""Shared settings for the activity wearable's laptop scripts.

The MQTT names must match unoq/activity-wearable/python/main.py.
"""
from dataclasses import dataclass, field
from pathlib import Path

BROKER = "broker.hivemq.com"   # test.mosquitto.org:1883 is unreachable from Tufts networks (2026-10-26)
PORT = 1883
TOPIC = "ME193/Sam/wear"
RATE_HZ = 100

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"                 # sessions copied off the board (pull_data.py)
LIVE_DIR = DATA_DIR / "live"             # the laptop's own copy of each session, from MQTT
SESSION_LOG = DATA_DIR / "session_log.csv"
BOARD_DATA_DIR = "/home/arduino/ArduinoApps/activity-wearable/data"

LABELS = ("still", "walk", "run", "bike")


@dataclass
class Step:
    key: str                 # fine-grained activity name, saved with the data
    label: str | None        # one of LABELS; None for a check that records nothing
    seconds: float
    title: str
    how: list[str]
    cues: list = field(default_factory=list)   # (seconds into the recording, text shown from then on)


# One person's recording session, in order. Running comes before lying down
# so the session ends on the floor. Lying still counts as "still" on purpose:
# Model 2 then has to recognise air-biking by the pedalling, not just by the
# fact that you're lying down.
PROTOCOL = [
    Step("fit", None, 0, "Put the wearable on", [
        "RIGHT leg, front of the lower shin, a few cm above the ankle.",
        "USB-C port points UP toward the knee; the cable runs up the outside of the knee.",
        "Snug: the case shouldn't slide or rock when you tap it.",
        "Power bank in a front pocket (not behind: you'll lie on your back later).",
    ]),
    Step("orient", None, 0, "Orientation check", [
        "Stand up straight on both feet and keep still.",
        "Y should read about +1 g, X and Z about 0.",
        "Fix anything marked red, then press Enter.",
    ]),
    Step("calib_stand", "still", 10, "Calibration: stand still", [
        "Stand tall, feet hip-width apart, weight on both feet.",
        "Arms relaxed. Don't move at all.",
        "This gives the gravity reference and the gyro's zero.",
    ]),
    Step("stand_natural", "still", 45, "Standing, natural", [
        "Stay on the spot, but be natural: shift your weight, talk, gesture, check your phone.",
        "Feet can shuffle a little. Don't take steps.",
    ]),
    Step("walk_normal", "walk", 45, "Walking, normal pace", [
        "Walk down the hall at your everyday pace.",
        "Turning around at the end is fine; just keep walking.",
    ]),
    Step("walk_varied", "walk", 45, "Walking, slow then fast", [
        "First half: stroll slowly.",
        "Second half: walk fast, like you're late for class. The screen says SWITCH.",
    ], cues=[(22, "SWITCH: walk fast now")]),
    Step("run_easy", "run", 45, "Running, easy jog", [
        "Jog at an easy pace you could talk at.",
        "Turning around is fine; keep jogging.",
    ]),
    Step("run_fast", "run", 30, "Running, fast", [
        "Run clearly faster than the jog. Not an all-out sprint.",
    ]),
    Step("lie_still", "still", 30, "Lying still on your back", [
        "Lie on your back, legs relaxed (flat or knees bent), and stay still.",
        "This counts as 'still' too.",
    ]),
    Step("bike_slow", "bike", 45, "Air-biking, slow", [
        "On your back, lift your legs and pedal slow, full circles.",
        "Like an easy bike ride.",
    ]),
    Step("bike_fast", "bike", 30, "Air-biking, fast", [
        "Same position: pedal fast, full circles.",
    ]),
]
