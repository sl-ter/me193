import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swing import SwingDetector, gyro_magnitude  # noqa: E402


def calibrated(rest_level=10.0, noise=2.0, **kw):
    d = SwingDetector(**kw)
    d.start_calibration()
    rng = random.Random(0)
    for _ in range(100):
        d.add_calibration(rest_level + rng.uniform(-noise, noise))
    d.finish_calibration()
    return d


def test_magnitude():
    assert gyro_magnitude(3, 4, 0) == 5


def test_threshold_above_resting_noise():
    d = calibrated(rest_level=10, noise=2, min_threshold=0)
    assert d.threshold > 12
    assert d.update(0.0, 12.0) is None


def test_threshold_floor_for_a_dead_still_sensor():
    d = calibrated(rest_level=0, noise=0, min_threshold=50)
    assert d.threshold == 50
    assert d.update(0.0, 5.0) is None


def test_one_swing_per_spike_with_peak_power():
    d = calibrated(min_threshold=50)
    trace = [(0.00, 10), (0.02, 80), (0.04, 300), (0.06, 150), (0.08, 20), (0.10, 10)]
    swings = [s for t, m in trace if (s := d.update(t, m))]
    assert len(swings) == 1
    assert swings[0].t == 0.02
    assert swings[0].power == 300 / d.threshold


def test_refractory_blocks_bounce_back():
    d = calibrated(min_threshold=50, refractory=0.4)
    # a swing, then the follow-through rebound 0.2 s later
    trace = [(0.0, 200), (0.1, 10), (0.2, 200), (0.3, 10), (0.6, 200)]
    swings = [s for t, m in trace if (s := d.update(t, m))]
    assert [s.t for s in swings] == [0.0, 0.6]


def test_no_swings_before_calibration():
    d = SwingDetector()
    assert d.update(0.0, 1e6) is None


def test_spin_is_twist_share_at_the_peak():
    d = calibrated(min_threshold=50)
    s = d.update(0.00, 100, twist=10)            # rising edge: mostly flat
    d.update(0.02, 400, twist=-300)              # peak: strong left twist
    d.update(0.04, 200, twist=200)               # after the peak: ignored
    assert s.spin == -300 / 400


def test_rumble_speeds_up_as_ball_approaches():
    import pong
    assert pong.rumble_interval(None) is None
    assert pong.rumble_interval(pong.RUMBLE_START + 0.1) is None
    far, near = pong.rumble_interval(pong.RUMBLE_START), pong.rumble_interval(0.0)
    assert far == pong.RUMBLE_SLOW and near == pong.RUMBLE_FAST and near < far
