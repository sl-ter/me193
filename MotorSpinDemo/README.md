# Motor Spin Demo — 9/10

First LEGO Education hardware exercise: connect to a single motor and spin it.

- `spin_motor.py` — connects to a Single Motor via a Connection Card (color + serial), spins it clockwise at 50% speed for 3 seconds, then disconnects. Uses the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library (see root `requirements.txt`).

## Before running

Update these two lines in `spin_motor.py` to match your actual Connection Card:

```python
card_color = le.LEGO_COLOR_AZURE
card_serial = '3683'
```

## Run it

From the repo root, with the venv active (see root [README](../README.md)):

```bash
python MotorSpinDemo/spin_motor.py
```
