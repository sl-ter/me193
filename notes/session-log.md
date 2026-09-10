# Claude Session Log — ME193 Robotics

Running log of what's been set up via Claude Code, kept because the class Claude accounts close on **Dec 10** and everything else disappears. Read this at the start of a new session to catch up; append a new dated entry each time something meaningful changes.

## 2026-09-10 — Initial setup

**Machine state found:**
- Python 3.14.4 already installed via Homebrew (`/opt/homebrew/bin/python3`) — no fresh install was needed.
- `git` 2.50.1 already installed.
- `gh` (GitHub CLI) was NOT installed — installed via `brew install gh`, then authenticated with `gh auth login` (account: `sl-ter`).

**Repo created:** [github.com/sl-ter/me193-robotics-libs](https://github.com/sl-ter/me193-robotics-libs) (private)

Contents:
- `spin_motor.py` — single-motor demo using the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library (connects via a Connection Card's color + serial, spins clockwise at 50% for 3s). `card_color`/`card_serial` are placeholders — need to be updated to match the actual card in use.
- `requirements.txt` — generated via `pip freeze` inside the venv. Key package: `legoeducation==1.1.1` (pulled in `bleak`, `pyobjc-*` for Bluetooth on macOS).
- `README.md` — setup/usage instructions for anyone cloning the repo.
- `.gitignore` — excludes `venv/`, `__pycache__/`, `.DS_Store`.
- `venv/` — local virtual environment, intentionally **not** pushed to GitHub (per class instructions to not commit the venv).

**Not yet done (from the class daily plan):**
- Actually test `spin_motor.py` against real hardware with correct card color/serial.
- GitHub practice exercise: fork `chrisbuerginrogers/ME193-Robotics`, branch, edit `main.py`, PR, captain merges.
- Learn to create Claude skills and save them to GitHub/machine.
- Be prepared to take over paying for the Claude account (~$25/mo) after Dec 10.

**Reference links from class ("Getting Started with LEGO Hardware"):**
- LEGO Education Python library: https://github.com/LEGO/LEGOEducation
- Class practice repo: https://github.com/chrisbuerginrogers/ME193-Robotics

## 2026-09-10 — Restructured into single class repo, organized by day

Decided to keep everything for the whole class in one repo rather than one repo per topic/day.

- Renamed repo `me193-robotics-libs` → `me193-robotics` (via `gh repo rename`; local folder renamed to match, remote URL updated automatically).
- Moved `spin_motor.py` into a new `9-10/` folder (dated folder-per-day pattern going forward), added `9-10/README.md` with day-specific usage notes.
- Shared stuff (`venv/`, `requirements.txt`, root `README.md`, this log) stays at repo root since it applies across days.
- Updated root `README.md` to explain the folder-per-day structure and point into `9-10/`.

**Convention going forward:** new class sessions get their own `M-D/` folder (e.g. `9-17/`) with their own README; shared deps get added to the root `requirements.txt`; append a new dated entry here each session.
