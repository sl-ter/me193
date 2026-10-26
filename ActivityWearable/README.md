# Activity wearable — 10/26

A wearable built from the UNO Q and an MPU-6050 IMU (GY-521 breakout) that tells **standing still, walking, running and air-biking** (lying on your back) apart. It has two models, and no neural nets:

1. **Model 1** uses only the peak acceleration along one axis.
2. **Model 2** uses all six IMU outputs.

Three classmates each try one activity live, so the models are trained on several people and tested on a person they haven't seen. The full plan lives in the Obsidian note `me193; ActivityWearable` (rubric, model choices, data plan, assembly steps).

Status: **the IMU is wired up and bench-checked** (below). Next: mount it in the case and the sleeve, then the data logger.

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

## Files

| Path | What it is |
|---|---|
| `unoq/imu-check/` | bench-check App Lab app (sketch + Python) |
