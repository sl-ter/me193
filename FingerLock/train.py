#!/usr/bin/env python3
"""Train and test the safe's network (PyTorch, built from scratch), then
export it for the board.

The data is capture.py's photos: data/<PERSON>/<session>/<label>/*.png, grey,
128 x 128. The owner (common.OWNER) is the person whose hand opens the safe.
Everyone else is a friend whose photos teach the network what "not the owner"
looks like.

The network (the layers are defined here; the same forward pass is written
out in numpy in unoq/finger-lock/python/fingernet.py for the board): 3 rounds
of 3 x 3 convolution, ReLU and 2 x 2 max pooling, a fully connected layer of
64, then two heads: the count (no hand, 0-5 fingers) and "is this the owner's
hand". Random starting weights, no pretrained anything.

Testing is done only on photos the network never trained on:
- Counting: one of the owner's sessions is held out (default: the last one
  alphabetically, e.g. lamp2 if you shot lamp1 and lamp2). Per-frame accuracy
  and a confusion matrix.
- Strangers: each friend is held out in turn (one training run per friend).
  How often does the owner head call that friend "the owner"? Measured per
  frame, and averaged over a 0.8 s hold the way the safe's rules do it.
- The owner threshold the safe uses is picked on those held-out answers,
  never on the training photos: the highest one that still lets the owner in
  on at least 90% of their held-out holds (higher refuses more strangers).
Then the final network trains on everything and is exported, thresholds
included, to unoq/finger-lock/python/fingernet_model.npz. A check confirms
the board's numpy version gives the same answers as PyTorch.

Training randomly spins (any angle), shifts, scales and flips each photo, and changes its
brightness, contrast and sharpness, so the network sees "the same hand" many
ways and doesn't memorise exact pixels.

Writes figures/confusion.png, loss.png, owner.png, filters.png, network.png,
figures/results.json, and figures/train_snapshots.npz (first-layer filters
after every epoch, for the movie's training scene).

    python FingerLock/train.py
    python FingerLock/train.py --quick                  # 3 epochs: check the pipeline runs
    python FingerLock/train.py --data DIR --out DIR     # another data set / output folder
"""
import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as TF  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from torch import nn  # noqa: E402

from common import DATA_DIR, FIG_DIR, MODEL_PATH, OWNER  # noqa: E402
import fingernet as FN  # noqa: E402
import lock_policy as LP  # noqa: E402

LABELS = FN.COUNT_LABELS
NONE = FN.NONE

# Training
EPOCHS, BATCH, LR, WEIGHT_DECAY, DROPOUT = 60, 64, 2e-3, 1e-4, 0.3
LR_DROP_AT = 0.7            # learning rate x0.2 for the last 30% of epochs
OWNER_WEIGHT = 1.0          # owner loss vs count loss
# Augmentation
TURN_DEG, SCALE, SHIFT = 180, (0.85, 1.15), 0.10      # any angle: the count doesn't depend on which way the hand points
# Testing
SAVE_RATE = 5.0             # capture.py's photos per second
HOLD_FRAMES = max(1, round(LP.HOLD_S * SAVE_RATE))     # 4 photos = one 0.8 s hold
BURST_GAP_S = 0.6           # photos further apart than this aren't the same hold
THRESHOLDS = np.round(np.arange(0.01, 1.0, 0.01), 2)
OWNER_MIN_ACCEPT = 0.9      # the owner's held-out holds that must get in
METHODS = ("head", "prototype")     # the two ways of checking the owner (see fingernet.py)
SD_FLOOR = 0.1              # x the mean spread: a nearly constant number mustn't dominate the distance
CHECK_TOL = 1e-4

# Same look as the wearable's figures (dataviz skill's reference palette)
BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


# ---- Data ---------------------------------------------------------------------------

