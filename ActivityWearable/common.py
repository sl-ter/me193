"""Shared settings for the activity wearable's laptop scripts.

The MQTT names must match unoq/activity-wearable/python/main.py.
"""
from dataclasses import dataclass, field
from pathlib import Path

BROKER = "broker.emqx.io"   # test.mosquitto.org:1883 is unreachable from Tufts networks; broker.hivemq.com stalled ~8 s on 3 of 8 connects (2026-10-26)
PORT = 1883
TOPIC = "ME193/Sam/wear"
RATE_HZ = 100

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"                 # sessions copied off the board (pull_data.py)
LIVE_DIR = DATA_DIR / "live"             # the laptop's own copy of each session, from MQTT
SESSION_LOG = DATA_DIR / "session_log.csv"
BOARD_DATA_DIR = "/home/arduino/ArduinoApps/activity-wearable/data"

LABELS = ("still", "walk", "run", "bike")
# Step-counting sessions that mix activities (e.g. walk 30 steps, then stand)
# are labelled "mixed"; the activity models (train.py) leave them out.
MIXED = "mixed"
PHONE_URL = "https://sl-ter.github.io/me193/ActivityWearable/phone/"


@dataclass
class Step:
    key: str                 # fine-grained activity name, saved with the data
    label: str | None        # one of LABELS; None for a check that records nothing
    seconds: float
    title: str
    how: list[str]
    cues: list = field(default_factory=list)   # (seconds into the recording, text shown from then on)
    taps: bool = False       # the observer taps every footstrike (record.py's tap mode)
    target: int | None = None   # steps the walker counts out loud, to check the taps against


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


# The step-counting protocol (week 2, the neural-net step counter): the same
# shin wearable plus the phone in the left pocket, and every session in tap
# mode, so each footstrike gets a time. Includes the awkward cases a counter
# gets wrong (turns, stop-start, shuffling on the spot) and zero-step sessions
# (standing, air-biking) so the network learns what isn't a step.
TAP_HOW = "Observer: tap every footstrike, f = left foot, j = right foot (space if unsure)."
STEP_PROTOCOL = [
    Step("fit", None, 0, "Put on the wearable and the phone", [
        "Wearable: RIGHT leg, front of the lower shin, USB-C up toward the knee, snug (as last week).",
        f"Phone: open {PHONE_URL} in Safari, tap Start, allow motion, then Pocket mode.",
        "Phone in the LEFT front pocket, any way round. A snug pocket is better than a loose one.",
        "Power bank in the right front pocket.",
    ]),
    Step("orient", None, 0, "Orientation check", [
        "Stand up straight on both feet and keep still.",
        "Y should read about +1 g, X and Z about 0.",
        "Fix anything marked red, then press Enter.",
    ]),
    Step("phone", None, 0, "Phone check", [
        "The header should show the phone streaming at about 60 Hz.",
        "If not: is the page still on screen (not locked)? Reload it and tap Start again.",
    ]),
    Step("calib_stand", "still", 10, "Calibration: stand still", [
        "Stand tall, feet hip-width apart, weight on both feet. Don't move at all.",
        "No taps: this is a zero-step session.",
    ], taps=True),
    Step("walk_normal", "walk", 40, "Walking, normal pace", [
        "Walk down the hall at your everyday pace. Turning around at the end is fine.",
        TAP_HOW,
    ], taps=True),
    Step("walk_counted", MIXED, 30, "Walk exactly 30 steps", [
        "Walk at a normal pace, counting your steps OUT LOUD.",
        "Stop after 30 steps and stand still until the time runs out.",
        TAP_HOW,
    ], taps=True, target=30),
    Step("walk_turns", "walk", 40, "Walking with turns", [
        "Walk, turning around every 5-6 steps (tight turns, both directions).",
        TAP_HOW,
    ], taps=True),
    Step("walk_stopstart", MIXED, 40, "Stop and start", [
        "Take a few steps (2 to 8, vary it), stop for 2-3 s, repeat.",
        TAP_HOW,
    ], taps=True),
    Step("fidget", MIXED, 30, "Fidgeting on the spot", [
        "Stay on the spot: shift your weight, sway, tap a foot, turn around on the spot.",
        "Observer: tap only when a foot is lifted and put down somewhere new.",
    ], taps=True),
    Step("stairs", "walk", 40, "Stairs", [
        "Walk up and down a flight of stairs. Press s to skip if there are none nearby.",
        TAP_HOW,
    ], taps=True),
    Step("run_easy", "run", 30, "Running, easy jog", [
        "Jog at an easy pace you could talk at. Turning around is fine.",
        TAP_HOW,
    ], taps=True),
    Step("run_fast", "run", 20, "Running, fast", [
        "Run clearly faster than the jog. Not an all-out sprint.",
        TAP_HOW,
    ], taps=True),
    Step("bike_fast", "bike", 30, "Air-biking", [
        "On your back, lift your legs and pedal full circles, slow then fast.",
        "No taps: this is a zero-step session.",
    ], taps=True),
]
PROTOCOLS = {"steps": STEP_PROTOCOL, "activity": PROTOCOL}
