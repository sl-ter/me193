# ME193 Robotics

Python code and libraries for ME193 (AI in Mobile Robotics), controlling LEGO Education hardware via the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library.

Everything for the class lives in this one repo (`~/Code/Projects/me193`), organized by assignment. Shared setup (venv, dependencies) lives at the root; each assignment gets its own folder.

## Structure

- `MotorSpinDemo/` — motor spin demo, day-one exercise (see its [README](MotorSpinDemo/README.md))
- `ImageMathExplorer/` — grayscale image conversion exercise (see its [README](ImageMathExplorer/README.md))
- `PDPositionTracker/` — PD position tracker, pulled from the class repo (see its [README](PDPositionTracker/README.md))
- `AprilTagCentering/` — AprilTag centering: car drives back and forth, stops centered on the webcam feed (see its [README](AprilTagCentering/README.md))
- `MQTTIntro/` — MQTT intro: publish/subscribe against the public `test.mosquitto.org` broker on the class topic `ME193` (see its [README](MQTTIntro/README.md))
- `SpectrogramClassifier/` — record 5 s of audio, show its spectrogram, and label the musical notes present (see its [README](SpectrogramClassifier/README.md))
- `WhistleWorldCup/` — whistle-controlled car for the World Cup: PyAudio pitch → drive commands, live signal/decision display, MQTT `start` and ball/goalie roles (see its [README](WhistleWorldCup/README.md))
- `SillyWalks/` — Q-learning a LEGO crawler to walk straight: IMU yaw-error bins × speed-differential actions, trained on the robot itself, with a simulator mode for practice (see its [README](SillyWalks/README.md))
- `CustomRobotCentering/` — YOLO green-minifig tracker (Chris Liang's Day 5 code, `ChrisLiang33/mobile-robotics`): the laptop camera finds the minifig and publishes its position over MQTT, and the UNO Q car (`mqtt-minifig-car`, already on the board) drives until it's centered (see its [README](CustomRobotCentering/README.md)). Has its own Python 3.11 `.venv` + `requirements.txt` (PyTorch/ultralytics), separate from the root venv.
- `PoseRaceCar/` — pose-gesture race car assignment. **Its own separate git repo** (shared with a partner, remote `Lucalo44/PoseRaceCar`), just nested here for local folder organization — it's gitignored by this repo, not tracked as part of it. It has its own venv; don't confuse it with the root one below.
- `ArduinoDisplay/` — Arduino App Lab app for an Arduino UNO Q: shows the current city and local weather on the 13x8 LED matrix (see its [README](ArduinoDisplay/README.md)). Not LEGO hardware like the rest of this repo, and has no Python deps beyond what App Lab's environment already provides, so it isn't in the root `requirements.txt`.
- `BoardStatus/` — second Arduino App Lab app for the same UNO Q: scrolls the board's real IP on the LED matrix (autostarts on boot), plus a standalone SSH-login dashboard with the richer CPU/memory/disk/network/process metrics (see its [README](BoardStatus/README.md)). Same "not LEGO hardware" caveat as `ArduinoDisplay/`.
- `PingPong/` — midterm: virtual ping-pong against a wall with the LEGO Double Motor as the paddle. MediaPipe pose places the paddle, the IMU detects swings, AprilTags pick the level, the record streak goes to MQTT `ME193/Rogers/Sam`, and the motor gives haptic feedback (see its [README](PingPong/README.md)). Has its own `venv` + `requirements.txt` (adds MediaPipe).
- `tools/` + `.vscode/tasks.json` — UNO Q deploy kit (from the class's `unoq-vscode-kit.zip`): open a file in `ArduinoDisplay/` or `BoardStatus/`, press Cmd+Shift+B, and pick Run on UNO Q / Python in UNO Q container / Terminal on UNO Q / Advertise UNO Q on Tufts WiFi (see [tools/README.md](tools/README.md)). The board's address goes in `tools/board_secrets.py` (gitignored, created on first run).
- `notes/session-log.md` — running log of Claude Code session context across the semester
- `requirements.txt` — shared dependencies for the assignments at this repo's root (not for `PoseRaceCar/`, `CustomRobotCentering/` or `PingPong/`, which have their own)

## Setup

```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate it
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate.bat     # Windows

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Usage

See each assignment's folder for its own README and instructions, e.g. [MotorSpinDemo/README.md](MotorSpinDemo/README.md).
