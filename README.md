# ME193 Robotics

Python code and libraries for ME193 (AI in Mobile Robotics), controlling LEGO Education hardware via the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library.

Everything for the class lives in this one repo, organized by day. Shared setup (venv, dependencies) lives at the root; each day's exercise gets its own dated folder.

## Structure

- `9-10/` — motor spin demo (see its [README](9-10/README.md))
- `notes/session-log.md` — running log of Claude Code session context across the semester
- `requirements.txt` — shared dependencies for the whole repo

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
