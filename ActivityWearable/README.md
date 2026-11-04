# Activity wearable — 10/26

A wearable built from the UNO Q and an MPU-6050 IMU (GY-521 breakout) that tells **standing still, walking, running and air-biking** (lying on your back) apart. It has two models, and no neural nets:

1. **Model 1** uses only the peak acceleration along one axis.
2. **Model 2** uses all six IMU outputs.

Three classmates each try one activity live, so the models are trained on several people and tested on a person they haven't seen. The full plan lives in the Obsidian note `me193; ActivityWearable` (rubric, model choices, data plan, assembly steps).

Status: **3 people recorded, both models trained** (2026-10-26). Held out (each person tested by a model trained on the others): **Model 1 80%, Model 2 99%**. **Live mode works:** the board classifies every 0.5 s and `dashboard.html` shows both models side by side.

**Week 2 (11/2): a neural-net step counter.** The assignment: *"extend your walker to now count your steps using a neural net and PyTorch. Use every sensor you can to make it as accurate as possible."* An iPhone in the left front pocket is the second sensor; a small 1D convolutional network, trained in PyTorch on footstrikes an observer taps in by hand, counts the steps; last week's hand-tuned stride rule is gone from the board. See [Step counter](#step-counter-neural-net--112). Status: **built and tested on synthetic data; no tap-mode recordings yet, so no trained net or real results yet.**

## Hardware and wiring

The UNO Q sits in its 3D-printed case with the GY-521 mounted on it. Both go in a sock-sleeve pocket on the **front of the lower shin**. A power bank in a front pocket powers it over USB-C.

| GY-521 | UNO Q | Where on the UNO Q | Colour |
|---|---|---|---|
| VCC | 3.3V | power header | red |
| GND | GND | digital header, past AREF | black |
| SDA | SDA | digital header, 2nd from the end | blue |
| SCL | SCL | digital header, end pin | yellow |
| XDA, XCL, AD0, INT | (not connected) | | |

- **Jumpers:** male-to-female.
- **Address:** AD0 is pulled low on the GY-521, so the address is 0x68.
- **Which bus:** the header's SDA/SCL pins are `Wire` in this core. The scan found the IMU there. `Wire1` and `Wire2` are empty.

## How to wear it (orientation)

- The UNO Q's components face out, and its **USB-C port points up, toward the knee**.
- The GY-521's components face out (its back with the MPU-6050 printing goes against the case), with its **printed Y arrow pointing the same way as the USB-C port**.

| Axis | Points |
|---|---|
| +Y | up the shin, toward the knee |
| +Z | forward, out of the shin (the planned Model 1 axis) |
| +X | toward the wearer's left |

- Standing still should read **ay ≈ +1 g, ax ≈ 0, az ≈ 0**. At rest, an accelerometer reads +1 g on whichever axis points up.
- If the printed X arrow points to the wearer's right, the GY-521 is facing backwards.

## `unoq/imu-check/`: bench check

An App Lab app for checking the wiring and axes.

**Sketch** (`sketch/sketch.ino`) offers three calls over the Bridge, all `provide_safe` so the I2C calls all run on the loop thread:

| Call | What it does |
|---|---|
| `i2c_scan()` | scans `Wire`, `Wire1` and `Wire2` |
| `imu_setup()` | finds the MPU-6050, resets it, sets ±16 g, ±2000 °/s, a ~44 Hz low-pass filter and 100 Hz sampling, and reads `ACCEL_CONFIG` back to confirm |
| `imu_read()` | returns one raw reading as text: `ax,ay,az,temp,gx,gy,gz` |

**Python** (`python/main.py`) prints:
- the scan and setup results
- how long one Bridge round trip takes
- a reading 5 times a second, in g and °/s, with which axis is up

Run it and watch it live:

```bash
python3 tools/deploy.py ActivityWearable/unoq/imu-check
python3 tools/deploy.py --cmd "arduino-app-cli app logs /home/arduino/ArduinoApps/imu-check --follow"
```

Ctrl+C stops watching (the app keeps running). The board runs one app at a time, so this stops BoardStatus: the IP stops scrolling on the LED matrix until the next reboot.

