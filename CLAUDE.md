# ME193 Robotics

Read [notes/session-log.md](notes/session-log.md) first — it's a running log of everything set up in this repo, kept because the class Claude accounts close Dec 10 and lose all conversation history.

## Conventions

- Lives at `~/Code/Projects/me193`. Everything for the class lives in this one folder, organized by assignment: each assignment gets its own folder (e.g. `9-10/` for a dated daily exercise, `PoseRaceCar/` for a named project) with its own README.
- Shared stuff (venv, `requirements.txt`, root README, the session log) stays at the repo root — but only for assignments that don't have their own venv/deps. `PoseRaceCar/` is a fully separate git repo (own remote, shared with a partner) nested here just for filesystem organization; it's listed in `.gitignore` and has its own venv/requirements.txt. Don't run its deps through the root venv or vice versa.
- `venv/` is never committed (see `.gitignore`) — recreate it locally with `python3 -m venv venv && pip install -r requirements.txt` if missing. Note venvs aren't relocatable (hardcoded shebangs) — if a project folder moves, delete and rebuild its venv rather than trying to carry it along.
- After any meaningful change, append a new dated entry to `notes/session-log.md`.