class Data:
    """Every photo, with who/which session/what label/when."""

    def __init__(self, data_dir, owner):
        rows = []
        for person_dir in sorted(p for p in Path(data_dir).iterdir() if p.is_dir()):
            for session_dir in sorted(p for p in person_dir.iterdir() if p.is_dir()):
                for li, lab in enumerate(LABELS):
                    for f in sorted((session_dir / lab).glob("*.png")):
                        m = re.match(r"(\d+)", f.stem)
                        t = int(m.group(1)) / 1000 if m else 0.0
                        rows.append((person_dir.name.upper(), session_dir.name, li, t, f))
        if not rows:
            sys.exit(f"No photos in {data_dir}. Take some with capture.py first.")
        imgs = []
        for *_, f in rows:
            img = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
            if img.shape != (FN.SAVE_SIZE, FN.SAVE_SIZE):
                img = np.clip(np.rint(FN.shrink(img, FN.SAVE_SIZE)), 0, 255).astype(np.uint8)
            imgs.append(img)
        self.imgs = np.stack(imgs)
        self.person = np.array([r[0] for r in rows])
        self.session = np.array([r[1] for r in rows])
        self.label = np.array([r[2] for r in rows], np.int64)
        self.time = np.array([r[3] for r in rows])
        self.owner_name = owner.upper()
        self.owner = self.person == self.owner_name
        self.n = len(rows)

    def summary(self):
        lines = [f"{'person':10s} {'session':10s} " + " ".join(f"{l:>5s}" for l in LABELS) + "  total"]
        for p in sorted(set(self.person)):
            for s in sorted(set(self.session[self.person == p])):
                m = (self.person == p) & (self.session == s)
                counts = [int(((self.label == li) & m).sum()) for li in range(len(LABELS))]
                lines.append(f"{p:10s} {s:10s} " + " ".join(f"{c:5d}" for c in counts) + f"  {int(m.sum()):5d}")
        return "\n".join(lines)


def augment(img, rng):
    """A random version of a 128 x 128 photo: spun by any angle (a hand has the
    same number of fingers whichever way it points; on 2026-11-09 the network
    trained on +-25 degrees called Sam's leftward-pointing 2s "3"), scaled,
    shifted, maybe flipped (a mirrored hand has the same number of fingers),
    brighter or darker, more or less contrast, sometimes blurred, a little noise.
    The corners a rotation uncovers are filled with the photo's border colour
    (the mat), not smeared edge pixels."""
    size = img.shape[0]
    border = float(np.median(np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])))
    m = cv2.getRotationMatrix2D((size / 2, size / 2), rng.uniform(-TURN_DEG, TURN_DEG), rng.uniform(*SCALE))
    m[:, 2] += rng.uniform(-SHIFT, SHIFT, 2) * size
    x = cv2.warpAffine(img.astype(np.float32), m, (size, size), flags=cv2.INTER_LINEAR,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=border)
    if rng.random() < 0.5:
        x = np.ascontiguousarray(x[:, ::-1])
    x = np.clip(x / 255.0, 0, 1) ** rng.uniform(0.7, 1.4)
    x = x * rng.uniform(0.7, 1.3) + rng.uniform(-0.15, 0.15)
    if rng.random() < 0.2:
        x = cv2.GaussianBlur(x, (0, 0), rng.uniform(0.5, 1.5))
    x = x + rng.normal(0, rng.uniform(0, 0.03), x.shape)
    return (np.clip(x, 0, 1) * 255.0).astype(np.float32)


def inputs(imgs):
    """Photos -> network inputs (N, 1, 64, 64), no augmentation."""
    return np.stack([FN.net_input(i) for i in imgs])


# ---- Network ---------------------------------------------------------------------------

class Net(nn.Module):
    """The same layers as fingernet.FingerNet, in PyTorch for training."""

    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(1, 8, 3, padding=1)
        self.conv2 = nn.Conv2d(8, 16, 3, padding=1)
        self.conv3 = nn.Conv2d(16, 32, 3, padding=1)
        self.fc = nn.Linear(32 * 8 * 8, 64)
        self.count = nn.Linear(64, len(LABELS))
        self.owner = nn.Linear(64, 1)
        self.drop = nn.Dropout(DROPOUT)

    def forward(self, x):
        """Count scores, owner-head score, and the 64-number description of the hand."""
        for conv in (self.conv1, self.conv2, self.conv3):
            x = TF.max_pool2d(TF.relu(conv(x)), 2)
        h = TF.relu(self.fc(x.flatten(1)))
        hd = self.drop(h)
        return self.count(hd), self.owner(hd).squeeze(1), h


