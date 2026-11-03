#!/usr/bin/env python3
"""Train and evaluate the step-counting neural net (PyTorch), leaving one
person out at a time.

The ground truth is the observer's taps (record.py's tap mode): one tap per
footstrike, either foot, in data/<session>_taps.csv. Sessions from before tap
mode count only if they're zero-step ones (standing, lying, air-biking).

The network (inputs and forward pass in steps.py, shared with the board):
12 channels per sample (7 from the shin IMU, 5 orientation-free ones from the
phone in the left pocket) -> 4 dilated 1D convolutions (ReLU between) -> the
probability that a foot hit the ground at that sample. It's trained to output
a narrow bump at every tap. Steps = peaks above a threshold, >= 0.2 s apart.

Training randomly drops the phone (so it still counts when there isn't one),
tilts the shin sensor a little, stretches time (cadence) and scales the
amplitude (other people move differently).

Compared, on people the network never saw:
- the net with the phone
- the net with the shin only (the phone hidden)
- last week's rule (main.py before 2026-11-02): one stride per forward swing
  of the shin, -gx rising past 120 deg/s, re-armed below 40 deg/s, >= 0.55 s
  apart; steps = 2 x strides. Kept here only for this comparison.

Writes figures/steps_*.png + figures/steps_results.json, and the final net,
trained on everyone, to unoq/activity-wearable/python/steps_model.json. Checks
that the board's numpy version gives the same output as PyTorch, and that the
board's live StepCounter finds the same steps as counting the whole recording
at once.

    python ActivityWearable/train_steps.py
    python ActivityWearable/train_steps.py --data DIR --out DIR    # another data set / output folder
"""
import argparse
import csv
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as TF  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from torch import nn  # noqa: E402

HERE = Path(__file__).resolve().parent
BOARD_PY = HERE / "unoq" / "activity-wearable" / "python"
sys.path.insert(0, str(BOARD_PY))
import steps as S  # noqa: E402
from common import DATA_DIR  # noqa: E402

FIG_DIR = HERE / "figures"
MODEL_JSON = BOARD_PY / "steps_model.json"

# Network
WIDTH, KERNEL, DILATIONS = 16, 9, (1, 2, 4, 8)
NET_REACH = (KERNEL - 1) * sum(DILATIONS) // 2          # 60 samples each side
SIGMA = 4                # samples: width of the bump trained at each tap
MIN_GAP = 20             # samples: steps at least 0.2 s apart (5 a second is a sprint)
TOL = 15                 # samples: a found step within 150 ms of a tap counts as that tap
STRIKE_G = 2.0           # a right heel strike = a peak in the shin's |a| above this, the biggest within 0.3 s
MATCH = 25               # samples: a right-foot tap within 250 ms of a heel strike is matched to it

# Training
CROP = 400               # rows of inputs per training example (4 s)
BATCH, ITERS, EPOCHS, LR = 64, 100, 25, 3e-3
POS_WEIGHT = 9.0         # the bumps are a small part of the time; weigh them up
P_NO_PHONE = 0.3         # how often training hides the phone
THRESHOLDS = np.round(np.arange(0.2, 0.81, 0.05), 2)

# Last week's rule
OLD_ENTER, OLD_LEAVE, OLD_GAP = 120.0, 40.0, 55

# Reference categorical palette (dataviz skill, slots 1-3 in order), one hue per method.
METHODS = {"net_phone": ("Net, shin + phone", "#2a78d6"), "net_shin": ("Net, shin only", "#eb6834"),
           "old_rule": ("Last week's rule (2 x strides)", "#1baf7a")}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


# ---- Data -------------------------------------------------------------------
def read_csv(path, cols):
    """Numeric columns of a session-style CSV (comment lines start with #)."""
    with open(path) as f:
        rows = [line.strip().split(",") for line in f if line.strip() and not line.startswith("#")]
    head, body = rows[0], rows[1:]
    idx = [head.index(c) if isinstance(c, str) else c for c in cols]
    return [[r[i].strip() for i in idx] for r in body]


