# Manual, throwaway diagnostic: confirm live_plot's `gate` actually gets
# unblocked by a real "start" MQTT message. Not part of the test suite
# (deliberately not named test_*.py, so pytest won't try to collect/run it
# -- this opens a real plot window and a real network connection).
#
# Run from anywhere: python WhistleWorldCup/manual_gate_check.py
# Then, from a second terminal in WhistleWorldCup/:
#   python -c "from mqttlib import MQTTClient; from config import START_TOPIC; c = MQTTClient(); c.connect(); c.publish(START_TOPIC, 'start'); c.disconnect()"

import threading

from mqttlib import MQTTClient

import live_plot
from config import START_TOPIC

started = threading.Event()


def on_start(_topic, payload):
    if payload.strip().lower() == "start":
        started.set()


with MQTTClient() as client:
    client.subscribe(START_TOPIC, on_start)
    print(f"Waiting for 'start' on {START_TOPIC} -- plot should show WAITING FOR START")
    live_plot.main(gate=started)  # no motor
