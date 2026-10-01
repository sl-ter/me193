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
- `PoseRaceCar/` — pose-gesture race car assignment. **Its own separate git repo** (shared with a partner, remote `Lucalo44/PoseRaceCar`), just nested here for local folder organization — it's gitignored by this repo, not tracked as part of it. It has its own venv; don't confuse it with the root one below.
- `ArduinoDisplay/` — Arduino App Lab app for an Arduino UNO Q: shows the current city and local weather on the 13x8 LED matrix (see its [README](ArduinoDisplay/README.md)). Not LEGO hardware like the rest of this repo, and has no Python deps beyond what App Lab's environment already provides, so it isn't in the root `requirements.txt`.
- `notes/session-log.md` — running log of Claude Code session context across the semester
- `requirements.txt` — shared dependencies for the assignments at this repo's root (not for `PoseRaceCar/`, which has its own)

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