def load(data_dir):
    sessions = []
    for r in csv.DictReader(open(data_dir / "session_log.csv")):
        path = data_dir / f"{r['session']}.csv"
        if r["status"] != "kept" or not path.exists():
            continue
        taps_path = data_dir / f"{r['session']}_taps.csv"
        shin = np.array(read_csv(path, list(range(1, 7))), dtype=float)
        shift = None
        if taps_path.exists():
            loaded = load_taps(taps_path, path)
            if loaded is None:
                continue
            taps, feet = loaded
            shift = tap_offset(taps, feet, shin)
            if shift is not None:
                taps = taps - shift
        elif r["label"] in ("still", "bike"):
            taps = np.zeros(0)               # zero-step session from before tap mode
        else:
            continue
        phone_path = data_dir / f"{r['session']}_phone.csv"
        ph = np.array(read_csv(phone_path, list(range(7))), dtype=float) if phone_path.exists() else np.zeros((0, 7))
        phone, on = S.phone_on_grid(ph[:, 0] * S.RATE_HZ, ph[:, 1:7], np.arange(len(shin)))
        X = S.inputs(shin, phone, on)
        sessions.append({
            "name": r["session"], "person": r["person"], "label": r["label"], "activity": r["activity"],
            "shin": shin, "phone": phone, "on": on, "taps": np.sort(taps), "has_phone": bool(on.any()),
            "X": X, "X_shin": S.inputs(shin, phone, np.zeros(len(shin), dtype=bool)),
            "y": bumps(taps, len(X)), "tap_shift": None if shift is None else round(shift * 10),
        })
    return sessions


def heel_strikes(shin):
    amag = np.linalg.norm(shin[:, :3], axis=1)
    pad = np.concatenate([np.zeros(30), amag, np.zeros(30)])
    win = np.lib.stride_tricks.sliding_window_view(pad, 61)
    return np.flatnonzero((np.argmax(win, axis=1) == 30) & (amag > STRIKE_G))


def tap_offset(taps, feet, shin):
    """How far the right-foot taps sit from the right shin's heel strikes
    (median, in samples), or None if fewer than 6 match. The laptop's estimate
    of the board's clock varies by ~0.1 s between sessions (2026-11-02: -138
    vs -7 ms), so each session's taps are shifted by this to sit on its heel
    strikes; the left-foot taps share the same clock and move with them."""
    strikes = heel_strikes(shin)
    right = taps[feet == "right"]
    if len(strikes) == 0 or len(right) == 0:
        return None
    off = np.array([t - strikes[np.argmin(np.abs(strikes - t))] for t in right])
    off = off[np.abs(off) <= MATCH]
    return float(np.median(off)) if len(off) >= 6 else None


def load_taps(taps_path, session_path):
    """Tap times in samples from the session's start, and which foot. A tap
    file written when the board's "saved" message never arrived has seq but no
    t_s; the start (first_seq) is then on the session CSV's "# end" line."""
    with open(taps_path) as f:
        rows = [line.strip().split(",") for line in f if line.strip() and not line.startswith("#")]
    head, body = rows[0], rows[1:]
    t_s = [r[head.index("t_s")] for r in body]
    feet = np.array([r[head.index("foot")] for r in body])
    if all(t_s):
        return np.array([float(t) for t in t_s]) * S.RATE_HZ, feet
    first = None
    for line in open(session_path):
        if line.startswith("# end") and "first_seq=" in line:
            first = int(line.split("first_seq=")[1].split()[0])
    if first is None:
        print("  no first_seq for", taps_path.name, "(skipped)")
        return None
    seqs = np.array([float(r[head.index("seq")]) for r in body]) - first
    keep = (seqs >= 0) & (seqs < sum(1 for line in open(session_path) if line[:1].isdigit()))
    return seqs[keep], feet[keep]


def bumps(taps, n):
    """The training target for input rows 0..n-1 (row i = sample i + CTX): a
    Gaussian bump, height 1, at every tap."""
    t = np.arange(n) + S.CTX
    y = np.zeros(n)
    for c in taps:
        y = np.maximum(y, np.exp(-0.5 * ((t - c) / SIGMA) ** 2))
    return y.astype(np.float32)


# ---- Network ----------------------------------------------------------------
def make_net(c_in=len(S.CHANNELS)):
    layers, c = [], c_in
    for d in DILATIONS:
        layers += [nn.Conv1d(c, WIDTH, KERNEL, dilation=d), nn.ReLU()]
        c = WIDTH
    layers.append(nn.Conv1d(c, 1, 1))
    return nn.Sequential(*layers)


