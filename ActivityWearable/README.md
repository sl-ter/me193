# Activity wearable — 10/26

A wearable built from the UNO Q and an MPU-6050 IMU (GY-521 breakout) that tells **standing still, walking, running and air-biking** (lying on your back) apart. It has two models, and no neural nets:

1. **Model 1** uses only the peak acceleration along one axis.
2. **Model 2** uses all six IMU outputs.

Three classmates each try one activity live, so the models are trained on several people and tested on a person they haven't seen. The full plan lives in the Obsidian note `me193; ActivityWearable` (rubric, model choices, data plan, assembly steps).

Status: **3 people recorded, both models trained** (2026-10-26). Held out (each person tested by a model trained on the others): **Model 1 80%, Model 2 99%**. **Live mode works:** the board classifies every 0.5 s and `dashboard.html` shows both models side by side.

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
| Model 2 card (random forest) | its answer, the forest's vote for each class, posture (upright vs lying, the tree's own split at 0.94 g), shin swing (gyro X std), and steps/min or pedal rpm |
| Banner | whether the models agree. When Model 1 says still and Model 2 says bike, it explains why one number can't tell them apart |
| Timeline | the last 60 s of answers, Model 1 and Model 2 |
| Signal chart | the raw +Y acceleration for the last 5 s, with the thresholds drawn on it |
| How far | the current stretch of activity: distance range for walk/run, pedal turns for bike, duration for still; the last 5 stretches; height and calibration controls |

**Checked:**
- Replaying recorded sessions through the board's `Live` class gave about 0.6 ms per answer on the laptop. On slow air-biking, Model 1 said still 87/87 times and Model 2 said bike 87/87.
- The board publishes an answer every ~0.5 s, and the Model 2 switch round-trips.
- The dashboard was screenshotted with headless Chrome: live, demo, light/dark, and 390 px wide (no sideways scroll).

## How far (distance per stretch of activity)

**Strides (board, `main.py`):** every sample, the board watches −gx, the shin's forward swing.
- It counts a stride when −gx rises past 120 °/s, re-arms once it falls below 40 °/s, and never counts two within 0.55 s.
- On all 27 recorded sessions, the count was within a median 3% of each session's stride rate, and 0 on every still session.
- While air-biking, the same swing comes once per pedal turn.
- The 0.55 s gap fixed double counts on fast runs (39 → 34 strides). It caps counting at 1.8 strides a second (about 218 steps a minute).

**Stretches:** a stretch ("bout") is a run of the same Model 2 answer.
- It ends only when a different answer holds for 2 answers in a row (1 s), so a flicker at a hallway turnaround doesn't split a walk.
- `.../live` carries the current stretch (label, duration, strides), `strides_total`, and the last 6 stretches. `.../bout` gets each one as it ends.
- Replaying TEOROM's stand → walk → run → lie → bike sessions back to back gave 5 stretches. Their lengths matched the sessions to within about 2 s, with 36 / 58 / 32 strides (walk / run / bike).

**Distance (dashboard):** strides × stride length, shown as a range.
- Stride length isn't measured. Without calibration it uses rough rules of thumb: stride ≈ 0.74–0.90 × height walking and 1.0–1.6 × height running. If no height is entered, 155–195 cm is assumed. A ±5% allowance for counting error is added on top.
- These ratios aren't from a source I could verify. Step length does scale with height, but published ratios vary; treat them as heuristics.
- **Calibrate** to narrow it: pick walk or run, enter a measured distance, press Start, cover the distance, press Stop. The stride length comes out as metres ÷ strides, and the range becomes about ±8% plus the counting allowance.
- Height and calibration are saved in that browser (localStorage).
- Air-biking shows pedal turns (it goes nowhere), and still shows only its duration.
- **Known limits:**
  - each activity is recognised about 1.5 s late, so a stretch's first stride or two can land in the one before
  - turns and pace changes add error
  - a calibration only holds for that person and about that pace

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
| `common.py` | broker/topic settings, data paths, the recording protocol |
| `record.py` | guided recording session (laptop) |
| `pull_data.py` | copies sessions off the board into `data/` |
| `train.py` | windows, leave-one-person-out evaluation, figures, `models.json` |
| `figure_models.py` | draws `figures/models_overview.png` (run after `train.py`) |
| `dashboard.html` | live demo display (browser, MQTT over WebSockets) |
| `figures/` | the figures + `results.json` |
| `unoq/activity-wearable/` | the wearable's App Lab app (sketch + Python). `python/features.py` (windows + features) and `python/classify.py` (runs `models.json` with numpy only) are shared with `train.py`, so the laptop and the board compute features identically |
| `unoq/imu-check/` | bench-check App Lab app (sketch + Python) |
| `data/` | recorded sessions + `session_log.csv` (`data/live/` is gitignored) |
