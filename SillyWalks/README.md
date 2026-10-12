# Silly Walks Q-learning — 10/6

A LEGO crawler (Double Motor, one arm per side) learns by trial and error
which speed correction keeps it crawling straight, using a Q-table: rows are
heading-error bins from the Double Motor's IMU yaw, columns are left/right
speed differentials, and each cell is learned from reward. Built from the
class handout's design (9 states, 5 actions, ±1/0 reward, α/γ/ε update).

## What "training" means here

Nothing gets trained on a computer and uploaded. **Training *is* the robot
crawling.** Every 0.5 s it:

1. reads its yaw error and puts it in a bin (the **state**, e.g. "+5..+10° = drifting right"),
2. picks a correction (**action**): random with probability ε (*explore*), otherwise the column with the highest number in that row (*exploit*),
3. runs the motors with that correction for one step,
4. reads the yaw again → the new state, plus a **reward** (+1 if within ±2°, 0 if within ±10°, −1 beyond),
5. nudges that one cell: `Q[s][a] ← (1−α)·Q[s][a] + α·(r + γ·max Q[s'])`.

Run that loop a few hundred times and the table *is* the learned policy:
for each heading error, which correction tends to lead back to straight.
ε starts at 1 (all random) and decays ×0.98 per step, so the robot gradually
switches from trying things to using what it has learned. The "trained
model" is just `qtable.json`, 45 numbers.

Note the learner never needs to be told which way is left. If the motors
or yaw were wired backwards, it would still learn the right corrections,
just under the wrong column names. `check_robot.py` only exists so the
labels and printouts make sense.

## Files

- `crawler.py` — hardware settings (card orange `0994`, `BASE_SPEED`, sign
  flips) and the two robots: `RealCrawler` (Double Motor over Bluetooth) and
  `SimCrawler` (a toy crawler that drifts right, for practice).
- `check_robot.py` — run first: checks the yaw axis/sign/units and that A0/A4
  turn the way their names say.
- `qlearn.py` — the training loop; also `--run` to just walk with the table.
- `plot_training.py` — on-target % per episode, ε, heading traces early vs
  late, and the Q-table as a heatmap.
- `lelib.py` — shared LEGO Education wrapper (same file as `PDPositionTracker/`).
- Generated: `qtable.json` (the learned table — commit this), `training_log.csv`
  (every step); the simulator writes `qtable_sim.json` / `training_log_sim.csv`
  instead so it never touches the robot's table.

Dependencies: all in the root `requirements.txt` (`legoeducation`, `matplotlib`).

## Run it

From the repo root with the venv active (`source venv/bin/activate`), `cd SillyWalks`:

```bash
# 0. See it learn without hardware (instant): it discovers the sim's rightward
#    drift and learns to hold a gentle left (A3) when on target.
python qlearn.py --sim --fresh --episodes 80
python plot_training.py --sim

# 1. Check the robot (turn it by hand, then three short test crawls)
python check_robot.py --drive

# 2. Train. Each episode: aim it straight, Enter, it crawls 30 steps (15 s)
#    or until it's 45° off. q + Enter to stop; the table is saved every
#    episode and the next run resumes from it.
python qlearn.py
python plot_training.py

# 3. Show it off: no exploring, no learning
python qlearn.py --run
```

`--fresh` throws away the saved table and log and starts over.

## Tuning, in order of likely need

- **The check comes first.** The Double Motor's yaw is rotation around
  whichever face is set as "up". If the motor is mounted on its side in the
  crawler, the default measures the wrong axis. `check_robot.py` shows
  yaw/pitch/roll live; set `YAW_FACE` in `crawler.py` accordingly. Also
  `YAW_SIGN`, `YAW_SCALE`, `FORWARD`, `SWAP_SIDES` there.
- **`STEP_TIME`** (in `qlearn.py`, 0.5 s): a crawler's heading wobbles
  within each arm stroke, so the reading depends on where in the stroke it
  lands. Aim for about one full arm revolution per step.
- **`BASE_SPEED` / `ACTIONS`**: if A0 vs A4 barely changes the heading in
  `check_robot.py`, the corrections are too small for the learner to tell apart.
- **ε decay**: 0.98 per step reaches the 0.05 floor after ~150 steps (~5
  episodes). If the table still has all-zero rows by then, those states were
  never visited; raise `EPS_DECAY` (e.g. 0.995) and/or train with `--fresh`.
- States 0 and 8 (more than 20° off) are rarely visited, because episodes end
  at 45°. That's fine.

In the simulator it reaches ~65–75% of steps on target. The rest is the
sim's random wobble (±1.5° per step) knocking it outside the ±2° band.