def weights_of(net):
    """PyTorch state -> the numpy weight names fingernet.FingerNet uses."""
    sd = {k: v.detach().cpu().numpy().astype(np.float32) for k, v in net.state_dict().items()}
    return {f"{name}_{kind}": sd[f"{name}.{'weight' if kind == 'w' else 'bias'}"]
            for name in ("conv1", "conv2", "conv3", "fc", "count", "owner") for kind in ("w", "b")}


def predict(net, x, batch=256):
    """Count probabilities (N, 7), owner-head probabilities (N,), descriptions (N, 64)."""
    net.eval()
    probs, owner, desc = [], [], []
    with torch.no_grad():
        for b in range(0, len(x), batch):
            sc, so, h = net(torch.from_numpy(x[b:b + batch]))
            probs.append(torch.softmax(sc, 1).numpy())
            owner.append(torch.sigmoid(so).numpy())
            desc.append(h.numpy())
    return np.concatenate(probs), np.concatenate(owner), np.concatenate(desc)


def prototypes(desc, labels):
    """The owner's average description for each count (1-6), how much each of
    the 64 numbers spreads, and the owner's typical squared distance (so an
    ordinary photo of the owner scores about exp(-0.5) = 0.61). From the
    owner's own unaugmented photos."""
    mu = np.zeros((6, desc.shape[1]), np.float32)
    sd = np.ones_like(mu)
    for c in range(1, 7):
        d = desc[labels == c]
        if len(d) < 2:              # too few photos of this count: use all the owner's hands
            d = desc[labels != NONE]
        s = d.std(0)
        mu[c - 1] = d.mean(0)
        sd[c - 1] = np.maximum(s, SD_FLOOR * s.mean() + 1e-6)
    hand = labels != NONE
    z = (desc[hand] - mu[labels[hand] - 1]) / sd[labels[hand] - 1]
    scale = float(np.median(np.mean(z * z, axis=1)))
    return mu, sd, max(scale, 1e-6)


