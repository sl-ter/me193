"""
Swing detection from gyro magnitude.

A swing is a fast rotation of the paddle, so |omega| = sqrt(gx^2 + gy^2 + gz^2)
spikes. The threshold isn't hard-coded (the Double Motor's raw gyro units
aren't documented): during calibration the player holds the paddle still,
and the threshold is set to the resting mean + K standard deviations, never
below min_threshold (or twice the resting mean) so a perfectly still sensor
doesn't make every twitch a swing.

The swing is reported on the rising edge (as soon as |omega| crosses the
threshold) so it reaches the game with as little delay as possible, and its
power (peak / threshold) keeps updating while the swing lasts.

Spin: alongside |omega| each sample can carry `twist`, the signed gyro
reading along the paddle's roll axis (nose pointed at the screen, rolling
right = clockwise as the player sees it). It's roll rather than yaw because a
swing is mostly yaw. pong.py projects the gyro onto the axis that
check_paddle.py measured. At the swing's peak, spin = twist / |omega|: the fraction of the
swing that was twist, in [-1, 1], with no units to worry about. A flat swing
is ~0, a swing that rolls the wrist hard to the right is close to +1.
"""

import math
import statistics

from game import Swing


def gyro_magnitude(gx, gy, gz):
    return math.sqrt(gx * gx + gy * gy + gz * gz)


class SwingDetector:
    def __init__(self, k=6.0, min_threshold=50.0, refractory=0.40):
        self.k = k
        self.min_threshold = min_threshold  # raw gyro units; see check_paddle.py
        self.refractory = refractory        # seconds before another swing can start
        self.threshold = None
        self._calib = []
        self._active = None                 # the Swing currently above threshold
        self._last_start = -math.inf

    # -- calibration ----------------------------------------------------------

    def start_calibration(self):
        self._calib = []
        self.threshold = None

    def add_calibration(self, mag):
        self._calib.append(mag)

    def finish_calibration(self):
        """Set the threshold from the resting samples. Returns it."""
        if len(self._calib) >= 2:
            mean = statistics.fmean(self._calib)
            std = statistics.pstdev(self._calib)
        else:
            mean, std = 0.0, 0.0
        self.threshold = max(mean + self.k * std, self.min_threshold, 2 * mean)
        return self.threshold

    # -- detection -------------------------------------------------------------

    def update(self, t, mag, twist=0.0):
        """Feed one sample. Returns a new Swing on its rising edge, else None.
        The returned Swing's power and spin keep updating until the peak."""
        if self.threshold is None:
            return None
        if self._active is not None:
            if mag >= self.threshold:
                if mag / self.threshold > self._active.power:
                    self._active.power = mag / self.threshold
                    self._active.spin = spin_fraction(twist, mag)
                return None
            self._active = None             # swing over
        if mag >= self.threshold and t - self._last_start >= self.refractory:
            self._active = Swing(t=t, power=mag / self.threshold, spin=spin_fraction(twist, mag))
            self._last_start = t
            return self._active
        return None


def spin_fraction(twist, mag):
    if mag <= 0:
        return 0.0
    return max(-1.0, min(1.0, twist / mag))


def find_twist_axis(gyros):
    """Work out the paddle's twist axis from a recording of the player
    twisting it to the RIGHT (then back) a few times.

    gyros: [(gx, gy, gz), ...] in time order. The motor body can sit at any
    angle in the handle, so the twist won't line up with one gyro axis. The
    axis is the direction the gyro vector swings along most: the principal
    component of the moving samples. A back-and-forth twist hits both signs,
    so the sign comes from the first strong movement, which is the twist to
    the right. Returns (unit 3-vector, purity), where purity is the share of
    the motion along that axis (1.0 = a perfectly clean twist).
    """
    import numpy as np

    g = np.asarray(gyros, dtype=float)
    if len(g) < 3:
        raise ValueError("not enough samples")
    mags = np.linalg.norm(g, axis=1)
    moving = g[mags >= 0.3 * mags.max()]
    if len(moving) < 2:
        raise ValueError("no clear movement")
    eigvals, eigvecs = np.linalg.eigh(moving.T @ moving)
    axis = eigvecs[:, -1]
    purity = float(eigvals[-1] / eigvals.sum())

    proj = g @ axis
    first = np.argmax(np.abs(proj) >= 0.5 * np.abs(proj).max())
    if proj[first] < 0:
        axis = -axis
    return tuple(float(v) for v in axis), purity
