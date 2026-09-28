"""Print every message on the game's topics (START/BALL/GOALIE from config.py).

    python WhistleWorldCup/listen.py
    python WhistleWorldCup/listen.py --topic ME193/Rogers   # add extra topics

Leave it running in a second terminal to see what actually arrives, and
on which exact topic. Ctrl+C to stop.
"""

import argparse
import time

from mqttlib import MQTTClient
from config import BALL_TOPIC, GOALIE_TOPIC, START_TOPIC

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--topic", action="append", default=[], help="extra topic to listen on (repeatable)")
args = parser.parse_args()

# mqttlib routes messages by exact topic, so MQTT wildcards (#, +) won't
# print anything -- list each topic explicitly instead.
topics = list(dict.fromkeys([START_TOPIC, BALL_TOPIC, GOALIE_TOPIC, *args.topic]))


def on_message(topic, payload):
    print(f"[{time.strftime('%H:%M:%S')}] {topic!r}: {payload}")


client = MQTTClient()
client.connect()
for topic in topics:
    client.subscribe(topic, on_message)
print("Listening on (test.mosquitto.org) -- Ctrl+C to stop:")
for topic in topics:
    print(f"  {topic!r}")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    client.disconnect()
