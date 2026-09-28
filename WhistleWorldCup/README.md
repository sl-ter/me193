# Whistle World Cup — 9/28

Drive the car by whistling. PyAudio streams the mic, an FFT picks out the
whistle's pitch, and pitch bands map to drive commands. A live window shows
the signal (spectrogram + FFT) and the decision it made. On World Cup day
the car waits for `start` over MQTT on `ME193/Rogers`, then plays either
"ball" or "goalie" — the role is asked when the script starts, so we're
ready for either assignment.

Built by partner (`spadil01/AI_Robotics`, `audio/` folder) and copied in
here, adapted to this repo's layout.

## Files

- `whistle_control_robot.py` — **the full game script.** Asks for the role,
  connects the Double Motor, opens the live plot in a "waiting for start"
  state, then drives from whistles until a trigger ends the run.
- `live_plot.py` — the live display (command label, scrolling spectrogram,
  FFT, frequency/note/loudness readouts). Run it alone, without a motor, to
  test and tune pitch detection.
- `light_sensor.py` — Color Sensor `reflection` monitor for the ball role.
  Run it alone to calibrate `LIGHT_SENSOR_THRESHOLD`.
- `config.py` — **every tunable lives here**: MQTT topics/messages, card
  color/serial, light threshold, pitch bands, speeds, song URLs.
- `audio_stream.py`, `pitch_utils.py`, `command_state.py`,
  `motor_commands.py` — mic stream, pitch → command, debounce + speed ramp,
  command → motor.
- `spectogram.py` — earlier record-and-plot spectrogram tool;
  `live_plot.py` reuses its `frequency_to_note`.
- `list_audio_devices.py` — prints every mic PyAudio can see with its
  index, for `INPUT_DEVICE_INDEX` in `config.py`. `None` (the setting
  here) uses the system default mic. Indexes differ per machine: the
  partner's config uses `0`, but on this Mac `0` is "Background Music" (a
  loopback device), so it's left at `None`.
- `manual_gate_check.py` — throwaway check that a real `start` message
  unblocks the plot (no motor).
- `send.py` — publishes one message and exits. Defaults to `start` on
  `START_TOPIC`; `--topic` picks another topic, `--goalie` sends the
  goalie trigger.
- `listen.py` — prints every message on the game's topics (start, ball,
  goalie from `config.py`) with the exact topic it arrived on.
- `mqttlib.py` — the class's MQTT wrapper (same file as `MQTTIntro/`, copied
  in per this repo's per-folder convention). Defaults to the public
  `test.mosquitto.org` broker.
- `test_*.py` — 63 pytest unit tests (no mic, motor, or network needed).

Dependencies: `pyaudio` (needs Homebrew's `portaudio`, already installed on
this machine) and `pytest` were added to the root `requirements.txt`;
`legoeducation`, `numpy`, `scipy`, `matplotlib`, and `paho-mqtt` were
already there. Uses the shared root venv.

## Whistle commands

| Pitch | Command |
|---|---|
| silence / out of band / gaps between bands | stop |
| 650–784 Hz | forward (speed ramps 25 → 70% over 5 s held) |
| 799–933 Hz | backward (same ramp) |
| 948–1100 Hz | left (fixed 30%) |
| 1115–1230 Hz | right (fixed 30%) |
| 1300–2000 Hz | **goal** (ball role: ends the run as a goal) |

A command needs 4 consecutive matching chunks (~0.2 s) to take effect.
These bands are fitted to one person's whistle on one mic — whoever
whistles on World Cup day should run `live_plot.py` first and re-fit
`FREQ_BANDS` from its "session whistle range seen" readout.

## Game flow

| Event | Ball does | Goalie does |
|---|---|---|
| `start` on `START_TOPIC` | starts driving | starts driving |
| light sensor ≥ threshold | stops, publishes `Ball stopped` to `BALL_TOPIC`, opens stopped (death) song | — |
| goal whistle | stops, publishes `Goal!` to `BALL_TOPIC`, opens goal song | — |
| `GOALIE_TRIGGER_MESSAGE` on `GOALIE_TOPIC` | — | stops, opens success song |

Songs are YouTube links opened in the default browser, so the laptop needs
internet at the venue. **The messages still need to be agreed with the
opposing team** — edit the topics/messages in `config.py` to match.

## Run it

```bash
cd ~/Code/Projects/me193
source venv/bin/activate
python WhistleWorldCup/live_plot.py               # tune pitch detection, no hardware
python WhistleWorldCup/light_sensor.py            # calibrate the light sensor
python WhistleWorldCup/whistle_control_robot.py   # the real thing
cd WhistleWorldCup && python -m pytest -q         # unit tests
```

Send and watch messages from a second terminal (same venv):

```bash
python WhistleWorldCup/send.py                    # "start" on START_TOPIC
python WhistleWorldCup/send.py --goalie           # goalie trigger on GOALIE_TOPIC
python WhistleWorldCup/send.py stop --topic ME193/Rogers/ballstopped   # anything, anywhere
python WhistleWorldCup/listen.py                  # watch start/ball/goalie topics
python WhistleWorldCup/listen.py --topic ME193/Rogers   # also watch an extra topic
```

These are the **real shared topics** — a `start` you send starts every
robot waiting on that topic (your partner's, other teams'). To test the
scripts themselves, use a private `--topic` like `yourname-test/whistle`.

Run from Terminal.app or iTerm2, not kitty or the VS Code terminal — they
don't reliably pass macOS mic permission through, and the mic then just
returns silence (everything reads as `stop`). Close the plot window or
Ctrl+C to quit; the motor stops and disconnects either way.

## Before World Cup day

- `START_TOPIC` in `config.py` is `ME193/Rogers/` (trailing slash). MQTT
  topics match exactly, so this receives a `start` sent to `ME193/Rogers/`
  but not one sent to `ME193/Rogers`, the topic named in the assignment.
  Confirm which one the instructor will publish on.
- `MOTOR_CARD_*` and `LIGHT_SENSOR_CARD_*` are both red `0994` (partner's
  setup). The session log recorded this team's card as red `1129` on
  9/24 — use whichever card is on the car you're driving.
- `LIGHT_SENSOR_THRESHOLD = 50` is a placeholder until calibrated.
