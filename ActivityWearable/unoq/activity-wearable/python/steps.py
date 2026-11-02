"""Neural-net step counting for the activity wearable: the network's inputs,
its forward pass in numpy, and turning its output into steps.

Shared like features.py: ActivityWearable/train_steps.py trains the network in
PyTorch and builds its training inputs with these functions, and the board's
main.py runs the exported network (steps_model.json) with them, so both sides
compute the same numbers. numpy only (the board has no PyTorch).

Two sensors, both on the board's 100 Hz sample clock (seq):
- shin: the GY-521 on the right shin, (n, 6) ax, ay, az (g), gx, gy, gz (deg/s),
  axes as in features.py
- phone: an iPhone in the LEFT front pocket, same units, in the phone's own
  axes. Every pocket holds it at a different angle, so the network only sees
  channels that don't depend on how it sits (see inputs()).

The network looks at REACH samples either side of a moment and says how likely
it is that a foot (either one) hit the ground right then. A step is a peak in
that probability above the threshold, at least min_gap samples after the last.
"""
import json
from collections import deque

import numpy as np

RATE_HZ = 100
CTX = 50                 # samples each side for the phone's gravity estimate (a 1 s centred average)
ACC_SCALE = 4.0          # inputs are divided by these so they sit around +-1
GYRO_SCALE = 400.0
MAX_PHONE_GAP = 5        # samples: phone readings further apart than this (50 ms) count as missing
CHANNELS = ["shin_ax", "shin_ay", "shin_az", "shin_gx", "shin_gy", "shin_gz", "shin_amag",
            "phone_up", "phone_side", "phone_turn", "phone_swing", "phone_on"]
PHONE_CH = slice(7, 12)


def phone_on_grid(t, vals, grid):
    """Put the phone's readings (times t in samples, values (m, 6)) onto the
    shin's sample grid by linear interpolation. Returns (n, 6) values and an
    (n,) mask of where the phone was really there (zeros where it wasn't)."""
    grid = np.asarray(grid, dtype=float)
    out = np.zeros((len(grid), 6))
    on = np.zeros(len(grid), dtype=bool)
    if len(t) < 2:
        return out, on
    t, vals = np.asarray(t, dtype=float), np.asarray(vals, dtype=float)
    order = np.argsort(t, kind="stable")
    t, vals = t[order], vals[order]
    j = np.searchsorted(t, grid, side="right")            # t[j-1] <= grid < t[j]
    jj = np.clip(j, 1, len(t) - 1)
    on = (j > 0) & (j < len(t)) & (t[jj] - t[jj - 1] <= MAX_PHONE_GAP)
    for c in range(6):
        out[:, c] = np.interp(grid, t, vals[:, c])
    out[~on] = 0.0
    return out, on


def _centred_mean(x, k):
    """(n, c) -> (n - 2k, c): the mean of rows i-k..i+k, for each i that has them."""
    c = np.cumsum(np.vstack([np.zeros((1, x.shape[1])), x]), axis=0)
    return (c[2 * k + 1:] - c[:-2 * k - 1]) / (2 * k + 1)


def inputs(shin, phone, on):
    """The network's input channels, (n - 2*CTX, 12) for n samples of each.

    Shin (fixed to the leg the same way on everyone): the 6 raw axes and |a|.
    Phone (any angle in the pocket): gravity is the phone's average
    acceleration over the surrounding second, and everything is measured
    against it:
      up     acceleration along gravity, minus 1 g (bouncing up and down)
      side   size of the acceleration across gravity
      turn   rotation about the vertical (turning around)
      swing  size of the rotation about horizontal axes (the thigh swinging)
      on     1 if the phone was there for that whole second, else all 0
    """
    shin, phone = np.asarray(shin, dtype=float), np.asarray(phone, dtype=float)
    n, k = len(shin), CTX
    s, p = shin[k:n - k], phone[k:n - k]
    g = _centred_mean(phone[:, :3], k)
    full = _centred_mean(np.asarray(on, dtype=float)[:, None], k)[:, 0] > 0.999
    gn = np.linalg.norm(g, axis=1)
    ok = full & (gn > 0.5)
    u = g / np.maximum(gn, 1e-6)[:, None]
    a_up = np.sum(p[:, :3] * u, axis=1)
    g_up = np.sum(p[:, 3:] * u, axis=1)
    X = np.column_stack([
        s[:, :3] / ACC_SCALE, s[:, 3:] / GYRO_SCALE, np.linalg.norm(s[:, :3], axis=1) / ACC_SCALE,
        (a_up - gn) / ACC_SCALE,
        np.linalg.norm(p[:, :3] - a_up[:, None] * u, axis=1) / ACC_SCALE,
        g_up / GYRO_SCALE,
        np.linalg.norm(p[:, 3:] - g_up[:, None] * u, axis=1) / GYRO_SCALE,
        ok.astype(float),
    ])
    X[~ok, PHONE_CH] = 0.0
    return X.astype(np.float32)