def export(net, threshold):
    convs = [m for m in net if isinstance(m, nn.Conv1d)]
    return {"layers": [{"w": m.weight.detach().double().numpy().tolist(), "b": m.bias.detach().double().numpy().tolist(),
                        "dilation": m.dilation[0]} for m in convs],
            "threshold": float(threshold), "min_gap": MIN_GAP, "channels": S.CHANNELS, "ctx": S.CTX}


def rotation(rng, max_deg):
    axis = rng.normal(size=3)
    axis /= np.linalg.norm(axis)
    a = np.radians(rng.uniform(-max_deg, max_deg))
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(a) * K + (1 - np.cos(a)) * K @ K


def example(s, rng):
    """One augmented training crop: (CROP, channels) inputs, (CROP - 2*NET_REACH,) target."""
    warp = rng.uniform(0.9, 1.1)                         # cadence +-10%
    src = int(round(CROP * warp))
    shift = int(rng.integers(-5, 6))                     # the phone's clock +-50 ms
    n = len(s["X"])
    a = int(rng.integers(max(0, -shift), n - src - max(0, shift) + 1))
    X = s["X"][a:a + src].copy()
    X[:, S.PHONE_CH] = s["X"][a + shift:a + shift + src, S.PHONE_CH]
    y = s["y"][a:a + src]
    R = rotation(rng, 10)                                # the sleeve sits a little differently
    X[:, 0:3], X[:, 3:6] = X[:, 0:3] @ R.T, X[:, 3:6] @ R.T
    X[:, :7] *= rng.uniform(0.85, 1.15)
    X[:, 7:11] *= rng.uniform(0.85, 1.15)
    X += rng.normal(0, 0.01, X.shape) * (np.arange(X.shape[1]) != 11)
    grid = np.linspace(0, src - 1, CROP)
    X = np.column_stack([np.interp(grid, np.arange(src), X[:, c]) for c in range(X.shape[1])])
    y = np.interp(grid, np.arange(src), y)
    X[X[:, 11] < 1, S.PHONE_CH] = 0.0                    # where the phone was missing, exactly as live
    if not s["has_phone"] or rng.random() < P_NO_PHONE:
        X[:, S.PHONE_CH] = 0.0
    return X.astype(np.float32), y[NET_REACH:CROP - NET_REACH].astype(np.float32)


def train(sessions, seed=0, epochs=EPOCHS):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    usable = [s for s in sessions if len(s["X"]) > CROP * 1.2 + 10]
    weights = np.array([len(s["X"]) for s in usable], dtype=float)
    weights /= weights.sum()
    net = make_net()
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs * ITERS)
    for _ in range(epochs):
        for _ in range(ITERS):
            xs, ys = zip(*(example(usable[i], rng) for i in rng.choice(len(usable), BATCH, p=weights)))
            x = torch.from_numpy(np.stack(xs)).transpose(1, 2)
            y = torch.from_numpy(np.stack(ys))
            loss = TF.binary_cross_entropy_with_logits(net(x)[:, 0], y, weight=1 + POS_WEIGHT * y)
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
    return net


# ---- Counting ---------------------------------------------------------------
def probabilities(spec, X):
    """The board's numpy forward pass; returns p for samples CTX + NET_REACH onward."""
    return S.Net(spec)(X)


def found(spec, X, threshold=None):
    p = probabilities(spec, X)
    peaks = S.pick_peaks(p, spec["threshold"] if threshold is None else threshold, spec["min_gap"])
    return np.array(peaks, dtype=int) + S.CTX + NET_REACH, p


def old_rule(shin):
    """Last week's live counter, sample by sample: stride times."""
    out, armed, last = [], True, -10 ** 9
    for i, swing in enumerate(-shin[:, 3]):
        if armed and swing > OLD_ENTER and i - last >= OLD_GAP:
            out.append(i)
            last, armed = i, False
        elif not armed and swing < OLD_LEAVE:
            armed = True
    return np.array(out, dtype=int)