Then turn it until each axis points at the ceiling in turn, and check `up` reads `+X`, `+Y` and `+Z`. The printed arrows point toward +X and +Y, and +Z points out of the component side.

### First run, 2026-10-26 (on the desk, before mounting)

```
I2C scan: Wire: 0x68 | Wire1: | Wire2:
IMU setup: Wire addr 0x68 WHO_AM_I 0x68 ACCEL_CONFIG 0x18 configured
Bridge round trip: 9.5 ms per reading (~106 readings/s)
acc g  x -0.04  y -0.73  z +0.66  |a| 0.99   gyro deg/s  x -1.6  y +2.4  z +1.7   up -Y   23.2 C
```

- **WHO_AM_I is 0x68.** That's what an MPU-6050 reports; many clone chips report something else.
- **The ±16 g setting stuck.**
- **At rest, |a| = 0.99 g.** The accelerometer's scale is right to about 1%.
- **The gyro reads 1–3 °/s while still.** That's normal MPU-6050 bias; subtract a still-period average before using it.
- **Bridge timing:** about 9.5 ms per call, so one call per sample can only just reach 100 Hz. The logger will sample on the STM32 and hand Python batches instead.

## Recording sessions

### Each time (board on the power bank, over Wi-Fi)

1. Plug the board into the power bank. BoardStatus starts on boot and scrolls the board's IP on the LED matrix. For the first minute after boot it may show the previous IP, until the once-a-minute update runs.
2. On the laptop, start the wearable app (about a minute, with logs at the end):
   ```bash
   cd ~/Code/Projects/me193
   UNOQ_HOST=<ip from the matrix> python3 tools/deploy.py ActivityWearable/unoq/activity-wearable
   ```
   When it's up, the matrix shows `OK` (or `E!` if the IMU isn't found).
3. Run the guided recorder (needs the root venv for paho-mqtt):
   ```bash
   source venv/bin/activate
   python ActivityWearable/record.py --person SL        # initials only
   ```
4. Afterwards, copy the sessions off the board, over Wi-Fi or by plugging into USB:
   ```bash
   UNOQ_HOST=<ip> python ActivityWearable/pull_data.py
   ```

### What `record.py` does

It runs the 11-step protocol in `common.py`: fit check, orientation check, a 10 s calibration stand, then two sessions each of standing (including lying still), walking, running and air-biking. That's about 5.5 min of recording per person.

For each step it:
1. shows what to do and how
2. runs a 5 s countdown, with a big number on screen
3. shows the time left (yellow for the last 10 s), live motion, and on-screen cues (e.g. "SWITCH: walk fast now" halfway through the slow-then-fast walk). There is no sound, so whoever holds the laptop calls the cues out.
4. sanity-checks the result: no missing samples, and roughly the right amount of motion for the activity. These are rough checks, not the model.

You can keep or redo each session.

Keys: Enter start/next, `r` redo, `s` skip, `b` back, `x` abort, `q` quit. `--start N` resumes at step N.

The board times each session itself and saves it to `data/` in its app folder, so a session finishes cleanly even if Wi-Fi drops. The laptop keeps:
- a copy of what arrived over MQTT, in `data/live/` (gitignored)
- a log of every session, in `data/session_log.csv`, with redone ones marked `discarded`

### `unoq/activity-wearable/`: the board app

- **Sketch:** samples the MPU-6050 at 100 Hz on its own clock into a 128-sample ring buffer.
  - Python drains it with `imu_batch()`, at most 7 samples per call. The Bridge's RPC buffer is 256 bytes (RPClite's `DECODER_BUFFER_SIZE / 4`), and a round trip is about 10 ms.
  - Each sample carries `seq`, a 10 ms tick count, so a gap in `seq` is a missed sample.
  - The sketch also draws the frames Python sends to the matrix: a countdown digit, the activity letter with a progress bar, and a check mark when saved.