class Net:
    """The exported network: dilated 1D convolutions with ReLU between them,
    no padding, so each output sees REACH input rows either side of it."""

    def __init__(self, spec):
        self.layers = [(np.array(l["w"], dtype=np.float32), np.array(l["b"], dtype=np.float32), l["dilation"])
                       for l in spec["layers"]]
        self.reach = sum((w.shape[2] - 1) * d for w, _, d in self.layers) // 2

    def __call__(self, X):
        """(n, channels) -> (n - 2*reach,) probabilities."""
        h = np.asarray(X, dtype=np.float32).T
        for i, (w, b, d) in enumerate(self.layers):
            L = h.shape[1] - (w.shape[2] - 1) * d
            out = b[:, None] + sum(w[:, :, j] @ h[:, j * d:j * d + L] for j in range(w.shape[2]))
            h = np.maximum(out, 0.0) if i < len(self.layers) - 1 else out
        return 1.0 / (1.0 + np.exp(-h[0].astype(np.float64)))


def pick_peaks(p, threshold, gap):
    """Steps = samples where p is >= threshold and the (first) largest value
    within gap samples either side. Two such peaks can't be closer than gap."""
    p = np.asarray(p, dtype=float)
    if len(p) == 0:
        return []
    pad = np.concatenate([np.full(gap, -np.inf), p, np.full(gap, -np.inf)])
    win = np.lib.stride_tricks.sliding_window_view(pad, 2 * gap + 1)
    return [int(c) for c in np.flatnonzero((np.argmax(win, axis=1) == gap) & (p >= threshold))]


class StepCounter:
    """The live version, on the board: shin and phone samples go in as they
    arrive, steps (as seq numbers) come out.

    A step at sample c can only be decided once the network has inputs up to
    c + reach (+ CTX for the phone) and its output up to c + gap, so steps come
    out about 1.3 s late. Gives the same steps as running inputs(), Net and
    pick_peaks over the whole recording at once (train_steps.py checks this).
    """
    HOP = 25                     # run the network once at least this many new outputs are due

    def __init__(self, path):
        with open(path) as f:
            self.spec = json.load(f)
        self.net = Net(self.spec)
        self.threshold, self.gap = self.spec["threshold"], self.spec["min_gap"]
        self.reach = self.net.reach + CTX
        self.shin = deque(maxlen=20 * RATE_HZ)          # (seq, values)
        self.phone = deque(maxlen=20 * RATE_HZ)         # (seq on the board's clock, values)
        self.reset()

    def reset(self):
        self.shin.clear()
        self.next_out = None     # seq of the next output the network hasn't computed
        self.probs = deque()     # (seq, p) not yet decided, plus gap samples of history
        self.decided = None      # every seq up to this one has been decided

    def add_shin(self, seq, v):
        if self.shin and seq != self.shin[-1][0] + 1:   # a gap: start over after it
            self.reset()
        self.shin.append((seq, v))
        if self.next_out is None:
            self.next_out = seq + self.reach

    def add_phone(self, t, v):
        self.phone.append((t, v))

    def update(self, ready):
        """Run the network on everything that's due. ready = the newest seq
        whose inputs are all in (the phone's data arrives a little late).
        Returns the seqs of new steps."""
        if not self.shin or self.next_out is None:
            return []
        last_out = min(ready, self.shin[-1][0]) - self.reach
        if last_out - self.next_out + 1 < self.HOP:
            return []
        seq0 = self.shin[0][0]
        if self.next_out - self.reach < seq0:           # fell further behind than the buffer holds: skip ahead
            self.next_out = seq0 + self.reach
            self.probs.clear()
            self.decided = None
            if last_out - self.next_out + 1 < self.HOP:
                return []
        a, b = self.next_out - self.reach - seq0, last_out + self.reach - seq0 + 1
        shin = np.array([v for _, v in list(self.shin)[a:b]])
        grid = np.arange(self.next_out - self.reach, last_out + self.reach + 1)
        ph = [x for x in self.phone if grid[0] - MAX_PHONE_GAP - 1 <= x[0] <= grid[-1] + MAX_PHONE_GAP + 1]
        phone, on = phone_on_grid([t for t, _ in ph], [v for _, v in ph], grid)
        p = self.net(inputs(shin, phone, on))
        self.probs.extend(zip(range(self.next_out, last_out + 1), p))
        self.next_out = last_out + 1
        return self._decide()

    def _decide(self):
        seqs = np.array([s for s, _ in self.probs])
        p = np.array([x for _, x in self.probs])
        start = self.decided + 1 if self.decided is not None else seqs[0]
        end = seqs[-1] - self.gap                       # p is known up to end + gap
        steps = []
        for i in np.flatnonzero((seqs >= start) & (seqs <= end) & (p >= self.threshold)):
            lo = max(0, i - self.gap)
            if lo + int(np.argmax(p[lo:i + self.gap + 1])) == i:
                steps.append(int(seqs[i]))
        if end >= start:
            self.decided = int(end)
        while self.probs and self.probs[0][0] < self.decided - self.gap:
            self.probs.popleft()
        return steps