def match(found_at, taps):
    """Found steps paired with taps within TOL, nearest first: (hits, F1)."""
    pairs = sorted((abs(f - t), i, j) for i, f in enumerate(found_at) for j, t in enumerate(taps) if abs(f - t) <= TOL)
    used_f, used_t, hits = set(), set(), 0
    for _, i, j in pairs:
        if i not in used_f and j not in used_t:
            used_f.add(i)
            used_t.add(j)
            hits += 1
    denom = len(found_at) + len(taps)
    return hits, (2 * hits / denom if denom else 1.0)


def tune_threshold(net_spec, sessions):
    """The threshold that gets the training sessions' totals closest, with and without the phone."""
    probs = [(probabilities(net_spec, s[k]), len(s["taps"])) for s in sessions for k in ("X", "X_shin")]
    err = [sum(abs(len(S.pick_peaks(p, t, MIN_GAP)) - n) for p, n in probs) for t in THRESHOLDS]
    return float(THRESHOLDS[int(np.argmin(err))])


def evaluate(spec, s):
    row = {"session": s["name"], "person": s["person"], "label": s["label"], "activity": s["activity"],
           "seconds": round(len(s["shin"]) / S.RATE_HZ, 1), "taps": len(s["taps"]), "has_phone": s["has_phone"],
           "tap_shift_ms": s["tap_shift"]}
    for key, X in (("net_phone", s["X"]), ("net_shin", s["X_shin"])):
        at, _ = found(spec, X)
        row[key] = len(at)
        row[key + "_f1"] = round(match(at, s["taps"])[1], 3)
    row["old_rule"] = 2 * len(old_rule(s["shin"]))
    return row


def folds(sessions):
    people = sorted({s["person"] for s in sessions})
    if len(people) >= 2:
        return "leave one person out", [(p, [s for s in sessions if s["person"] != p],
                                         [s for s in sessions if s["person"] == p]) for p in people]
    print("  only one person: falling back to 3 folds by session (NOT a test on a new person)")
    idx = np.random.default_rng(0).permutation(len(sessions))
    parts = np.array_split(idx, 3)
    return "3 folds by session", [(f"fold {k + 1}", [sessions[i] for i in idx if i not in part],
                                  [sessions[i] for i in part]) for k, part in enumerate(parts)]


def summarise(rows):
    out = {}
    walking = [r for r in rows if r["taps"] >= 10]
    zero = [r for r in rows if r["taps"] == 0]
    for key in METHODS:
        errs = [abs(r[key] - r["taps"]) / r["taps"] * 100 for r in walking]
        out[key] = {
            "median_abs_err_pct": round(float(np.median(errs)), 1) if errs else None,
            "total_abs_err_pct": round(sum(abs(r[key] - r["taps"]) for r in walking) /
                                       max(1, sum(r["taps"] for r in walking)) * 100, 1),
            "false_steps_per_min": round(sum(r[key] for r in zero) / max(1e-9, sum(r["seconds"] for r in zero) / 60), 2)
            if zero else None,
        }
        if key != "old_rule":
            out[key]["median_f1"] = round(float(np.median([r[key + "_f1"] for r in walking])), 3) if walking else None
    return out


# ---- Checks -----------------------------------------------------------------
def check_numpy_matches_torch(net, spec, sessions):
    s = max(sessions, key=lambda s: len(s["X"]))
    X = s["X"][:1000]
    with torch.no_grad():
        ref = torch.sigmoid(net.double()(torch.from_numpy(X.astype(np.float64)).T[None]))[0, 0].numpy()
    net.float()
    diff = float(np.max(np.abs(ref - probabilities(spec, X))))
    print(f"  numpy vs PyTorch: largest difference {diff:.1e}")
    assert diff < 1e-4, "the board's forward pass doesn't match PyTorch"
    return diff


