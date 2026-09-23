import time

from mqttlib import MQTTClient

TOPIC = "ME193"

def on_message(topic, payload):
    print(f"[{topic}] {payload}")

client = MQTTClient()
client.connect()
client.subscribe(TOPIC, on_message)
print(f"Listening on '{TOPIC}' (test.mosquitto.org) — Ctrl+C to stop")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    client.disconnect()
