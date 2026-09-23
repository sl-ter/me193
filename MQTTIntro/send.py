import sys

from mqttlib import MQTTClient

TOPIC = "ME193"

message = " ".join(sys.argv[1:]) or input("Message to send: ")

with MQTTClient() as client:
    client.publish(TOPIC, message)
    print(f"Sent to '{TOPIC}': {message}")
