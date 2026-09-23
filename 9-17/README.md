# PD Position Tracker — 9/17

Live PD-control demo, pulled from the class repo ([`chrisbuerginrogers/ME193-Robotics`, `Public stuff/Controls/`](https://github.com/chrisbuerginrogers/ME193-Robotics/tree/main/Public%20stuff/Controls)): a Single Motor acts as a hand-turned dial (the target), and one side of a Double Motor drives itself to match that dial's angle. Two on-screen sliders — Kp and Kd — let you change the controller's gains while it's running, so you can watch the effect on rise time, overshoot, and oscillation live on the plot.

- `pd_tracker.py` — the demo itself. Uses [`legoeducation`](https://github.com/LEGO/LEGOEducation) and `matplotlib` (both in root `requirements.txt`).
- `lelib.py` — shared LEGO Education wrapper (`singleMotor`, `doubleMotor`, `controller`, `colorSensor`) copied in from the class repo, same as its `useful libraries/` folder. Imported directly by `pd_tracker.py`.

## Before running

`CARD_COLOR`/`CARD_SERIAL` at the top of `pd_tracker.py` are set to this kit's Connection Card (orange, serial `0994`) — same card used for both the Single Motor and the Double Motor:

```python
CARD_COLOR = le.LEGO_COLOR_ORANGE
CARD_SERIAL = '0994'
```

## Run it

From the repo root, with the venv active (see root [README](../README.md)):

```bash
python 9-17/pd_tracker.py
```

## How it works

At every control-loop tick:

```
error  = target_position - actual_position
speed  = Kp * error - Kd * d(actual_position)/dt
```

`speed` (clamped to ±100%) is the only thing commanded — there's no separate "move to position" call, so everything on the plot comes from the P and D terms alone. The D term is "derivative on measurement": it damps the follower's own velocity, not the raw error's rate of change, so turning the dial by hand doesn't itself spike the D term (see the comment in `control_loop()` in `pd_tracker.py`).

Start with Kp around 1 and Kd at 0, then raise Kp until it oscillates, then raise Kd to damp it out. The terminal prints loop rate, error, and commanded speed every couple of seconds — useful for spotting when the motor is saturating at ±100%.

Closing the plot window stops the control loop and the Double Motor.
