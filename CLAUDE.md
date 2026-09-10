# ME193 Robotics

Read [notes/session-log.md](notes/session-log.md) first — it's a running log of everything set up in this repo, kept because the class Claude accounts close Dec 10 and lose all conversation history.

## Conventions

- Everything for the class lives in this one repo, organized by day: each session gets its own `M-D/` folder (e.g. `9-10/`, `9-17/`) with its own README.
- Shared stuff (venv, `requirements.txt`, root README, the session log) stays at the repo root.
- `venv/` is never committed (see `.gitignore`) — recreate it locally with `python3 -m venv venv && pip install -r requirements.txt` if missing.
- After any meaningful change, append a new dated entry to `notes/session-log.md`.
