"""UNO Q - Linux side. Bench check for the GY-521 (MPU-6050).

Scans the I2C buses, sets the IMU up (+-16 g, +-2000 deg/s, 100 Hz), times
the Bridge round trip, then prints a reading 5 times a second in g and deg/s,
plus which axis is pointing up. Watch it from the laptop with:

    python3 tools/deploy.py --cmd "arduino-app-cli app logs /home/arduino/ArduinoApps/imu-check --follow"
"""
import time

from arduino.app_utils import App, Bridge

ACC_LSB_PER_G = 2048.0      # MPU-6050 at +-16 g
GYRO_LSB_PER_DPS = 16.4     # MPU-6050 at +-2000 deg/s
PRINT_EVERY = 0.2           # seconds

ready = False


def setup_imu():
    print("I2C scan:", Bridge.call("i2c_scan"), flush=True)
    result = Bridge.call("imu_setup")
    print("IMU setup:", result, flush=True)
    if result == "not found":
        return False
    # How fast can Python pull single readings? Decides how the logger batches.
    n, start = 50, time.time()
    for _ in range(n):
        Bridge.call("imu_read")
    ms = (time.time() - start) / n * 1000
    print(f"Bridge round trip: {ms:.1f} ms per reading (~{1000 / ms:.0f} readings/s)", flush=True)
    return True


def up_axis(ax, ay, az):
    """The axis closest to straight up. At rest an accelerometer reads +1 g
    on whichever axis points up (it feels the table pushing it up)."""
    name, value = max((("X", ax), ("Y", ay), ("Z", az)), key=lambda p: abs(p[1]))
    return ("+" if value > 0 else "-") + name


def loop():
    global ready
    try:
        if not ready:
            ready = setup_imu()
            if not ready:
                time.sleep(2)
            return
        raw = Bridge.call("imu_read")
    except Exception as e:
        print("Bridge error:", e, flush=True)
        time.sleep(1)
        return
    if not raw:
        print("read failed (loose wire?)", flush=True)
        time.sleep(PRINT_EVERY)
        return
    ax, ay, az, t, gx, gy, gz = (int(v) for v in raw.split(","))
    ax, ay, az = ax / ACC_LSB_PER_G, ay / ACC_LSB_PER_G, az / ACC_LSB_PER_G
    gx, gy, gz = gx / GYRO_LSB_PER_DPS, gy / GYRO_LSB_PER_DPS, gz / GYRO_LSB_PER_DPS
    temp_c = t / 340.0 + 36.53   # MPU-6050 datasheet formula
    mag = (ax * ax + ay * ay + az * az) ** 0.5
    print(f"acc g  x {ax:+5.2f}  y {ay:+5.2f}  z {az:+5.2f}  |a| {mag:4.2f}   "
          f"gyro deg/s  x {gx:+7.1f}  y {gy:+7.1f}  z {gz:+7.1f}   "
          f"up {up_axis(ax, ay, az)}   {temp_c:4.1f} C", flush=True)
    time.sleep(PRINT_EVERY)


App.run(user_loop=loop)
