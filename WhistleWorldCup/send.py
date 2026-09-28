"""Publish one message and exit -- defaults to "start" on START_TOPIC.

    python WhistleWorldCup/send.py                          # "start" on START_TOPIC
    python WhistleWorldCup/send.py stop --topic ME193/Rogers/ballstopped
    python WhistleWorldCup/send.py --goalie                 # GOALIE_TRIGGER_MESSAGE on GOALIE_TOPIC

This publishes to the real, shared class topic -- any robot waiting on it
(yours, your partner's, another team's) will react.
"""

import argparse

from mqttlib import MQTTClient
from config import GOALIE_TOPIC, GOALIE_TRIGGER_MESSAGE, START_TOPIC

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("message", nargs="*", help='message to send (default: "start")')
parser.add_argument("--topic", default=START_TOPIC, help=f"topic to publish on (default: {START_TOPIC!r})")
parser.add_argument("--goalie", action="store_true", help="send GOALIE_TRIGGER_MESSAGE on GOALIE_TOPIC (from config.py)")
args = parser.parse_args()

if args.goalie:
    topic, message = GOALIE_TOPIC, GOALIE_TRIGGER_MESSAGE
else:
    topic, message = args.topic, " ".join(args.message) or "start"

with MQTTClient() as client:
    client.publish(topic, message)
    print(f"Sent to '{topic}': {message}")