def check_live_matches_offline(spec, sessions, latency=15):
    """Feed sessions through the board's StepCounter in 7-sample batches, the
    phone arriving `latency` samples late, and compare with counting each
    whole recording at once (ignoring the last couple of seconds, which the
    live counter hasn't decided yet)."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(spec, f)
    checked = 0
    for s in [x for x in sessions if x["has_phone"]][:3] + [x for x in sessions if not x["has_phone"]][:1]:
        offline, _ = found(spec, s["X"] if s["has_phone"] else s["X_shin"])
        counter, live = S.StepCounter(f.name), []
        ph_t = np.flatnonzero(s["on"]).astype(float) if s["has_phone"] else np.zeros(0)
        k = 0
        for start in range(0, len(s["shin"]), 7):
            for i in range(start, min(start + 7, len(s["shin"]))):
                counter.add_shin(i, tuple(s["shin"][i]))
            newest = min(start + 6, len(s["shin"]) - 1)
            while k < len(ph_t) and ph_t[k] <= newest - latency:
                counter.add_phone(ph_t[k], tuple(s["phone"][int(ph_t[k])]))
                k += 1
            ready = min(newest, int(ph_t[k - 1]) - 1) if s["has_phone"] and k else newest
            live += counter.update(ready)
        cut = len(s["shin"]) - 3 * S.RATE_HZ
        a, b = [x for x in offline if x < cut], [x for x in live if x < cut]
        assert a == b, f"live StepCounter differs on {s['name']}: {len(a)} vs {len(b)} steps"
        checked += 1
    Path(f.name).unlink()
    print(f"  live StepCounter = whole-recording count on {checked} sessions")
    return checked


# ---- Figures ----------------------------------------------------------------
def fig_example(spec_by_person, sessions, out):
    """One held-out walk: the inputs, the net's output, taps vs found steps."""
    pick = sorted([s for s in sessions if s["label"] == "walk" and len(s["taps"]) >= 10],
                  key=lambda s: (not s["has_phone"], s["activity"] != "walk_normal"))
    if not pick:
        return
    s = pick[0]
    spec = spec_by_person[s["person"]]
    at, p = found(spec, s["X"])
    t_p = (np.arange(len(p)) + S.CTX + NET_REACH) / S.RATE_HZ
    a0 = max(0.0, s["taps"][0] / S.RATE_HZ - 0.5) if len(s["taps"]) else 3.0
    a1 = a0 + 8
    t = np.arange(len(s["shin"])) / S.RATE_HZ
    win = (t >= a0) & (t <= a1)
    fig, axes = plt.subplots(3, 1, figsize=(10, 6.6), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1.2]})
    axes[0].plot(t[win], s["shin"][win, 3], color=INK, lw=1.5)
    axes[0].set_ylabel("shin gx (°/s)")
    axes[0].set_title(f"A held-out walk ({s['person']}, {s['activity']}): what the net sees and what it counts")
    for c in old_rule(s["shin"]):
        if a0 <= c / S.RATE_HZ <= a1:
            axes[0].plot(c / S.RATE_HZ, -OLD_ENTER, marker="^", ms=8, color=METHODS["old_rule"][1], ls="none")
    swing = s["X"][:, 10] * S.GYRO_SCALE
    tx = (np.arange(len(swing)) + S.CTX) / S.RATE_HZ
    w2 = (tx >= a0) & (tx <= a1)
    axes[1].plot(tx[w2], swing[w2], color=INK2, lw=1.5)
    axes[1].set_ylabel("phone swing (°/s)")
    if not s["has_phone"]:
        axes[1].text(0.5, 0.5, "no phone in this session", transform=axes[1].transAxes, ha="center", color=INK2)
    w3 = (t_p >= a0) & (t_p <= a1)
    axes[2].plot(t_p[w3], p[w3], color=METHODS["net_phone"][1], lw=2, label="net: P(foot hits the ground)")
    axes[2].axhline(spec["threshold"], color=INK2, lw=1, ls=(0, (4, 4)), label=f"threshold {spec['threshold']:.2f}")
    taps = [c / S.RATE_HZ for c in s["taps"] if a0 <= c / S.RATE_HZ <= a1]
    axes[2].vlines(taps, 1.02, 1.12, color=INK, lw=2, label="observer's taps (truth)")
    hits = [c / S.RATE_HZ for c in at if a0 <= c / S.RATE_HZ <= a1]
    axes[2].plot(hits, np.interp(hits, t_p, p), "o", ms=8, color=METHODS["net_phone"][1],
                 mec=SURFACE, mew=2, label="steps it counts")
    axes[2].set_ylim(-0.03, 1.16)
    axes[2].set_ylabel("probability")
    axes[2].set_xlabel("time (s)")
    axes[2].plot([], [], marker="^", ms=8, color=METHODS["old_rule"][1], ls="none",
                 label="last week's rule: a stride (top panel)")
    axes[2].legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), frameon=False, fontsize=9, ncol=3)
    fig.tight_layout()
    fig.savefig(out / "steps_example.png", dpi=150)
    plt.close(fig)