- **Python:**
  - **Network:** MQTT on `broker.emqx.io`, under the `ME193/Sam/wear/` topic prefix:

    | Topic | Direction | Carries |
    |---|---|---|
    | `cmd` | laptop → board | commands |
    | `status` | board → laptop | state, twice a second |
    | `event` | board → laptop | `recording`, `saved`, `aborted`, `error` |
    | `imu` | board → laptop | live samples, 10 messages a second: every sample while recording, every 4th (25 Hz) otherwise |

  - **Files:** writes `data/<person>_<activity>_<time>.csv` in the app folder, which the container mounts as `/app`.
  - **CSV format:** two `#` header lines (person, leg, activity, label, rates, axes), the columns `t_s,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps`, and an `# end` line with the row, gap and drop counts.

### Live demo

1. Start the app as for recording (`UNOQ_HOST=<ip> python3 tools/deploy.py ActivityWearable/unoq/activity-wearable`). The board always classifies live; recording still works alongside it.
2. Open the dashboard:
   ```bash
   open ActivityWearable/dashboard.html
   ```
   It's one HTML file. It loads `mqtt.js` 5.10.1 from jsDelivr and connects to `wss://broker.emqx.io:8084/mqtt`, so it needs internet but no install. `dashboard.html?demo` shows made-up data for checking the layout without the board.

**What the board does:**
- Every 0.5 s it classifies the last 2 s with both models.
- Each answer shown is the most common of the last 3 (1.5 s), so it doesn't flicker. The board publishes them on `ME193/Sam/wear/live`.
- The LED matrix shows **Model 1's letter on the left and Model 2's on the right** (S/W/R/B).
- **Model 2 is the random forest.** The tree and KNN versions stay in `models.json` for comparison, and `{"cmd": "model2", "kind": ...}` on `.../cmd` can still switch the board. The dashboard has no switch, so it always shows exactly two models: Model 1 (decision tree) and Model 2 (random forest).

**What the dashboard shows:**

