# Virtual ping-pong — 10/12

Midterm: play ping-pong against a virtual wall, with the LEGO Education Double
Motor as the paddle. Every rally uses the sensors from the class so far, and
the paddle pushes back with haptic feedback, which we haven't done before.

## How each piece is used

| Piece | Job in the game | Where |
|---|---|---|
| **Pose** (MediaPipe Pose Landmarker, as in PoseRaceCar) | Puts the paddle where your hand is. Your wrist's left-right position in the camera becomes the paddle's position on the court | `vision.py` `PoseTracker` |
| **IMU** (Double Motor gyro, as in SillyWalks) | Tells whether you're actually swinging. Gyro magnitude \|ω\| spikes past a calibrated threshold | `swing.py` `SwingDetector`, `paddles.py` `LegoPaddle` |
| **AprilTags** (36h11 via `cv2.aruco`, as in AprilTagCentering) | Hold up tag 1, 2 or 3 for ~0.6 s to choose easy/medium/hard (ball speed, speed-up per hit, paddle width) and start the game. Tag 0 pauses | `vision.py` `TagReader`, levels in `game.py` |
| **MQTT** (`mqttlib.py`, as in MQTTIntro) | After every hit and miss, publishes the **record number of continuous hits** as a float (`"7.0"`) to `ME193/Rogers/Sam` | `pong.py` `Scoreboard` |
| **Hardware programming** (`legoeducation` over BLE) | The IMU stream is raised from 10 Hz to 50 Hz, and the motor is used as a vibration motor | `paddles.py` |
| **New: haptics** | An off-center LEGO weight on one motor output makes a rumble motor. As the ball approaches, light ticks start about 1 s out and speed up until it arrives. **Contact** is a stiff full-power kick (forward, then straight back); a sweet-spot hit gets a shorter, crisper kick plus an azure light. A **miss** is three long rumbles plus a red light. Plus a start beep | `paddles.py` `_haptic_loop`, rumble timing in `pong.py` |
| **New: spin** | **Rolling** the paddle as you swing curves the ball. Point its nose at the screen; rolling right (clockwise as you see it) curves right. It's roll, not yaw, because the swing itself is mostly yaw. Spin is the share of the swing's peak gyro that's on the roll axis, from −1 to +1. The curve scales with ball speed, and the wall takes off half the spin | `swing.py`, `game.py` |

**The hit rule** combines pose and IMU. When the ball reaches your hitting line, it counts as a hit only if:
- your paddle (from pose) is under the ball, and
- you swung (from the IMU) between 0.30 s before and 0.15 s after it arrives.

So holding the paddle in the right spot without swinging is a miss ("no swing"). Swinging in the wrong spot is also a miss ("out of position").

Where the ball lands on the paddle sets the return angle; the edges send it up to 55° sideways. A harder swing (higher peak gyro) returns the ball faster. The sweet spot, the middle quarter of the paddle, adds a small speed bonus. Twisting while you swing adds spin. Below 25% twist, the shot counts as flat.

**No model training.** MediaPipe Pose is already trained. We only read one of its outputs, the wrist position, and there's no gesture classifier like PoseRaceCar's KNN. The only "training" is calibration: hold the paddle still for 2 s at the start, and run `check_paddle.py` once to find the twist axis.

## Run

Use Terminal.app or iTerm2. The VS Code terminal loses macOS camera permission.

```bash
cd ~/Code/Projects/me193/PingPong
venv/bin/python check_paddle.py                    # check + calibrate the paddle -> paddle_calib.json
venv/bin/python check_paddle.py --haptics-only     # just feel the haptics (or --skip-haptics)
venv/bin/python pong.py                            # loads paddle_calib.json automatically
venv/bin/python pong.py --paddle keyboard --no-mqtt   # no hardware: space = flat swing, z/x = twist left/right
venv/bin/pytest tests
```

Watch the score arrive: `mosquitto_sub -h test.mosquitto.org -t 'ME193/Rogers/Sam' -v`, or `MQTTIntro/listen.py` with its topic changed.

Game flow:
1. Show a level tag.
2. Hold the paddle still for 2 s while the swing threshold is calibrated.
3. A 3-2-1 countdown, then the rally.
4. After a miss, the ball is served again 1.2 s later.

Keys: `q` quit, `c` recalibrate, `p` pause, and `1`/`2`/`3` choose a level when you don't have the printed tags.

