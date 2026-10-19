# ME193 Robotics

Read [notes/session-log.md](notes/session-log.md) first — it's a running log of everything set up in this repo, kept because the class Claude accounts close Dec 10 and lose all conversation history.

## Conventions

- Lives at `~/Code/Projects/me193`. Everything for the class lives in this one folder, organized by assignment: each assignment gets its own folder, named after its subject rather than its date (e.g. `AprilTagCentering/`, `PoseRaceCar/`), with its own README.
- Shared stuff (venv, `requirements.txt`, root README, the session log) stays at the repo root — but only for assignments that don't have their own venv/deps. `PoseRaceCar/` is a fully separate git repo (own remote, shared with a partner) nested here just for filesystem organization; it's listed in `.gitignore` and has its own venv/requirements.txt. Don't run its deps through the root venv or vice versa.
- `venv/` is never committed (see `.gitignore`) — recreate it locally with `python3 -m venv venv && pip install -r requirements.txt` if missing. Note venvs aren't relocatable (hardcoded shebangs) — if a project folder moves, delete and rebuild its venv rather than trying to carry it along.
- After any meaningful change, append a new dated entry to `notes/session-log.md`.
- Headings read `Subject — Date`, not `Date — Subject` — e.g. an assignment README titles itself `# AprilTag centering — 9/22`, and a session-log entry heads itself `## Added Grayscale exercise — 2026-09-15`.

## UNO Q apps (Arduino App Lab)

Folders with an `app.yaml` (`ArduinoDisplay/`, `BoardStatus/`, and nested ones like `SumoWrestling/unoq/sumo-distance/`) are App Lab apps for the UNO Q (`UNOQ2`). They mirror `/home/arduino/ArduinoApps` on the board, but this repo is the master copy: the board's folder is not its own git repo. Deploy kit from Chris Rogers's `unoq-vscode-kit.zip` (class repo, `Public stuff/UNOQ code/`), see [tools/README.md](tools/README.md):

- `python/main.py` runs in a container on the board's Linux side; `sketch/` is the STM32 code. `arduino.app_utils` only exists on the board, so unresolved-import warnings locally are expected. Don't pip install it.
- Always go through `tools/deploy.py`, not raw `ssh`/`scp`. It tries USB (adb), then each address in `HOSTS` in `tools/board_secrets.py` (gitignored; the board's IP lives there).
  - `python3 tools/deploy.py <AppFolder>`: stop, copy up, start one app, show its first logs. Read them and fix errors before reporting back. Any path inside the app works; it deploys the nearest folder with an `app.yaml`, named after that folder.
  - `python3 tools/deploy.py --cmd "<command>"`: run anything on the board.
- Local folders are PascalCase but some board apps are kebab-case (`BoardStatus` → `board-status`); `BOARD_APP_NAMES` in `tools/deploy.py` maps them. Add a mapping for any app first created in App Lab, or deploying makes a duplicate app.
- Deploying copies but never deletes; remove renamed/deleted files on the board with `--cmd "rm ..."`. Edits made only on the board are overwritten by the next deploy. Pull App Lab–made apps down into this repo before editing them here.
- If deploy.py can't reach the board, stop and tell Sam. The board's current IP scrolls on its LED matrix (BoardStatus autostarts on boot). Tufts Wi-Fi can block laptop↔board traffic even on the same subnet.
