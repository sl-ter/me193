# Activity wearable — 10/26

A wearable built from the UNO Q and an MPU-6050 IMU (GY-521 breakout) that tells **standing still, walking, running and air-biking** (lying on your back) apart. It has two models, and no neural nets:

1. **Model 1** uses only the peak acceleration along one axis.
2. **Model 2** uses all six IMU outputs.

Three classmates each try one activity live, so the models are trained on several people and tested on a person they haven't seen. The full plan lives in the Obsidian note `me193; ActivityWearable` (rubric, model choices, data plan, assembly steps).

Status: **assembled, and recording works end to end** (tested 2026-10-26: 500/500 samples, no gaps). Next: record Sam's protocol, then 3–5 other people.

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
  - **Network:** MQTT on `broker.hivemq.com`, under the `ME193/Sam/wear/` topic prefix:

    | Topic | Direction | Carries |
    |---|---|---|
    | `cmd` | laptop → board | commands |
    | `status` | board → laptop | state, twice a second |
    | `event` | board → laptop | `recording`, `saved`, `aborted`, `error` |
    | `imu` | board → laptop | live samples, 10 messages a second |

  - **Files:** writes `data/<person>_<activity>_<time>.csv` in the app folder, which the container mounts as `/app`.
  - **CSV format:** two `#` header lines (person, leg, activity, label, rates, axes), the columns `t_s,ax_g,ay_g,az_g,gx_dps,gy_dps,gz_dps`, and an `# end` line with the row, gap and drop counts.

### Network notes (2026-10-26)

- **Registration:** Tufts_Wireless only gives the board internet once its MAC is registered (`14:b5:cd:f7:fd:9b`; the `B6:28:…` address in older notes was a randomized one). Until then every connection is redirected to `device-registration-prod-04.it.tufts.edu`.
- **The broker:** `test.mosquitto.org:1883` (the class default) times out from both Tufts_Wireless and Tufts Secure, so this project uses `broker.hivemq.com`.
- **SSH and deploy over Wi-Fi:** the laptop on Tufts Secure can reach the board on Tufts_Wireless, so `deploy.py` and `pull_data.py` work over Wi-Fi with `UNOQ_HOST`.
- **The board's clock isn't NTP-synced** (it reads 1 Oct), so each session's start time in the file comes from the laptop.

## Files

| Path | What it is |
|---|---|
| `common.py` | broker/topic settings, data paths, the recording protocol |
| `record.py` | guided recording session (laptop) |
| `pull_data.py` | copies sessions off the board into `data/` |
| `unoq/activity-wearable/` | the wearable's App Lab app (sketch + Python) |
| `unoq/imu-check/` | bench-check App Lab app (sketch + Python) |
| `data/` | recorded sessions + `session_log.csv` (`data/live/` is gitignored) |