def train(data, idx_train, epochs, seed, eval_sets=None, log=print):
    """Train a fresh network on data.imgs[idx_train]. eval_sets: {name: indices}
    whose (unaugmented) loss is tracked each epoch. Returns (net, history)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.MultiStepLR(opt, [max(1, int(epochs * LR_DROP_AT))], 0.2)

    y = data.label[idx_train]
    freq = np.bincount(y, minlength=len(LABELS)).astype(np.float64)
    cw = np.where(freq > 0, freq.sum() / np.maximum(freq, 1) / (freq > 0).sum(), 0.0)
    cw = torch.tensor(cw, dtype=torch.float32)
    hand = idx_train[data.label[idx_train] != NONE]
    n_pos, n_neg = int(data.owner[hand].sum()), int((~data.owner[hand]).sum())
    use_owner = n_pos > 0 and n_neg > 0
    pos_weight = torch.tensor(n_neg / max(n_pos, 1), dtype=torch.float32)

    eval_x = {k: torch.from_numpy(inputs(data.imgs[v])) for k, v in (eval_sets or {}).items() if len(v)}
    hist = {"train": [], "eval": {k: [] for k in eval_x}, "filters": [weights_of(net)["conv1_w"]]}

    def loss_of(sc, so, yc, yo, weighted):
        loss = TF.cross_entropy(sc, yc, weight=cw if weighted else None)
        on = yc != NONE
        if use_owner and on.any():
            loss = loss + OWNER_WEIGHT * TF.binary_cross_entropy_with_logits(
                so[on], yo[on], pos_weight=pos_weight if weighted else None)
        return loss

    for epoch in range(epochs):
        net.train()
        t0, total, n = time.time(), 0.0, 0
        order = rng.permutation(idx_train)
        for b in range(0, len(order), BATCH):
            bi = order[b:b + BATCH]
            x = torch.from_numpy(np.stack([FN.net_input(augment(data.imgs[i], rng)) for i in bi]))
            yc = torch.from_numpy(data.label[bi])
            yo = torch.from_numpy(data.owner[bi].astype(np.float32))
            sc, so, _ = net(x)
            loss = loss_of(sc, so, yc, yo, weighted=True)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(bi)
            n += len(bi)
        sched.step()
        hist["train"].append(total / n)
        net.eval()
        with torch.no_grad():
            for k, x in eval_x.items():
                v = eval_sets[k]
                sc, so, _ = net(x)
                hist["eval"][k].append(loss_of(sc, so, torch.from_numpy(data.label[v]),
                                               torch.from_numpy(data.owner[v].astype(np.float32)),
                                               weighted=False).item())
        hist["filters"].append(weights_of(net)["conv1_w"])
        ev = "  ".join(f"{k} {vals[-1]:.3f}" for k, vals in hist["eval"].items())
        log(f"  epoch {epoch + 1:2d}/{epochs}  train loss {hist['train'][-1]:.3f}  {ev}  ({time.time() - t0:.1f} s)")
    hist["use_owner"] = use_owner
    return net, hist


# ---- Testing ----------------------------------------------------------------------------

def hold_means(data, idx, p):
    """A score averaged over every run of HOLD_FRAMES consecutive photos of the
    same hand pose (same person, session and label, taken in one burst), the
    way the safe averages it over a 0.8 s hold. Hand photos only."""
    by_key = {}
    for i, pi in zip(idx, p):
        if data.label[i] != NONE:
            by_key.setdefault((data.person[i], data.session[i], data.label[i]), []).append((data.time[i], pi))
    out = []
    for rows in by_key.values():
        rows.sort()
        burst = [rows[0][1]]
        for (t0, _), (t1, pi) in zip(rows, rows[1:]):
            if t1 - t0 > BURST_GAP_S:
                if len(burst) >= HOLD_FRAMES:
                    out.extend(np.convolve(burst, np.ones(HOLD_FRAMES) / HOLD_FRAMES, mode="valid"))
                burst = []
            burst.append(pi)
        if len(burst) >= HOLD_FRAMES:
            out.extend(np.convolve(burst, np.ones(HOLD_FRAMES) / HOLD_FRAMES, mode="valid"))
    if not out:     # no bursts long enough: fall back to single frames
        out = [pi for rows in by_key.values() for _, pi in rows]
    return np.array(out)


def confusion(y, pred):
    m = np.zeros((len(LABELS), len(LABELS)), np.int64)
    for a, b in zip(y, pred):
        m[a, b] += 1
    return m


def pick_owner_threshold(owner_holds):
    """The highest threshold that still lets the owner in on at least
    OWNER_MIN_ACCEPT of their held-out holds. Higher refuses more strangers,
    so this keeps out as many as possible without locking the owner out."""
    ok = [t for t in THRESHOLDS if (owner_holds >= t).mean() >= OWNER_MIN_ACCEPT]
    return float(max(ok)) if ok else float(THRESHOLDS[0])


def run_fold(data, idx_train, owner_idx, stranger_idx, epochs, seed, label):
    """Train without the held-out photos, then score them both ways."""
    eval_sets = {"owner": owner_idx}
    if len(stranger_idx):
        eval_sets[f"stranger {label}"] = stranger_idx
    net, hist = train(data, idx_train, epochs, seed, eval_sets)
    own_train = idx_train[data.owner[idx_train] & (data.label[idx_train] != NONE)]
    _, _, d_own = predict(net, inputs(data.imgs[own_train]))
    proto = prototypes(d_own, data.label[own_train])

    def scores(idx):
        p, head, d = predict(net, inputs(data.imgs[idx]))
        return p, {"head": head, "prototype": FN.proto_scores(d, p.argmax(1), *proto)}

    p, s = scores(owner_idx)
    fold = {"without": label, "hist": hist,
            "count_acc": float((p.argmax(1) == data.label[owner_idx]).mean()),
            "confusion": confusion(data.label[owner_idx], p.argmax(1)),
            "owner": {m: hold_means(data, owner_idx, v) for m, v in s.items()}}
    if len(stranger_idx):
        ps, ss = scores(stranger_idx)
        fold["stranger"] = {m: hold_means(data, stranger_idx, v) for m, v in ss.items()}
        fold["stranger_count_acc"] = float((ps.argmax(1) == data.label[stranger_idx]).mean())
    return fold


def compare_owner_checks(folds, have_strangers):
    """Each way of checking the owner at its own threshold. The head needs
    strangers to train on, so without friends only the prototype is possible."""
    summary = {}
    for m in METHODS:
        if m == "head" and not have_strangers:
            continue
        oh = np.concatenate([f["owner"][m] for f in folds])
        t = pick_owner_threshold(oh)
        entry = {"threshold": t, "owner_accepted_holds": round(float((oh >= t).mean()), 4)}
        if have_strangers:
            sh = np.concatenate([f["stranger"][m] for f in folds])
            entry["stranger_refused_holds"] = round(float((sh < t).mean()), 4)
            entry["stranger_refused_by_friend"] = {f["without"]: round(float((f["stranger"][m] < t).mean()), 4)
                                                   for f in folds}
        summary[m] = entry
    if have_strangers:
        method = max(summary, key=lambda m: (summary[m]["stranger_refused_holds"],
                                             summary[m]["owner_accepted_holds"], m == "head"))
    else:
        method = "prototype"
    return method, summary


# ---- Figures ------------------------------------------------------------------------------

def fig_confusion(m, title, out):
    rows = m / np.maximum(m.sum(1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    ax.imshow(rows, cmap="Blues", vmin=0, vmax=1)
    ax.grid(False)
    for i in range(len(LABELS)):
        for j in range(len(LABELS)):
            if m[i, j]:
                ax.text(j, i, f"{m[i, j]}", ha="center", va="center", fontsize=9,
                        color="white" if rows[i, j] > 0.6 else INK)
    names = ["no hand" if lab == "none" else lab for lab in LABELS]
    ax.set_xticks(range(len(LABELS)), names)
    ax.set_yticks(range(len(LABELS)), names)
    ax.set_xlabel("network's answer")
    ax.set_ylabel("true count")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_loss(final_hist, folds, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    ep = np.arange(1, len(final_hist["train"]) + 1)
    ax.plot(ep, final_hist["train"], color=BLUE, lw=2, label="training photos (augmented), final network")
    for f in folds:
        for k, vals in f["hist"]["eval"].items():
            colour = GREEN if k.startswith("owner") else ORANGE
            ax.plot(np.arange(1, len(vals) + 1), vals, color=colour, lw=1.2, alpha=0.8,
                    label=f"held out: {k} (run without {f['without']})" if f["without"] else f"held out: {k}")
    ax.set_xlabel("epoch (one pass through the training photos)")
    ax.set_ylabel("loss")
    ax.set_title("Loss while training")
    ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_owner(folds, summary, method, owner, out):
    ms = [m for m in METHODS if m in summary]
    fig, axes = plt.subplots(1, len(ms), figsize=(6.4 * len(ms), 4), squeeze=False)
    bins = np.linspace(0, 1, 26)
    for ax, m in zip(axes[0], ms):
        oh = np.concatenate([f["owner"][m] for f in folds])
        ax.hist(oh, bins=bins, color=BLUE, alpha=0.75, weights=np.full(len(oh), 1 / max(len(oh), 1)),
                label=f"{owner}, held-out session")
        for k, f in enumerate(x for x in folds if "stranger" in x):
            v = f["stranger"][m]
            ax.hist(v, bins=bins, histtype="step", lw=2, color=[ORANGE, GREEN, INK2][k % 3],
                    weights=np.full(len(v), 1 / max(len(v), 1)), label=f"{f['without']}, never trained on")
        t = summary[m]["threshold"]
        ax.axvline(t, color=INK, ls="--", lw=1.2)
        refused = summary[m].get("stranger_refused_holds")
        name = "owner head, trained on friends" if m == "head" else f"closeness to {owner}'s average hand"
        ax.set_title(name + ("  (used)" if m == method else ""))
        ax.set_xlabel(f"score over a 0.8 s hold; threshold {t:.2f}"
                      + (f"; strangers refused {refused:.0%}" if refused is not None else ""))
        ax.set_ylabel("fraction of holds")
        ax.legend(fontsize=8, frameon=False)
    fig.suptitle(f"Is it {owner}'s hand?", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_filters(w, out):
    fig, axes = plt.subplots(1, len(w), figsize=(1.3 * len(w), 1.8))
    lim = np.abs(w).max()
    for k, ax in enumerate(axes):
        ax.imshow(w[k, 0], cmap="RdBu_r", vmin=-lim, vmax=lim)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        ax.set_title(f"filter {k + 1}", fontsize=8, loc="center", fontweight="normal")
    fig.suptitle("First-layer 3x3 filters after training (red +, blue -)", fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


def fig_network(owner, method, out):
    boxes = [("camera crop\n64 x 64 grey", "1 x 64 x 64"),
             ("conv 3x3, 8 filters\nReLU, max pool 2x2", "8 x 32 x 32"),
             ("conv 3x3, 16 filters\nReLU, max pool 2x2", "16 x 16 x 16"),
             ("conv 3x3, 32 filters\nReLU, max pool 2x2", "32 x 8 x 8"),
             ("flatten 2048\nfully connected 64, ReLU\n(the hand's description)", "64")]
    fig, ax = plt.subplots(figsize=(12, 3.2))
    ax.set_xlim(0, 12.2)
    ax.set_ylim(0, 3.2)
    ax.axis("off")
    for k, (text, shape) in enumerate(boxes):
        x = 0.1 + k * 2.0
        ax.add_patch(FancyBboxPatch((x, 1.0), 1.7, 1.2, boxstyle="round,pad=0.04", fc="#eaf2fc", ec=BLUE))
        ax.text(x + 0.85, 1.6, text, ha="center", va="center", fontsize=8.5)
        ax.text(x + 0.85, 0.75, shape, ha="center", va="center", fontsize=8, color=INK2)
        ax.annotate("", (x + 1.95, 1.6), (x + 1.75, 1.6), arrowprops=dict(arrowstyle="->", color=INK2))
    owner_text = (f"owner check:\ncloseness to {owner}'s\naverage hand" if method == "prototype"
                  else f"owner check:\nis it {owner}'s hand?\n(sigmoid)")
    for y, text, colour in [(2.25, "count: no hand,\n0, 1, 2, 3, 4, 5\n(softmax)", BLUE), (0.35, owner_text, ORANGE)]:
        ax.add_patch(FancyBboxPatch((10.25, y), 1.8, 0.9, boxstyle="round,pad=0.04", fc=SURFACE, ec=colour))
        ax.text(11.15, y + 0.45, text, ha="center", va="center", fontsize=8.5)
        ax.annotate("", (10.25, y + 0.45), (9.85, 1.6), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.set_title("The safe's network: one set of layers, two answers")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    plt.close(fig)


# ---- Main ---------------------------------------------------------------------------------

def check_numpy_matches_torch(net, weights, imgs):
    """The board's numpy forward pass must give PyTorch's answers: count
    probabilities, owner head, and the prototype score."""
    x = inputs(imgs)
    p_t, o_t, d_t = predict(net, x)
    pr_t = FN.proto_scores(d_t, p_t.argmax(1), weights["proto_mu"], weights["proto_sd"],
                           float(weights["proto_scale"]))
    board = FN.FingerNet(weights=weights)
    diffs = []
    for k in range(len(x)):
        p_n, _, acts = board.forward(x[k], keep=True)
        diffs.append(max(np.abs(p_n - p_t[k]).max(), abs(acts["owner_head"] - o_t[k]),
                         abs(acts["owner_proto"] - pr_t[k])))
    return float(max(diffs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DATA_DIR)
    ap.add_argument("--out", type=Path, default=FIG_DIR, help="figures and results folder")
    ap.add_argument("--model", type=Path, default=MODEL_PATH, help="where to export the trained network")
    ap.add_argument("--owner", default=OWNER)
    ap.add_argument("--holdout-session", help="the owner's session to test on (default: the last one)")
    ap.add_argument("--holdout-tail", metavar="SESSION",
                    help="test on the last 20%% of each label's photos in this owner session and train on the rest of it "
                         "(how much a session helps on its own conditions)")
    ap.add_argument("--save-counting-run", type=Path, metavar="NPZ",
                    help="also save the counting run's network (it never saw the held-out photos), for testing it later")
    ap.add_argument("--owner-method", choices=METHODS, help="force a way of checking the owner")
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--quick", action="store_true", help="3 epochs, just to check everything runs")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    epochs = 3 if args.quick else args.epochs
    args.out.mkdir(parents=True, exist_ok=True)

    data = Data(args.data, args.owner)
    owner = data.owner_name
    print(data.summary())
    if not data.owner.any():
        sys.exit(f"No photos of the owner ({owner}) in {args.data}.")

    # Held out: one of the owner's sessions (or, with only one, the last 20% of each label's photos).
    owner_sessions = sorted(set(data.session[data.owner]))
    hs = None if args.holdout_tail else (args.holdout_session or (owner_sessions[-1] if len(owner_sessions) >= 2 else None))
    if hs:
        held_owner = data.owner & (data.session == hs)
        held_desc = f"{owner}'s session '{hs}'"
    else:
        pool = data.owner & (data.session == args.holdout_tail) if args.holdout_tail else data.owner
        held_owner = np.zeros(data.n, bool)
        for li in range(len(LABELS)):
            idx = np.where(pool & (data.label == li))[0]
            idx = idx[np.argsort(data.time[idx])]
            held_owner[idx[int(len(idx) * 0.8):]] = True
        held_desc = (f"the last 20% of {owner}'s session '{args.holdout_tail}', each label" if args.holdout_tail
                     else f"the last 20% of {owner}'s photos of each label (only one session)")
    if not held_owner.any():
        sys.exit(f"Nothing held out ({held_desc} is empty).")
    friends = sorted(str(p) for p in set(data.person[~data.owner]))
    print(f"\nHeld out for counting: {held_desc}. Friends (strangers when held out): {friends or 'none'}")
    if not friends:
        print("WARNING: no friends' photos. The owner check can only be the prototype one, "
              "and nothing tests it on strangers.")

    # One run per held-out friend.
    owner_idx = np.where(held_owner)[0]
    folds = []
    for f in friends or [None]:
        held_friend = data.person == f if f else np.zeros(data.n, bool)
        idx_train = np.where(~held_owner & ~held_friend)[0]
        print(f"\nRun without {f or '(no friends)'}: training on {len(idx_train)} photos")
        fold = run_fold(data, idx_train, owner_idx, np.where(held_friend)[0], epochs, args.seed, f)
        folds.append(fold)
        if f:
            print(f"  (this run never saw {f}: {f}'s fingers counted right {fold['stranger_count_acc']:.1%})")

    # Counting: trained on everyone except the owner's held-out photos (friends included,
    # like the final network), tested on those held-out photos.
    if friends:
        print(f"\nCounting run: training on everything except {held_desc}")
        idx_c = np.where(~held_owner)[0]
        net_c, hist_c = train(data, idx_c, epochs, args.seed, {"owner": owner_idx})
        pc, _, _ = predict(net_c, inputs(data.imgs[owner_idx]))
        if args.save_counting_run:
            m = {"labels": LABELS, "save_size": FN.SAVE_SIZE, "size": FN.NET_SIZE, "crop_frac": FN.CROP_FRAC,
                 "count_conf": LP.CONF, "owner_method": "head", "owner_threshold": 0.5, "owner_check": False,
                 "trained": date.today().isoformat(), "note": f"counting run, never saw {held_desc}"}
            np.savez(args.save_counting_run, **weights_of(net_c), meta=np.array(json.dumps(m)))
            print(f"  saved the counting run's network to {args.save_counting_run}")
    else:
        pc, _, _ = predict(net, inputs(data.imgs[owner_idx]))        # the only run already is that
    count_pred = pc.argmax(1)
    count_acc = float((count_pred == data.label[owner_idx]).mean())
    m_count = confusion(data.label[owner_idx], count_pred)
    conf_ok = pc.max(1) >= LP.CONF
    trusted_share = float(conf_ok.mean())
    trusted_acc = float((count_pred[conf_ok] == data.label[owner_idx][conf_ok]).mean()) if conf_ok.any() else 0.0
    print(f"  counting, {held_desc}: {count_acc:.1%} of frames right; the network is sure (>= {LP.CONF}) "
          f"on {trusted_share:.0%} of them, and right on {trusted_acc:.1%} of those")

    method, summary = compare_owner_checks(folds, bool(friends))
    if args.owner_method:
        if args.owner_method not in summary:
            sys.exit(f"--owner-method {args.owner_method} needs friends' photos.")
        method = args.owner_method
    owner_t = summary[method]["threshold"]
    print("\nOwner check, on photos it never trained on:")
    for m, s in summary.items():
        refused = f", strangers' holds refused {s['stranger_refused_holds']:.0%}" if "stranger_refused_holds" in s else ""
        print(f"  {m:9s} threshold {s['threshold']:.2f}: {owner}'s holds let in {s['owner_accepted_holds']:.0%}"
              f"{refused}{'   <- used' if m == method else ''}")
    if summary[method]["owner_accepted_holds"] < OWNER_MIN_ACCEPT:
        print(f"WARNING: even the lowest threshold lets {owner} in on fewer than {OWNER_MIN_ACCEPT:.0%} "
              "of held-out holds. The owner check isn't working yet.")

    # Final network: everything, plus the owner's averages from all their photos.
    print(f"\nFinal network: training on all {data.n} photos")
    net, hist = train(data, np.arange(data.n), epochs, args.seed)
    own_all = np.where(data.owner & (data.label != NONE))[0]
    _, _, d_all = predict(net, inputs(data.imgs[own_all]))
    mu, sd, scale = prototypes(d_all, data.label[own_all])
    weights = {**weights_of(net), "proto_mu": mu, "proto_sd": sd, "proto_scale": np.array(scale, np.float32)}
    diff = check_numpy_matches_torch(net, weights, data.imgs[np.random.default_rng(1).permutation(data.n)[:200]])
    print(f"numpy vs PyTorch, biggest difference: {diff:.2e} ({'OK' if diff < CHECK_TOL else 'MISMATCH'})")

    results = {
        "trained": date.today().isoformat(),
        "owner": owner,
        "photos": int(data.n),
        "photos_by_person": {p: int((data.person == p).sum()) for p in sorted(set(data.person))},
        "epochs": epochs,
        "held_out_counting": held_desc,
        "count_acc": round(count_acc, 4),
        "count_trusted_share": round(trusted_share, 4),
        "count_trusted_acc": round(trusted_acc, 4),
        "count_acc_per_label": {lab: round(float((count_pred[data.label[owner_idx] == li] == li).mean()), 4)
                                for li, lab in enumerate(LABELS) if (data.label[owner_idx] == li).any()},
        "confusion": m_count.tolist(),
        "count_acc_in_stranger_runs": {str(f["without"]): round(f["count_acc"], 4) for f in folds},
        "stranger_count_acc": {str(f["without"]): round(f["stranger_count_acc"], 4) for f in folds if "stranger" in f},
        "owner_method": method,
        "owner_threshold": owner_t,
        "owner_checks": summary,
        "owner_min_accept": OWNER_MIN_ACCEPT,
        "count_conf": LP.CONF,
        "hold_frames": HOLD_FRAMES,
        "numpy_vs_torch_max_diff": diff,
    }
    meta = {"labels": LABELS, "owner": owner, "save_size": FN.SAVE_SIZE, "size": FN.NET_SIZE,
            "crop_frac": FN.CROP_FRAC, "count_conf": LP.CONF, "owner_method": method, "owner_threshold": owner_t,
            "owner_check": True, "owner_tested_on_strangers": bool(friends), "trained": results["trained"],
            "photos": results["photos"], "count_acc_held_out": results["count_acc"],
            "stranger_refused_holds": summary[method].get("stranger_refused_holds")}
    args.model.parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.model, **weights, meta=np.array(json.dumps(meta)))
    print(f"Exported {args.model}")

    np.savez_compressed(args.out / "train_snapshots.npz", filters=np.stack(hist["filters"]),
                        train_loss=np.array(hist["train"]))
    (args.out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    fig_confusion(m_count, f"Counting on photos it never trained on: {count_acc:.0%} right",
                  args.out / "confusion.png")
    fig_loss(hist, folds, args.out / "loss.png")
    fig_owner(folds, summary, method, owner, args.out / "owner.png")
    fig_filters(weights["conv1_w"], args.out / "filters.png")
    fig_network(owner, method, args.out / "network.png")

    print(f"\nCounting (held out): {results['count_acc']:.1%} of frames right")
    s = summary[method]
    print(f"Owner check ({method}, threshold {owner_t:.2f}): {s['owner_accepted_holds']:.0%} of {owner}'s holds "
          "let in" + (f", {s['stranger_refused_holds']:.0%} of strangers' holds refused"
                      if "stranger_refused_holds" in s else " (not tested on strangers)"))
    print(f"Figures and results.json in {args.out}")
    if diff >= CHECK_TOL:
        sys.exit("The numpy forward pass doesn't match PyTorch: don't deploy this.")


if __name__ == "__main__":
    main()