def fig_comparison(rows, out):
    groups = [g for g in ("walk", "mixed", "run") if any(r["label"] == g and r["taps"] >= 10 for r in rows)]
    zero = [g for g in ("still", "bike") if any(r["label"] == g and r["taps"] == 0 for r in rows)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 4), gridspec_kw={"width_ratios": [max(len(groups), 1), max(len(zero), 1)]})
    width, top1, top2 = 0.26, 1.0, 1.0
    for k, (key, (name, color)) in enumerate(METHODS.items()):
        vals = [np.median([abs(r[key] - r["taps"]) / r["taps"] * 100 for r in rows if r["label"] == g and r["taps"] >= 10])
                for g in groups]
        xs = np.arange(len(groups)) + (k - 1) * (width + 0.02)
        ax1.bar(xs, vals, width, color=color, label=name)
        top1 = max([top1] + vals)
        for x, v in zip(xs, vals):
            ax1.text(x, v, f"{v:.0f}%\n", ha="center", va="bottom", fontsize=9, color=INK, linespacing=0.6)
        zv = [sum(r[key] for r in rows if r["label"] == g and r["taps"] == 0) /
              (sum(r["seconds"] for r in rows if r["label"] == g and r["taps"] == 0) / 60) for g in zero]
        zx = np.arange(len(zero)) + (k - 1) * (width + 0.02)
        ax2.bar(zx, zv, width, color=color)
        top2 = max([top2] + zv)
        for x, v in zip(zx, zv):
            ax2.text(x, v, f"{v:.1f}\n", ha="center", va="bottom", fontsize=9, color=INK, linespacing=0.6)
    ax1.set_xticks(range(len(groups)), groups)
    ax1.set_ylabel("count error, median per session (%)")
    ax1.set_title("Steps counted vs. taps (held out)")
    ax2.set_xticks(range(len(zero)), zero)
    ax2.set_ylabel("false steps per minute")
    ax2.set_title("Zero-step sessions")
    ax1.set_ylim(0, top1 * 1.2)
    ax2.set_ylim(0, top2 * 1.2)
    for ax in (ax1, ax2):
        ax.grid(axis="x", visible=False)
    fig.legend(*ax1.get_legend_handles_labels(), loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out / "steps_comparison.png", dpi=150)
    plt.close(fig)