| Part | Shows |
|---|---|
| Model 1 card (decision tree) | its answer, the +Y peak on a gauge coloured by the 3 thresholds, and one sentence saying why |
| Model 2 card (random forest) | its answer, the forest's vote for each class, posture (upright vs lying, the tree's own split at 0.94 g), shin swing (gyro X std), and steps/min (the step net, last 5 s) or pedal rpm (gyro X's main frequency) |
| Banner | whether the models agree. When Model 1 says still and Model 2 says bike, it explains why one number can't tell them apart |
| Timeline | the last 60 s of answers, Model 1 and Model 2 |
| Signal chart | the raw +Y acceleration for the last 5 s, with the thresholds drawn on it |
| How far | the current stretch of activity: the step net's steps and a distance range for walk/run, duration for bike and still; how sure the net is (below); the last 5 stretches; height and calibration controls |
| Header | board rate, and whether the phone is streaming |

**Checked:**
- Replaying recorded sessions through the board's `Live` class gave about 0.6 ms per answer on the laptop. On slow air-biking, Model 1 said still 87/87 times and Model 2 said bike 87/87.
- The board publishes an answer every ~0.5 s, and the Model 2 switch round-trips.
- The dashboard was screenshotted with headless Chrome: live, demo, light/dark, and 390 px wide (no sideways scroll).

## How far (distance per stretch of activity)

**Steps:** counted by the neural net (see [Step counter](#step-counter-neural-net--112)). Until 2026-11-02 the board counted *strides* with a hand-tuned rule on the shin's forward swing (−gx past 120 °/s, re-armed below 40 °/s, ≥ 0.55 s apart) and doubled them. That rule is gone from the board; `train_steps.py` keeps a copy only to compare against the net. On the week-1 air-biking sessions it counts about 115 "steps" a minute, since every pedal turn looks like a stride.

**Stretches:** a stretch ("bout") is a run of the same Model 2 answer.
- It ends only when a different answer holds for 2 answers in a row (1 s), so a flicker at a hallway turnaround doesn't split a walk.
- `.../live` carries the current stretch (label, duration, steps), `steps_total`, `step_rate_spm`, and the last 6 stretches. `.../bout` gets each one as it ends.

**How sure the net is (dashboard, walk/run):** each counted step is a peak in the net's output, and how far the peak clears the threshold says how sure it was.
- **Unsure:** a counted step peaking under threshold + 0.2 (`steps.UNSURE_MARGIN`). **Near miss:** a peak just under the threshold (within 0.05, `NEAR_MARGIN`), not counted. The board counts both per stretch (`unsure`, `near_miss` in each bout) and publishes the last 10 steps' mean peak (`step_peak_recent`).
- The dashboard shows a bar of clear / unsure / near-miss steps and "likely steps − unsure to steps + near misses" for the current walk or run, or the last one once you stop (each finished walk/run also gets its likely range in the recent-stretches table), plus the held-out median and 90th-percentile count error (`count_err_p90_pct` in `steps_model.json`, 13.5%).
- **Checked on the training recordings** (the final net, so a little flattering): counted steps peaking at 0.5–0.6 were on a tap 45% of the time, 0.6–0.7 79%, 0.7 and up 96–99%. Uncounted peaks at 0.45–0.5 were steps 40% of the time, lower ones never. Not yet checked held out.

**Distance (dashboard):** steps × step length, shown as a range.
- Step length isn't measured. Without calibration it uses rough rules of thumb: step ≈ 0.37–0.45 × height walking and 0.5–0.8 × height running (half of last week's stride ratios). If no height is entered, 155–195 cm is assumed. The net's own held-out count error (which the board reports from `steps_model.json`) is added on top; 10% until there is one.
- These ratios aren't from a source I could verify. Step length does scale with height, but published ratios vary; treat them as heuristics.
- **Calibrate** to narrow it: pick walk or run, enter a measured distance, press Start, cover the distance, press Stop. The step length comes out as metres ÷ steps, and the range becomes about ±8% plus the counting allowance.
- Height and calibration are saved in that browser (localStorage). Calibrations from week 1 were per stride, so they don't carry over.
- Air-biking and standing show only their duration (and any steps counted, which should be 0).
- **Known limits:**
  - steps come out about 1.3 s late and the activity about 1.5 s late, so a stretch's first step or two can land in the one before
  - a calibration only holds for that person and about that pace

## Step counter (neural net) — 11/2

**Sensors.** Everything the hardware has:
- **Shin:** the MPU-6050's 3 accelerometer and 3 gyro axes, as last week. (Its temperature sensor is read and dropped; it doesn't change with steps.)
- **Phone:** an iPhone in the **left** front pocket, so the net sees both legs. The shin mostly sees its own leg: during walks, its signal repeats once per stride, not once per step (autocorrelation 0.6–0.7 at one stride vs 0.1–0.3 at half a stride). The phone sends its accelerometer (including gravity) and gyro at about 60 Hz.
- The lab drawer has an MSA311 accelerometer (no gyro) but no second MPU-6050; the phone is better and needs no wiring between the legs.

**The phone page** (`phone/index.html`, served by GitHub Pages at <https://sl-ter.github.io/me193/ActivityWearable/phone/>, because iPhones only give motion data to https pages):
- Start → allow motion → **Pocket mode** (black screen that ignores touches; hold 2 s to leave). The screen must stay on: Safari stops the sensors when the page isn't showing, so it asks for a wake lock (or set Auto-Lock to Never).
- Publishes `ME193/Sam/wear/phone`, 10 messages a second: `{"id": page, "n": batch, "s": [[phone ms, ax, ay, az, gx, gy, gz], ...]}` in g and °/s, phone axes.
- Shows whether the board hears it (it reads the board's `status`).

**Putting the phone on the board's clock** (`main.py`, class `Phone`): arrival time − phone time = clock difference + network delay, so the smallest value over the last 20 s is the clock difference plus the quickest delivery. Samples are placed at phone time + that, i.e. late by at most the quickest delivery. In the simulation below that was a steady +61 ms (±1 ms). The same thing happens while recording and live, so the net trains on what it sees live.

**Orientation-free phone inputs** (`python/steps.py`, `inputs()`): every pocket holds the phone differently, so gravity is estimated as its average acceleration over the surrounding second, and the net gets: *up* (acceleration along gravity − 1 g), *side* (size of the acceleration across it), *turn* (rotation about the vertical), *swing* (size of the rotation about horizontal axes: the thigh swinging), and *phone-on*. Plus the shin's 6 axes and |a|: 12 channels.

**Patchy Wi-Fi** (fixed 2026-11-02 after the first real run lost sessions): the board's Wi-Fi drops now and then when it's worn (a body blocks 2.4 GHz well, and it has to roam between access points down a hall).
- **What went wrong:**
  - The record command or the board's replies were sometimes lost, so `record.py` sat on GO and aborted after 4 s (two sessions cut off at about 400 rows), or never logged a session the board did save.
  - Last week's reconnect code called paho's `loop_stop()` on the main loop. With no Wi-Fi, that waited for a stuck connect, and the board stopped reading the IMU (1757 samples lost mid-walk).
- **Fixes:**
  - Commands and events are sent with QoS 1.
  - The board ignores a repeated record command.
  - Reconnects run in their own thread, with backoff (8, 16, 32 s).
  - `record.py` resends the command until the board's status shows it, and takes the start time from the status or the event. It never aborts on its own. If the "saved" message never comes, it offers to keep the session: the board's copy comes over with `pull_data.py`.
  - The taps are saved with the board's seq numbers, and the board's CSV `# end` line now carries `first_seq` to line them up.
- **Tested** against a scripted fake board (normal, first command lost, events lost) and in the board simulation (duplicate command, and a reconnect whose `loop_stop()` hangs for 5 s: 0 drops).
- **Also seen once:** after a Wi-Fi deploy, the sketch stopped answering (`Bridge error: Request 'imu_status' timed out`) until a second deploy reflashed it. If `record.py` shows the IMU missing or 0 Hz, deploy again, and check the GY-521 jumpers.

**Ground truth: tap mode** (`record.py`). While a session records, the observer presses **f** at every left footstrike and **j** at every right one (space if unsure). Each tap is put on the board's clock the same way as the phone (from the arrival times of the board's live samples) and saved as `data/<session>_taps.csv` (`t_s,foot`, the same `t_s` as the session CSV). The board's `saved` event now carries `first_seq` so the two line up exactly.

**Step protocol** (`common.STEP_PROTOCOL`, the default; `--protocol activity` gives week 1's): fit (wearable + phone), orientation, phone check, then 10 timed sessions, all tapped, about 5 min of recording:

| Session | Label | s | Why |
|---|---|---|---|
| calib_stand | still | 10 | zero steps |
| walk_normal | walk | 40 | the basic case |
| walk_counted | mixed | 30 | walk exactly 30 steps counting out loud, then stand: checks the taps (record.py flags a mismatch) |
| walk_turns | walk | 40 | turns every 5–6 steps |
| walk_stopstart | mixed | 40 | 2–8 steps, stop, repeat |
| fidget | mixed | 30 | weight shifts, foot taps, turning on the spot: what *isn't* a step |
| stairs | walk | 40 | skippable |
| run_easy / run_fast | run | 30 / 20 | |
| bike_fast | bike | 30 | zero steps (the old rule's worst case) |

"mixed" sessions have no single activity, so `train.py` leaves them out of the activity models. Week 1's still and bike sessions also count as zero-step sessions for the net (no taps needed).

**The network** (`train_steps.py`; drawn in `figures/steps_network.png`):
- 12 channels → 4 dilated 1D convolutions (9 taps each, spaced 1, 2, 4, 8 samples apart, 16 channels, ReLU) → 1 output: the probability that a foot hit the ground at that sample. About 8.7k weights. Each output sees 0.6 s either side (1.1 s with the phone's gravity average), so steps come out about 1.3 s late.
- Trained to output a narrow bump (σ = 40 ms) at every tap; loss = binary cross-entropy, weighted up near taps. Adam, 25 epochs × 100 batches of 64 random 4 s crops.
- Augmentation: the phone hidden 30% of the time (so it still counts without one), the shin sensor tilted up to 10°, time stretched ±10% (cadence), amplitudes ±15%, the phone's clock shifted ±50 ms, noise.
- Steps = peaks above a threshold, ≥ 0.2 s apart. The threshold is picked on people the net hadn't seen: the folds' held-out output (closest totals, with and without the phone). Each fold's own threshold comes from the *other* folds, so the person it's tested on plays no part in it. The board's net uses the best one over all of them (0.50).
- Evaluated leave one person out, like last week: count error per session, false steps per minute in zero-step sessions, and F1 of found steps vs taps (within 150 ms). Three ways: the net with the phone, the net with the shin only, and last week's rule × 2.
- Everything is compared on the part of each recording the net can count: its output starts 1.1 s in and stops 1.1 s before the end (it needs context either side). Live, the stream has no edges. Counting the whole recording put 110 of the 2110 taps out of the net's reach.

**On the board:** `main.py` feeds every shin and phone sample to `steps.StepCounter`, which runs the exported net (`python/steps_model.json`) in numpy every 0.25 s. "Trained in PyTorch, run in numpy": training is where PyTorch is needed; running the net is just its multiplications, so the board doesn't need the big PyTorch install. `train_steps.py` checks the numpy version matches PyTorch and that the live counter finds exactly the steps that counting a whole recording at once does.

**Results (2026-11-03): 6 people, held out.** 70 sessions: 37 tapped (2110 taps) from BANJO, DHRUV, MAYA, RUBYA and SL, plus zero-step ones (TEOROM and week 1's still and bike sessions). Every phone session had the phone.

| | count error, median per session | total error | false steps / min, air-biking | F1 (steps within 150 ms of a tap) |
|---|---|---|---|---|
| **Net, shin + phone** | **2.0%** | 4.3% | **0.35** | 0.94 |
| Net, shin only | 2.9% | 4.2% | 0.35 | 0.94 |
| Last week's rule × 2 | 2.6% | 3.3% | 106 | – |

- By activity (median per session, net + phone vs the rule): walking 1.5% vs 1.6%, stop-start/counted walks 3.3% vs 6.7%, running 1.3% vs 2.1%. Standing: 0 false steps for all three.
- The net's real win is what *isn't* a step: the rule counts every pedal turn as a stride.
- The phone helps most on walks (3.0% → 1.5% median).
- Per person (net + phone vs taps): BANJO +1.1%, DHRUV −8.5%, MAYA +5.9%, RUBYA +1.1%, SL +1.4%. All together: 2006 steps vs 2000 taps (the rule: 2010).
- **Where it misses:** gaits unlike the training people's. BANJO's stop-start walk was slow, short shuffling steps with no real stops (shin swings −100 to −200 °/s; DHRUV's are −300), and the first half of BANJO's stairs was similar. The data itself is clean (0 gaps, 0 drops, no flat or zeroed stretches), so it isn't the wiring. More varied training data (slow, short steps) is the fix.
- **Two corrections on the way** (2026-11-03), worth keeping in mind:
  - Counting whole recordings made the net look 5% short: the taps in each recording's first and last 1.1 s are outside its output. Fixed by comparing all three methods on the same span.
  - A threshold tuned on the net's own training people came out 0.60 on every fold: the net is surer of people it has seen, so it missed steps on new ones (DHRUV 308 vs 375 taps). Picking it on held-out output gives 0.45–0.50 and the numbers above.
- Checks: numpy vs PyTorch 6.9e-09; the live `StepCounter` finds the same steps as the whole-recording count (within 1 sample) on 4 sessions.

**Before the real data** (2026-11-02): a synthetic pipeline test (fake taps from the old rule, a fake phone from the shifted shin signal), the real `main.py` in a simulation (fake Bridge and MQTT, simulated clock), and headless-Chrome screenshots of the phone page and dashboard. They checked the plumbing, not the accuracy.

**Training timelapse** (`timelapse_steps.py` → `figures/steps_timelapse.json`, played by `timelapse.html`): re-trains BANJO's fold exactly as `train_steps.py` does (same seed and sessions) and snapshots it 283 times over its 2500 updates, densely at first. Each snapshot has both losses (augmented training clips and BANJO's real recordings), the steps it counts on each of BANJO's sessions, and its output over 8 s of four of them (walk, stairs, fast run, air-bike). The last frame equals BANJO's line in `train_steps.py`'s output (372 steps vs 368 taps).
- One finding from it: BANJO's held-out loss is lowest at update 110 (1.52) and drifts up after (1.88 at the end), while the training loss keeps falling and the count barely changes. The net gets more confident in peak shapes it learned from the five others, without counting a new person any better.
- Open it at <https://sl-ter.github.io/me193/ActivityWearable/timelapse.html>, or locally with `cd ActivityWearable && python -m http.server 8000` → <http://localhost:8000/timelapse.html> (browsers won't load its data from a file opened directly).

**Run it:**
```bash
source venv/bin/activate
python ActivityWearable/record.py --person SL        # step protocol, tap mode
UNOQ_HOST=<ip> python ActivityWearable/pull_data.py  # sessions + _phone.csv files
python ActivityWearable/train_steps.py               # ~3 min per person on a laptop CPU (~25 min for 6)
python ActivityWearable/timelapse_steps.py           # after train_steps.py: the timelapse's data, ~5 min
UNOQ_HOST=<ip> python3 tools/deploy.py ActivityWearable/unoq/activity-wearable   # ships steps_model.json
```
torch 2.14.1 is now in the root `requirements.txt`.

| Figure | Shows |
|---|---|
| `steps_example.png` | a held-out walk: shin gx, phone swing, the net's output with the taps and the steps it found, and the old rule's strides |
| `steps_comparison.png` | count error per activity and false steps per minute when still or biking: net + phone vs net, shin only vs the old rule |
| `steps_network.png` | the network as a diagram |
| `steps_results.json` | every number, per session, and each fold's threshold |
| `steps_timelapse.json` | the timelapse's snapshots (for `timelapse.html`) |

## Network notes (2026-10-26)

- **Registration:** Tufts_Wireless only gives the board internet once its MAC is registered (`14:b5:cd:f7:fd:9b`; the `B6:28:…` address in older notes was a randomized one). Until then every connection is redirected to `device-registration-prod-04.it.tufts.edu`.
- **The broker:** `test.mosquitto.org:1883` (the class default) times out from both Tufts_Wireless and Tufts Secure. `broker.hivemq.com` worked, but it stalled for 5–9 s on 3 of 8 connects, from both the laptop and the board. `broker.emqx.io` connected in about 0.4 s on 8 of 8 from both, so this project uses EMQX.
- **"The dashboard goes offline after a while":** the board's Wi-Fi drops for about 2 s now and then (once per boot in the logs), and it switches access points as you walk down the hall. That can leave the MQTT connection open but dead. Two fixes:
  - **A self-check:** the board listens for its own status on `.../status`. If none has come back for 8 s, it reconnects (`mqtt_watchdog`).
  - **Faster dead-connection detection:** a 15 s keepalive and 1–5 s reconnect retries.
  - Tested on the laptop against the real broker, on a separate topic: cutting off its messages makes it reconnect after about 8 s, and it recovers as soon as messages flow again.
- **Unreadable app log:** pulling the power while Docker is writing can corrupt the container log (`docker logs` then fails with `invalid character '\x00'`). Fix: `arduino-app-cli app stop ...`, then `docker rm activity-wearable-main-1`, then deploy again.
- **SSH and deploy over Wi-Fi:** the laptop on Tufts Secure can reach the board on Tufts_Wireless, so `deploy.py` and `pull_data.py` work over Wi-Fi with `UNOQ_HOST`.
- **The board's clock isn't NTP-synced** (it reads 1 Oct), so each session's start time in the file comes from the laptop.

## Training and results

```bash
source venv/bin/activate
python ActivityWearable/train.py
```

What `train.py` does:
- Cuts every kept session into **2 s windows, one every 0.5 s**, after dropping 3 s at each end (1 s for the 10 s calibration).
- Scores every model **leave-one-person-out**: train on two people, test on the third, then rotate. That's the demo situation, a person the model has never seen.
- Writes `figures/` and `unoq/activity-wearable/python/models.json`, which holds the final models trained on everyone.
- Checks that the board's numpy-only runner (`classify.py`) gives the same answers as scikit-learn. It does: 100% match for every model.

Results, 2026-10-26: 1569 windows from SL, TEOROM and MAYA.

| Model | Input | Held-out accuracy | Per person |
|---|---|---|---|
| **Model 1** | peak of **+Y** (along the shin, toward the knee) in each window, 3 thresholds | **80%** | MAYA 78, SL 85, TEOROM 77 |
| Model 2, decision tree (depth ≤ 4) | 31 features from all six IMU outputs | 95% | MAYA 100, SL 94, TEOROM 92 |
| **Model 2, random forest** (100 trees) | same | **99%** | MAYA 98, SL 100, TEOROM 100 |
| Model 2, KNN (k = 7, standardised) | same | 97.5% | MAYA 99, SL 98, TEOROM 95 |

**Model 1's thresholds on +Y:**

| +Y peak | Predicted |
|---|---|
| below 1.20 g | still |
| 1.20–1.71 g | bike |
| 1.71–3.69 g | walk |
| above 3.69 g | run |

**Choosing Model 1's setup:**
- **Direction:** all six directions were tried; +Y wins (Z, the original guess, gets 61%).
- **Tree shape:** a tree that grows its 4 regions best-first (`max_leaf_nodes=4`) beats a depth-2 tree (80% vs 74%), because the depth-2 tree spent two thresholds between walk and run and none on bike.

**Why Model 2 wins: bike.** Air-biking's +Y peaks (0.5–2.8 g) overlap standing still (about 1 g) and walking. So Model 1 gets bike right only 33% of the time: 44% of bike windows are called still and 24% walk. Its other mistakes are 10% of runs called walks (tall people's fast walks hit 7–9 g).

**Model 2's decision tree is readable** (`figures/model2_tree.png`). It asks 4 questions:

| Question | If yes |
|---|---|
| Is the shin barely swinging (`gyro_x_std` ≤ 45 °/s)? | still |
| Is the shin not vertical (`acc_y_mean` ≤ 0.94 g, i.e. lying down)? | bike |
| Is the shin leaning forward on average (`acc_z_mean` ≤ −0.44 g)? | run |
| Otherwise | walk |

**K-means** (`figures/kmeans.png`), with no labels at all, finds still and bike as clean groups. It splits running by speed instead of separating walk from run: walking and easy jogging end up in one group, fast running in another.

| Figure | Shows |
|---|---|
| `models_overview.png` | both models as one diagram: Model 1's 3-question tree, and Model 2's forest (3 real trees' first questions, then the vote). Drawn by `figure_models.py` from `models.json` + `results.json` |
| `model1_peaks.png` | every window's +Y peak by activity, with the 3 thresholds |
| `model1_directions.png` | Model 1's held-out accuracy for each of the 6 directions |
| `confusion.png` | Model 1 vs Model 2 (forest), held out |
| `model2_tree.png` | the 4-question decision tree |
| `model2_importance.png` | the forest's most-used features |
| `kmeans.png` | true activities vs k-means groups, on 2 principal components |
| `results.json` | every number above |

## Files

| Path | What it is |
|---|---|
| `common.py` | broker/topic settings, data paths, both recording protocols (`STEP_PROTOCOL`, `PROTOCOL`) |
| `record.py` | guided recording session (laptop), with tap mode for step sessions |
| `train_steps.py` | the step net: PyTorch training, leave-one-person-out comparison with the old rule, figures, `steps_model.json` |
| `timelapse_steps.py` | records one fold of the step net's training, snapshot by snapshot |
| `timelapse.html` | plays that back: the net's output, losses and counts over training |
| `phone/index.html` | the phone page (GitHub Pages), streams the iPhone's motion over MQTT |
| `pull_data.py` | copies sessions off the board into `data/` |
| `train.py` | windows, leave-one-person-out evaluation, figures, `models.json` |
| `figure_models.py` | draws `figures/models_overview.png` (run after `train.py`) |
| `dashboard.html` | live demo display (browser, MQTT over WebSockets) |
| `figures/` | the figures + `results.json` |
| `unoq/activity-wearable/` | the wearable's App Lab app (sketch + Python). `python/features.py` (windows + features) and `python/classify.py` (runs `models.json` with numpy only) are shared with `train.py`, and `python/steps.py` (the step net's inputs, numpy forward pass and live counter) with `train_steps.py`, so the laptop and the board compute everything identically |
| `unoq/imu-check/` | bench-check App Lab app (sketch + Python) |
| `data/` | recorded sessions + `session_log.csv`; step sessions also have `_phone.csv` (from the board) and `_taps.csv` (from the laptop) (`data/live/` is gitignored) |