**Tag cards:** print [`tags/tags.pdf`](tags/tags.pdf) at 100% / Actual size, not Fit to page. It has 4 Letter pages: 0 pause, 1 easy, 2 medium, 3 hard, each 14 cm. Run `venv/bin/python make_tags.py --size-cm N` to remake them at another size. No printer? Open `tags/tagN.png` full-screen on your phone and hold that up instead, with the brightness turned up.

Useful flags:
- `--hand left`
- `--reach 0.5`: less arm movement is needed to cross the court.
- `--haptic-motor right`: if the weight is on the other output.
- `--k`, `--min-threshold`: swing sensitivity.
- `--topic ...`: test on a private topic first.
- `--no-haptics`, `--no-rumble` (keeps the contact and miss haptics)
- `--card-color/--card-serial`: default to the team's card, orange 0994.

## Building the paddle

- Make a beam handle on the Double Motor body so it's held like a paddle.
- Put a short axle on **one** motor output (left by default) with a beam or gear fixed **off-center**. When it spins, the imbalance shakes the paddle, the same way a phone's vibration motor works. Keep it clear of your fingers.
- If the motor outputs seem to make the gyro noisy during a rumble, raise `--k`. The swing threshold is calibrated while the motor is still.

## Still to check on the hardware

- **Gyro units.** The library gives raw int16 values with undocumented units. The threshold is calibrated relative to rest, so the units don't matter much, but `--min-threshold 50` is a guess. Run `check_paddle.py` to see the resting and swinging values.
- **IMU rate.** It's requested at 20 ms intervals. `check_paddle.py` prints the rate actually achieved.
- **Haptic feel.** The constants at the top of `paddles.py` are starting points to tune by feel: rumble tick 30 ms at 35%, contact kick 2 × 45 ms, sweet spot 2 × 30 ms, miss 3 × 180 ms. A 30 ms tick at 35% may be too weak to spin the weight at all; if so, raise `TICK_SPEED`.
- **Twist axis.** It depends on how the Double Motor is mounted in the handle, and it usually doesn't line up with a single gyro axis. On Sam's mount (buttons down, top facing forward), it came out between y and x. `check_paddle.py` step 2 records a few twists, takes the main direction of the motion (PCA) as the twist axis, and takes its sign from the first move (the twist to the right). It saves the result to `paddle_calib.json`, which `pong.py` loads. Spin = (gyro · axis) / |gyro| at the swing's peak.
- **Timing window.** If good swings register as late, increase `SWING_LATE` in `game.py`.

## Why the Double Motor and not the UNO Q

Both were options for the paddle:

| | LEGO Double Motor (used) | UNO Q + IMU |
|---|---|---|
| IMU | Built in, streamed over BLE | External I2C IMU read by the STM32 sketch |
| Link to the laptop | Direct BLE, roughly 20–50 ms | Board → MQTT broker → laptop, roughly 100–300 ms. Tufts Wi-Fi blocks laptop↔board traffic, but both can reach the broker |
| Swing timing | Tight window | Needs a wider window or timestamps to absorb broker latency |
| Haptics | Spare motor output with an off-center weight | Vibration motor driven by the Maker Drive (MX1508) |
| Power | Built-in battery, wireless | USB-C power bank |
| Code | Python on the laptop only | An App Lab app: sketch, Bridge, and Python plus an MQTT relay |

The Double Motor already has the IMU, the battery, the radio and a motor in one package. That makes it a better paddle with less code and less lag. The UNO Q's extra flexibility (any sensor, LED matrix) doesn't buy much here.

## Files

- `pong.py`: main loop, state machine (`WAIT_TAG → CALIBRATE → COUNTDOWN → RALLY ⇄ PAUSED`), rendering, MQTT scoreboard.
- `game.py`: pure game logic (ball, levels, hit rule, streak/record). Tested in `tests/test_game.py`.
- `swing.py`: swing detection from gyro magnitude. Tested in `tests/test_swing.py`.
- `vision.py`: pose wrist tracker, AprilTag reader, camera opener (from CustomRobotCentering).
- `paddles.py`: `LegoPaddle` (IMU sampling and haptics) and `KeyboardPaddle` (no hardware).
- `check_paddle.py`: IMU check, twist-axis finder and haptics check.
- `make_tags.py` → `tags/`: the printable AprilTag cards.
- `mqttlib.py`: copy of the class MQTT wrapper.
- `venv/` (Python 3.14) and `requirements.txt`. The pose model downloads to `models/` on first run.
