# ME193 Robotics

Python code and libraries for ME193 (AI in Mobile Robotics), controlling LEGO Education hardware via the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library.

Everything for the class lives in this one repo (`~/Code/Projects/me193`), organized by assignment. Shared setup (venv, dependencies) lives at the root; each assignment gets its own folder.

## Structure

- `9-10/` — motor spin demo, day-one exercise (see its [README](9-10/README.md))
- `9-15/` — grayscale image conversion exercise (see its [README](9-15/README.md))
- `9-17/` — PD position tracker, pulled from the class repo (see its [README](9-17/README.md))
- `PoseRaceCar/` — pose-gesture race car assignment. **Its own separate git repo** (shared with a partner, remote `Lucalo44/PoseRaceCar`), just nested here for local folder organization — it's gitignored by this repo, not tracked as part of it. It has its own venv; don't confuse it with the root one below.
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

See each day's folder for its own README and instructions, e.g. [9-10/README.md](9-10/README.md).
