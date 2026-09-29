# MQTT intro — 9/22

Publish/subscribe over MQTT using `mqttlib.py` (a thin wrapper around
`paho-mqtt`, pulled from the class repo:
[chrisbuerginrogers/ME193-Robotics](https://github.com/chrisbuerginrogers/ME193-Robotics/blob/main/Public%20stuff/useful%20libraries/MQTTLIB.md)),
against the public `test.mosquitto.org` broker on the class topic `ME193`.

## Files

- `mqttlib.py` — the class's wrapper library (copied in, not pip-installed).
- `mqtt_test.py` — publishes `"hello world"` and subscribes at the same
  time, so you see your own message echo back. Good for confirming the
  setup works.
- `listen.py` — subscribes only and stays running, printing every message
  it sees on `ME193`. Use this to watch for messages from the instructor
  or other students.
- `send.py` — publishes a one-off message to `ME193` and exits. Run it in
  a second terminal alongside `listen.py` (they're independent MQTT
  connections, so both can run at once) to reply to what you see.
- `chat.py` — two-way chat in one terminal: prints what arrives and sends
  what you type. Defaults to `ME193` as "Sam", sending
  `{"sender": ..., "text": ...}` JSON (the format others on `ME193` use)
  and showing incoming messages in that shape as `sender: text`. Your own
  messages echo back marked `(you)`. `--name`, `--topic`, and `--raw`
  (plain text) change the defaults.

## Usage

```bash
cd ~/Code/Projects/me193
source venv/bin/activate
cd MQTTIntro
python mqtt_test.py           # round-trip sanity check
python listen.py              # leave running to catch live messages (Ctrl+C to stop)
python send.py "some message" # in a second terminal, to send something
python chat.py                # read + reply in one window (Ctrl+C to quit)
python chat.py --topic ME193/Rogers   # chat on another topic
```

## Notes

- `ME193` is a **public, unauthenticated, shared topic** on
  `test.mosquitto.org` — anyone (any student, the instructor, or a
  stranger) can publish or subscribe to it. Expect crosstalk from other
  people testing at the same time; don't publish anything sensitive.
- No new dependency beyond `paho-mqtt` (added to the shared root
  `requirements.txt`) — this exercise uses the shared root venv, no venv
  of its own.