def fig_network(spec, out):
    """The network as a diagram, for the write-up."""
    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 3.4)
    ax.axis("off")
    reach = S.Net(spec).reach
    boxes = [
        ("12 inputs, 100 a second", "shin (7): ax, ay, az, gx, gy, gz, |a|\nphone (5): up, side, turn, swing,\nphone-on"),
        (f"{len(DILATIONS)} dilated convolutions", f"each {KERNEL} taps, {WIDTH} channels, ReLU\ntaps spaced "
         + ", ".join(str(d) for d in DILATIONS) + " samples apart\n(each layer looks twice as far)"),
        ("1 output", "P(a foot hits\nthe ground now)"),
        ("peaks = steps", f"above {spec['threshold']:.2f},\nat least {MIN_GAP / S.RATE_HZ:.1f} s apart"),
    ]
    widths, gap, x = [2.9, 3.0, 1.9, 2.0], 0.3, 0.05
    for (title, body), w in zip(boxes, widths):
        if x > 0.05:
            ax.annotate("", (x, 1.85), (x - gap, 1.85), arrowprops=dict(arrowstyle="->", color=INK2, lw=1.2))
        ax.add_patch(FancyBboxPatch((x, 1.0), w, 1.7, boxstyle="round,pad=0,rounding_size=0.08",
                                    fc="#ffffff", ec=GRID, lw=1.2))
        ax.text(x + w / 2, 2.4, title, ha="center", va="center", fontsize=10, weight="bold")
        ax.text(x + w / 2, 1.65, body, ha="center", va="center", fontsize=8.5, color=INK2, linespacing=1.4)
        x += w + gap
    n_params = sum(np.size(l["w"]) + np.size(l["b"]) for l in spec["layers"])
    ax.text(0.05, 0.5, f"Each output sees {reach / S.RATE_HZ:.1f} s either side ({(reach + S.CTX) / S.RATE_HZ:.1f} s with "
                       f"the phone's 1 s gravity average), so steps come out about 1.3 s late.\n{n_params:,} weights, "
                       f"trained in PyTorch; the board runs the same weights with numpy.",
            fontsize=9, color=INK2, va="center", linespacing=1.5)
    ax.text(0.05, 3.15, "The step-counting network", fontsize=12, weight="bold")
    fig.savefig(out / "steps_network.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---- Main -------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DATA_DIR, help="folder with session_log.csv and the sessions")
    ap.add_argument("--out", type=Path, help="write figures and steps_model.json here instead")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    args = ap.parse_args()
    fig_dir = args.out or FIG_DIR
    model_json = (args.out / "steps_model.json") if args.out else MODEL_JSON
    fig_dir.mkdir(parents=True, exist_ok=True)

    sessions = load(args.data)
    tapped = [s for s in sessions if len(s["taps"])]
    if not tapped:
        sys.exit("No tap-mode sessions yet: record some with record.py (the step protocol) first.")
    print(f"{len(sessions)} sessions ({len(tapped)} with taps, {sum(s['has_phone'] for s in sessions)} with the phone), "
          f"{sum(len(s['taps']) for s in sessions)} taps, people: {', '.join(sorted({s['person'] for s in sessions}))}")

    how, plan = folds(sessions)
    rows, spec_by_person = [], {}
    for held, train_set, test_set in plan:
        net = train(train_set, epochs=args.epochs)
        spec = export(net, 0.5)
        spec["threshold"] = tune_threshold(spec, train_set)
        for s in test_set:
            spec_by_person[s["person"]] = spec
            rows.append(evaluate(spec, s))
        r = [x for x in rows if x["session"] in {s["name"] for s in test_set} and x["taps"] >= 10]
        print(f"  {held}: threshold {spec['threshold']:.2f}; " + ", ".join(
            f"{k} {sum(x[k] for x in r)}" for k in METHODS) + f" vs {sum(x['taps'] for x in r)} taps")
    summary = summarise(rows)

    print("final net, trained on everyone")
    net = train(sessions, epochs=args.epochs)
    spec = export(net, 0.5)
    spec["threshold"] = tune_threshold(spec, sessions)
    diff = check_numpy_matches_torch(net, spec, sessions)
    checked = check_live_matches_offline(spec, sessions)
    spec["summary"] = {"trained": date.today().isoformat(), "people": sorted({s["person"] for s in sessions}),
                       "sessions": len(sessions), "taps": int(sum(len(s["taps"]) for s in sessions)),
                       "evaluation": how,
                       "count_err_pct": summary["net_phone"]["median_abs_err_pct"],
                       "count_err_pct_shin_only": summary["net_shin"]["median_abs_err_pct"]}
    model_json.write_text(json.dumps(spec))

    fig_example(spec_by_person, sessions, fig_dir)
    fig_comparison(rows, fig_dir)
    fig_network(spec, fig_dir)
    (fig_dir / "steps_results.json").write_text(json.dumps({
        "evaluation": how, "summary": summary, "sessions": rows, "final_threshold": spec["threshold"],
        "checks": {"numpy_vs_torch_max_diff": diff, "live_equals_offline_sessions": checked},
        "settings": {"width": WIDTH, "kernel": KERNEL, "dilations": DILATIONS, "sigma": SIGMA, "min_gap": MIN_GAP,
                     "tolerance": TOL, "crop": CROP, "epochs": args.epochs, "p_no_phone": P_NO_PHONE},
    }, indent=1))

    print(f"\nHeld out ({how}), sessions with >= 10 taps:")
    for key, (name, _) in METHODS.items():
        m = summary[key]
        print(f"  {name:32s} median error {m['median_abs_err_pct']}%  total {m['total_abs_err_pct']}%  "
              f"false steps/min when still or biking {m['false_steps_per_min']}")
    print(f"wrote {model_json.relative_to(HERE.parent) if not args.out else model_json} and {fig_dir}/steps_*")


if __name__ == "__main__":
    main()
