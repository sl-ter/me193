"""Two-way MQTT chat in one terminal: prints what arrives, sends what you type.

    python chat.py                        # chat on ME193 as "Sam"
    python chat.py --name Sergio          # different sender name
    python chat.py --topic ME193/Rogers   # a different topic
    python chat.py --raw                  # send plain text instead of JSON

Messages go out as {"sender": NAME, "text": ...} -- the format others on
ME193 use -- and incoming JSON in that shape is shown as "sender: text".
Anything else is printed as-is. Ctrl+C or Ctrl+D to quit.
"""

import argparse
import json
import time

from mqttlib import MQTTClient

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--topic", default="ME193", help="topic to chat on (default: ME193)")
parser.add_argument("--name", default="Sam", help='sender name (default: "Sam")')
parser.add_argument("--raw", action="store_true", help="send plain text instead of JSON")
args = parser.parse_args()

# Payloads we sent, so their echo back from the broker is labeled "(you)".
sent = []


def format_message(payload):
    try:
        data = json.loads(payload)
    except ValueError:
        return payload
    if isinstance(data, dict) and "text" in data:
        return f"{data.get('sender', '?')}: {data['text']}"
    return payload


def on_message(_topic, payload):
    you = " (you)" if payload in sent else ""
    if you:
        sent.remove(payload)
    print(f"\r[{time.strftime('%H:%M:%S')}] {format_message(payload)}{you}\n> ", end="", flush=True)


client = MQTTClient()
client.connect()
client.subscribe(args.topic, on_message)
print(f"Chatting on '{args.topic}' (test.mosquitto.org) as {args.name} -- type and press Enter. Ctrl+C to quit.")

try:
    while True:
        text = input("> ").strip()
        if not text:
            continue
        payload = text if args.raw else json.dumps({"sender": args.name, "text": text})
        sent.append(payload)
        client.publish(args.topic, payload)
except (KeyboardInterrupt, EOFError):
    print()
finally:
    client.disconnect()
