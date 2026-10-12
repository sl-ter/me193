"""
The robot, seen from the learner's side: reset the heading, apply a
differential speed correction, read the yaw back. Two versions share that
interface -- RealCrawler (the LEGO Double Motor over Bluetooth) and
SimCrawler (a toy model of a crawler that drifts), so qlearn.py can't tell
which one it is driving.

Hardware settings live here; run check_robot.py to find the right values.
"""

import math
import random
import time

import legoeducation as le

# --- Hardware settings (verify with check_robot.py) -------------------------
CARD_COLOR = le.LEGO_COLOR_ORANGE
CARD_SERIAL = '0994'

BASE_SPEED = 50     # % speed both arms run at when the correction is 0
FORWARD = 1         # flip to -1 if BASE_SPEED on both sides crawls backward
SWAP_SIDES = False  # flip if A0 ("right turn") actually turns the robot left

# Which face of the Double Motor points UP on the robot. Yaw is rotation
# around that face, so if the motor is mounted on its side, the default
# (top) measures the wrong axis. None = leave the motor's default.
# Options: le.DEVICE_FACE_TOP, _BOTTOM, _FRONT, _BACK, _LEFT, _RIGHT.
YAW_FACE = None

YAW_SIGN = 1        # flip to -1 if turning the robot clockwise (from above) reads negative
YAW_SCALE = 1.0     # set to 0.1 if a 90-degree turn by hand reads ~900


def speeds_for(diff):
    """The handout's formula: the correction is split evenly, so the average
    speed stays at BASE_SPEED. diff > 0 = right side faster = turn left."""
    left = BASE_SPEED - diff // 2
    right = BASE_SPEED + diff // 2
    return left, right


class RealCrawler:
    def __init__(self):
        from lelib import doubleMotor
        self.dm = doubleMotor()
        print(f"Connecting to Double Motor (card {CARD_SERIAL})...")
        self.dm.connect(card_serial=CARD_SERIAL, card_color=CARD_COLOR)
        if YAW_FACE is not None:
            self.dm.imu_set_yaw_face(YAW_FACE)
        # yaw is NaN until the first IMU notification arrives
        deadline = time.monotonic() + 5
        while math.isnan(float(self.dm.imu_device.yaw)):
            if time.monotonic() > deadline:
                raise RuntimeError("Connected, but no IMU readings arrived from the Double Motor.")
            time.sleep(0.05)
        print("Connected.")

    def reset_heading(self):
        self.dm.imu_reset_yaw_axis(0)
        time.sleep(0.3)  # let a fresh IMU notification arrive

    def yaw(self):
        """Heading error in degrees: + = drifted right (clockwise from above)."""
        return YAW_SIGN * YAW_SCALE * float(self.dm.imu_device.yaw)

    def drive(self, diff):
        left, right = speeds_for(diff)
        if SWAP_SIDES:
            left, right = right, left
        self.dm.movement_move_tank(speed_left=FORWARD * left, speed_right=FORWARD * right,
                                   blocking=False)

    def stop(self):
        self.dm.movement_stop(blocking=False)

    def close(self):
        try:
            self.stop()
            time.sleep(0.2)
        finally:
            self.dm.disconnect()


class SimCrawler:
    """A crawler with a built-in rightward drift (one arm a bit stronger) and
    a wobble on every stroke. Corrections turn it by TURN_GAIN degrees/second
    per % of speed difference. Time is simulated, so training is instant.
    The learner is never told DRIFT -- it has to discover that a small
    left correction (A3) is what keeps it straight."""

    DRIFT = 6.0        # deg/s it veers right with no correction
    TURN_GAIN = 0.4    # deg/s per % of speed difference
    NOISE = 1.5        # deg of random wobble per step

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self._yaw = 0.0
        self._diff = 0

    def reset_heading(self):
        self._yaw = 0.0

    def yaw(self):
        return self._yaw

    def drive(self, diff):
        self._diff = diff

    def advance(self, dt):
        """Called instead of time.sleep(dt) to move simulated time forward."""
        rate = self.DRIFT - self.TURN_GAIN * self._diff
        self._yaw += rate * dt + self.rng.gauss(0, self.NOISE)

    def stop(self):
        self._diff = 0

    def close(self):
        pass
