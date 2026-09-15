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

## 2026-09-14 — Consolidated under ~/Code/Projects, added PoseRaceCar

Home directory was accumulating one loose folder per assignment at `~`. Moved everything for the class into a single parent folder, one subfolder per assignment.

- Renamed repo `me193-robotics` → `me193` on GitHub (`gh repo rename`) and locally; remote URL auto-updated.
- Moved the repo from `~/me193-robotics` to `~/Code/Projects/me193`.
- Deleted and rebuilt the venv post-move — venvs hardcode absolute paths in their `bin/` shebangs and don't survive being moved; rebuilding from `requirements.txt` is cheap and safe.
- Cloned the group assignment repo (`Lucalo44/PoseRaceCar` — pose-gesture LEGO race car, built with partner Luca) into `~/Code/Projects/me193/PoseRaceCar/`. It's a **separate git repo with its own GitHub remote**, nested here only for filesystem organization — added `/PoseRaceCar/` to this repo's `.gitignore` so it isn't tracked as part of `me193`. It has its own venv and `requirements.txt`, independent of the root ones.
- Pre-downloaded PoseRaceCar's MediaPipe pose model to `PoseRaceCar/models/` so it works without internet at race time.
- Found and fixed a macOS camera-permission issue running `PoseRaceCar/gesture_car_control.py`: the `kitty` terminal doesn't reliably propagate camera TCC permission to child processes (known kitty limitation) — Apple's Terminal.app does. Use Terminal.app (or iTerm2) for anything touching the webcam/mic; kitty is fine for everything else.
- `PoseRaceCar/gesture_car_control.py` has `CARD_COLOR`/`CARD_SERIAL` hardcoded (shared kit card with Luca) — intentional, not a placeholder to fix.
