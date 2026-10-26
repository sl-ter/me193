"""Windows and features for the activity wearable.

Used on both sides so they can never drift apart: the laptop's train.py builds
its training data with it, and the board's main.py will classify live with it.
numpy only (the board has no scikit-learn).

A window is WINDOW_S seconds of samples: an (n, 6) array of ax, ay, az (g) and
gx, gy, gz (deg/s), with the axes as worn: +Y up the shin, +Z forward out of
the shin, +X to the wearer's left.
"""
import numpy as np

RATE_HZ = 100
WINDOW_S = 2.0          # about two strides of walking
STEP_S = 0.5            # a new window every half second
WINDOW = int(WINDOW_S * RATE_HZ)
STEP = int(STEP_S * RATE_HZ)

AXES = ("x", "y", "z")
DIRECTIONS = ("+x", "-x", "+y", "-y", "+z", "-z")


def windows(samples, trim_s=0.0):
    """Split a session's (n, 6) samples into overlapping windows, after
    dropping trim_s seconds at each end (getting into position, stopping)."""
    trim = int(trim_s * RATE_HZ)
    samples = samples[trim:len(samples) - trim] if trim else samples
    return [samples[i:i + WINDOW] for i in range(0, len(samples) - WINDOW + 1, STEP)]


# ---- Model 1: one number ----------------------------------------------------
def peak(window, direction):
    """Model 1's only input: the largest acceleration along one signed axis,
    e.g. "+y" = how hard the shin was pushed up toward the knee."""
    sign = 1.0 if direction[0] == "+" else -1.0
    return float(np.max(sign * window[:, AXES.index(direction[1])]))


# ---- Model 2: all IMU outputs ----------------------------------------------
def _dominant(signal):
    """Strongest frequency in 0.3-8 Hz (Hz) and its share of that band's power.
    Zero-padded so a 2 s window still gives a usable estimate."""
    x = signal - signal.mean()
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)), n=1024)) ** 2
    freqs = np.fft.rfftfreq(1024, 1 / RATE_HZ)
    band = (freqs >= 0.3) & (freqs <= 8.0)
    total = spec[band].sum()
    if total <= 1e-12:
        return 0.0, 0.0
    i = int(np.argmax(spec[band]))
    return float(freqs[band][i]), float(spec[band][i] / total)


def features(window):
    """Named features of one window (dict, fixed order)."""
    acc, gyro = window[:, :3], window[:, 3:]
    amag = np.linalg.norm(acc, axis=1)
    gmag = np.linalg.norm(gyro, axis=1)
    f = {}
    for i, ax in enumerate(AXES):            # mean = which way gravity points (posture)
        a = acc[:, i]
        f[f"acc_{ax}_mean"] = a.mean()
        f[f"acc_{ax}_std"] = a.std()
        f[f"acc_{ax}_min"] = a.min()
        f[f"acc_{ax}_max"] = a.max()
    f["acc_mag_mean"] = amag.mean()
    f["acc_mag_std"] = amag.std()
    f["acc_mag_max"] = amag.max()
    f["acc_jerk"] = np.abs(np.diff(amag)).mean() * RATE_HZ   # how sharp the impacts are
    for i, ax in enumerate(AXES):
        g = gyro[:, i]
        f[f"gyro_{ax}_mean"] = g.mean()
        f[f"gyro_{ax}_std"] = g.std()
        f[f"gyro_{ax}_absmax"] = np.abs(g).max()
    f["gyro_mag_mean"] = gmag.mean()
    f["gyro_mag_max"] = gmag.max()
    # The shin swings about X (side to side axis) when walking, running and
    # pedalling, so gx's strongest frequency is the step/pedal rate.
    f["cadence_hz"], f["cadence_share"] = _dominant(gyro[:, 0])
    f["acc_mag_freq_hz"], _ = _dominant(amag)
    return {k: float(v) for k, v in f.items()}


FEATURE_NAMES = list(features(np.zeros((WINDOW, 6))))


def vector(window):
    return np.array(list(features(window).values()))
