#!/usr/bin/env python3
"""Stop-action frames that explain the safe's network, drawn from the real
trained network running on one of your photos. You add the voice-over.

    python FingerLock/movie/render.py                       # a photo of 3 fingers from your newest session
    python FingerLock/movie/render.py --photo PATH.png      # a different 128 x 128 photo
    python FingerLock/movie/render.py --untrained           # random weights (to try it before training)

Writes PNG frames to movie/frames/<scene>/ (gitignored), one video per scene
(movie/scene_XX_<name>.mp4, so each can be stretched to fit your narration in
iMovie) and the whole thing as movie/infallible_safe.mp4. Frames change at
about 3 a second during the animated steps, for the stop-action look.

movie/narration.md is the voice-over, one "## NN" block per scene. Each scene
lasts as long as its block takes to say at WPM words a minute, plus a breath,
so after changing the words, render again: the scene times printed at the end
follow the new script.

Scenes:
  01 title                       07 deeper layers
  02 pixels                      08 fully connected, softmax
  03 convolution, step by step   09 training
  04 all 8 filters               10 the safe's rules
  05 ReLU                        11 end
  06 max pooling, step by step
The numbers on screen come from figures/results.json, figures/bench.json and
settings.json. Nothing here ever shows your real code: the rules scene uses a
made-up digit.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import DATA_DIR, FIG_DIR, MODEL_PATH, OWNER, load_settings  # noqa: E402
import fingernet as FN  # noqa: E402
import leds  # noqa: E402
import lock_policy as LP  # noqa: E402

BG, INK, INK2, LINE = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE, GREEN, RED = "#2a78d6", "#eb6834", "#1baf7a", "#d33b3b"
STEP = 1 / 3            # seconds per animated step (stop-action pace)
NARRATION = HERE / "narration.md"
WPM = 150               # narration pace: a scene lasts as long as its block takes to say...
BREATH_S = 1.0          # ...plus a breath before the next scene
FFMPEG_CANDIDATES = ["ffmpeg", "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]
plt.rcParams.update({"font.size": 13, "text.color": INK, "axes.edgecolor": LINE})


# ---- Drawing helpers --------------------------------------------------------------------

class Movie:
    def __init__(self, out_dir):
        self.frames_dir = out_dir / "frames"
        shutil.rmtree(self.frames_dir, ignore_errors=True)
        self.out_dir = out_dir
        self.items = []                 # (scene, png, seconds)

    def add(self, fig, scene, seconds):
        folder = self.frames_dir / scene
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{len(list(folder.glob('*.png'))) + 1:04d}.png"
        fig.savefig(path, dpi=100, facecolor=BG)
        plt.close(fig)
        self.items.append((scene, path, seconds))


def frame(title, caption=None):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    fig.patch.set_facecolor(BG)
    fig.text(0.035, 0.915, title, fontsize=26, weight="bold")
    if caption:
        fig.text(0.035, 0.035, "\n".join(textwrap.wrap(caption, 105)), fontsize=16, color=INK2, va="bottom")
    return fig


def image(fig, rect, img, cmap="gray", vmin=None, vmax=None, title=None):
    ax = fig.add_axes(rect)
    ax.imshow(img, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=13, color=INK2, loc="left")
    return ax


def numbers(fig, rect, vals, cmap, vmin, vmax, fmt, title=None, highlight=None, fontsize=11):
    """A small grid of numbers on coloured cells."""
    ax = image(fig, rect, vals, cmap, vmin, vmax, title)
    cm = matplotlib.colormaps[cmap]
    for (r, c), v in np.ndenumerate(vals):
        if np.isfinite(v):
            red, green, blue, _ = cm(float(np.clip((v - vmin) / (vmax - vmin + 1e-9), 0, 1)))
            light = 0.299 * red + 0.587 * green + 0.114 * blue > 0.5
            ax.text(c, r, fmt.format(v), ha="center", va="center", fontsize=fontsize,
                    color="black" if light else "white")
    if highlight:
        r, c, h, w = highlight
        ax.add_patch(Rectangle((c - 0.5, r - 0.5), w, h, fill=False, ec=RED, lw=3))
    return ax


def box(ax, r, c, h, w, colour=RED, lw=2.5):
    ax.add_patch(Rectangle((c - 0.5, r - 0.5), w, h, fill=False, ec=colour, lw=lw))


def arrow(fig, x0, x1, y, text=None):
    fig.add_artist(matplotlib.patches.FancyArrowPatch((x0, y), (x1, y), transform=fig.transFigure,
                                                      arrowstyle="-|>", mutation_scale=22, color=INK2, lw=2))
    if text:
        fig.text((x0 + x1) / 2, y + 0.03, text, ha="center", fontsize=12, color=INK2)


def led(fig, rect, arr, title=None):
    ax = fig.add_axes(rect)
    ax.set_facecolor("#111111")
    rows, cols = arr.shape
    ys, xs = np.mgrid[0:rows, 0:cols]
    on = arr.reshape(-1) > 0
    ax.scatter(xs.reshape(-1)[~on], ys.reshape(-1)[~on], s=90, color="#2a2a2a")
    ax.scatter(xs.reshape(-1)[on], ys.reshape(-1)[on], s=90,
               color=[(1.0, 0.15, 0.1, 0.25 + 0.75 * v / 7) for v in arr.reshape(-1)[on]])
    ax.set_xlim(-0.7, cols - 0.3)
    ax.set_ylim(rows - 0.3, -0.7)
    ax.set_xticks([])
    ax.set_yticks([])
    if title:
        ax.set_title(title, fontsize=12, color=INK2, loc="left")
    return ax


def sym(a):
    m = float(np.abs(a).max()) or 1.0
    return -m, m


# ---- Scenes ----------------------------------------------------------------------------------

def s01_title(mv):
    fig = frame("")
    fig.text(0.5, 0.58, "The Infallible Safe", ha="center", fontsize=48, weight="bold")
    fig.text(0.5, 0.47, "How its neural network counts your fingers", ha="center", fontsize=20, color=INK2)
    fig.text(0.5, 0.36, "a convolutional neural network built from scratch in PyTorch, running on an Arduino UNO Q",
             ha="center", fontsize=15, color=INK2)
    mv.add(fig, "01_title", 3.0)


def s02_pixels(mv, photo, img64):
    fig = frame("1. What the camera sees", "A camera looks down at the mat. The safe keeps a grey square of it.")
    image(fig, [0.06, 0.16, 0.42, 0.68], photo, "gray", 0, 255, "the camera's view of the mat")
    mv.add(fig, "02_pixels", 2.5)

    fig = frame("1. What the camera sees", "Shrunk to 64 x 64: 4,096 numbers, each one how bright that spot is.")
    image(fig, [0.06, 0.16, 0.36, 0.68], photo, "gray", 0, 255, "128 x 128")
    arrow(fig, 0.44, 0.52, 0.5, "shrink")
    image(fig, [0.55, 0.16, 0.36, 0.68], img64, "gray", 0, 255, "64 x 64 (what the network sees)")
    mv.add(fig, "02_pixels", 2.5)

    r0, c0 = _busiest(img64, 8)
    fig = frame("1. What the camera sees",
                "Zoomed in: just numbers. The network then subtracts the picture's average and divides by its "
                "spread, so a dim room and a bright room give the same numbers.")
    ax = image(fig, [0.05, 0.16, 0.36, 0.68], img64, "gray", 0, 255, "64 x 64")
    box(ax, r0, c0, 8, 8)
    arrow(fig, 0.43, 0.5, 0.5, "zoom")
    numbers(fig, [0.52, 0.16, 0.42, 0.68], img64[r0:r0 + 8, c0:c0 + 8], "gray", 0, 255, "{:.0f}",
            "8 x 8 of them, brightness 0-255", fontsize=12)
    mv.add(fig, "02_pixels", 3.5)


def _busiest(img, size):
    """Top-left of the size x size block with the most change in it (an edge of the hand)."""
    g = np.abs(np.diff(img, axis=0))[:, :-1] + np.abs(np.diff(img, axis=1))[:-1, :]
    best, at = -1, (0, 0)
    for r in range(0, img.shape[0] - size, 2):
        for c in range(0, img.shape[1] - size, 2):
            v = g[r:r + size - 1, c:c + size - 1].sum()
            if v > best:
                best, at = v, (r, c)
    return at


def s03_convolution(mv, x, acts, w, k):
    W, b = w["conv1_w"][k, 0], float(w["conv1_b"][k])
    F = acts["conv1"][k]
    xin = x[0]
    lo, hi = sym(F)
    xlo, xhi = -2.5, 2.5
    spread = np.lib.stride_tricks.sliding_window_view(np.pad(xin, 1), (3, 3)).std(axis=(2, 3))
    r_star, c_star = np.unravel_index(np.argmax(spread), spread.shape)    # an edge of the hand
    r, c_first = int(r_star), int(max(0, min(64 - 6, c_star - 2)))
    xp = np.pad(xin, 1)
    filled = np.full(F.shape, np.nan)
    filled[:r] = F[:r]
    filled[r, :c_first] = F[r, :c_first]

    for step, c in enumerate(range(c_first, c_first + 6)):
        patch = xp[r:r + 3, c:c + 3]
        prod = patch * W
        out = prod.sum() + b
        filled[r, c] = F[r, c]
        fig = frame("2. Convolution: one filter, one spot at a time",
                    f"Multiply the 9 numbers under the window by the filter's 9 weights, add them up, add the bias "
                    f"({b:+.2f}). That one number goes in the feature map. Then slide one step right.")
        ax = image(fig, [0.03, 0.2, 0.27, 0.62], xin, "gray", xlo, xhi, "input (64 x 64)")
        box(ax, r - 1, c - 1, 3, 3)
        numbers(fig, [0.33, 0.48, 0.13, 0.3], patch, "gray", xlo, xhi, "{:.1f}", "under the window")
        fig.text(0.475, 0.62, "x", fontsize=26, ha="center")
        numbers(fig, [0.5, 0.48, 0.13, 0.3], W, "RdBu_r", *sym(W), "{:.2f}", f"filter {k + 1}'s weights")
        fig.text(0.645, 0.62, "=", fontsize=26, ha="center")
        numbers(fig, [0.67, 0.48, 0.13, 0.3], prod, "RdBu_r", *sym(prod), "{:.2f}", "products")
        fig.text(0.33, 0.36, f"sum of the 9 products {prod.sum():+.2f}  +  bias {b:+.2f}  =  {out:+.2f}",
                 fontsize=17, weight="bold")
        ax2 = image(fig, [0.835, 0.48, 0.15, 0.3], filled, "RdBu_r", lo, hi, "feature map")
        box(ax2, r, c, 1, 1)
        mv.add(fig, "03_convolution", 2.2 if step == 0 else (1.2 if step < 3 else 0.7))

    for rows_done in range(r + 1, 64 + 1, 8):
        filled[:rows_done] = F[:rows_done]
        fig = frame("2. Convolution: one filter, one spot at a time",
                    "...and the same 9 weights slide over all 4,096 spots.")
        ax = image(fig, [0.05, 0.16, 0.4, 0.68], xin, "gray", xlo, xhi, "input")
        box(ax, rows_done - 2, 0, 3, 64, colour=RED, lw=1.5)
        image(fig, [0.53, 0.16, 0.4, 0.68], filled, "RdBu_r", lo, hi, f"filter {k + 1}'s feature map")
        mv.add(fig, "03_convolution", STEP)

    fig = frame("2. Convolution: one filter, one spot at a time",
                f"Filter {k + 1}'s feature map: red where the picture matches its 3 x 3 pattern, blue where it's "
                "the opposite. Nobody chose the pattern: training did.")
    image(fig, [0.05, 0.16, 0.4, 0.68], xin, "gray", xlo, xhi, "input")
    image(fig, [0.53, 0.16, 0.4, 0.68], F, "RdBu_r", lo, hi, f"filter {k + 1}'s feature map")
    mv.add(fig, "03_convolution", 3.0)


def s04_all_filters(mv, acts, w):
    fig = frame("3. Eight filters, eight feature maps",
                "Layer 1 has 8 filters. Each one looks for its own small pattern everywhere in the picture.")
    for k in range(8):
        x0 = 0.04 + k * 0.118
        numbers(fig, [x0, 0.6, 0.1, 0.18], w["conv1_w"][k, 0], "RdBu_r", *sym(w["conv1_w"]), "{:.1f}",
                f"filter {k + 1}", fontsize=8)
        image(fig, [x0, 0.2, 0.105, 0.3], acts["conv1"][k], "RdBu_r", *sym(acts["conv1"][k]))
    fig.text(0.04, 0.47, "each filter's feature map (64 x 64):", fontsize=13, color=INK2)
    mv.add(fig, "04_all_filters", 4.0)


def s05_relu(mv, acts, k):
    F, R = acts["conv1"][k], acts["conv1_relu"][k]
    fig = frame("4. ReLU", "As in the V-fit: negatives become 0. Each map keeps only where its pattern was found.")
    image(fig, [0.05, 0.16, 0.38, 0.68], F, "RdBu_r", *sym(F), "before (negatives in blue)")
    arrow(fig, 0.45, 0.53, 0.5, "max(0, x)")
    image(fig, [0.56, 0.16, 0.38, 0.68], R, "inferno", 0, float(R.max()) or 1, "after ReLU")
    mv.add(fig, "05_relu", 3.0)


def s06_pooling(mv, acts, k):
    R, P = acts["conv1_relu"][k], acts["conv1_pool"][k]
    r_star, c_star = np.unravel_index(np.argmax(R), R.shape)
    r0, c0 = int(min(56, max(0, r_star - 4))) // 2 * 2, int(min(56, max(0, c_star - 4))) // 2 * 2
    region = R[r0:r0 + 8, c0:c0 + 8]
    pooled = np.full((4, 4), np.nan)
    vmax = float(region.max()) or 1.0
    windows = [(i, j) for i in range(4) for j in range(4)]
    for n, (i, j) in enumerate(windows):
        pooled[i, j] = region[2 * i:2 * i + 2, 2 * j:2 * j + 2].max()
        if n >= 4 and n not in (7, 11, 15):
            continue
        fig = frame("5. Max pooling", "Look at each 2 x 2 block and keep only its biggest number. "
                    "Half the width, half the height, and the strongest responses survive.")
        ax = numbers(fig, [0.05, 0.16, 0.42, 0.68], region, "inferno", 0, vmax, "{:.1f}",
                     "8 x 8 of the ReLU map", fontsize=10)
        box(ax, 2 * i, 2 * j, 2, 2, colour="#00c8ff", lw=4)
        arrow(fig, 0.5, 0.57, 0.5, "biggest")
        ax2 = numbers(fig, [0.6, 0.27, 0.3, 0.45], pooled, "inferno", 0, vmax, "{:.1f}", "4 x 4 after pooling")
        box(ax2, i, j, 1, 1, colour="#00c8ff", lw=4)
        mv.add(fig, "06_pooling", 1.5 if n < 4 else STEP * 2)

    fig = frame("5. Max pooling", "The whole map: 64 x 64 becomes 32 x 32. Less to compute, same message.")
    image(fig, [0.05, 0.16, 0.4, 0.68], R, "inferno", 0, float(R.max()) or 1, "after ReLU, 64 x 64")
    arrow(fig, 0.47, 0.55, 0.5, "max pool 2 x 2")
    image(fig, [0.6, 0.27, 0.27, 0.45], P, "inferno", 0, float(R.max()) or 1, "after pooling, 32 x 32")
    mv.add(fig, "06_pooling", 3.0)


def _grid(fig, maps, rect, cols, cmap="inferno"):
    x0, y0, wd, ht = rect
    rows = int(np.ceil(len(maps) / cols))
    cw, ch = wd / cols, ht / rows
    for n, m in enumerate(maps):
        r, c = divmod(n, cols)
        image(fig, [x0 + c * cw, y0 + (rows - 1 - r) * ch, cw * 0.92, ch * 0.9], m, cmap, 0, float(m.max()) or 1)


def s07_deeper(mv, acts):
    fig = frame("6. Deeper layers",
                "Layer 2: 16 filters, each 3 x 3 across all 8 maps at once, so they can combine layer 1's "
                "patterns into bigger shapes. ReLU and pooling again: 16 maps of 16 x 16.")
    _grid(fig, acts["conv2_pool"], [0.05, 0.16, 0.9, 0.66], 8)
    mv.add(fig, "07_deeper", 4.0)
    fig = frame("6. Deeper layers",
                "Layer 3: 32 filters, then ReLU and pooling: 32 maps of 8 x 8. That's 2,048 numbers "
                "describing the picture.")
    _grid(fig, acts["conv3_pool"], [0.05, 0.16, 0.9, 0.66], 16)
    mv.add(fig, "07_deeper", 4.0)


def s08_heads(mv, acts, owner):
    flat = acts["conv3_pool"].reshape(1, -1)
    h = acts["fc"]
    fig = frame("7. Fully connected: the hand's description",
                "Flatten the 32 maps into one row of 2,048 numbers. Each of the next layer's 64 neurons adds up "
                "all 2,048, each with its own weight, then ReLU: 64 numbers that describe the hand.")
    image(fig, [0.05, 0.6, 0.9, 0.06], np.repeat(flat, 40, axis=0), "inferno", 0, float(flat.max()) or 1,
          "2,048 numbers in a row")
    fig.add_artist(matplotlib.patches.FancyArrowPatch((0.5, 0.585), (0.5, 0.5), transform=fig.transFigure,
                                                      arrowstyle="-|>", mutation_scale=22, color=INK2, lw=2))
    ax = fig.add_axes([0.05, 0.18, 0.9, 0.26])
    ax.bar(range(64), h, color=BLUE)
    ax.set_xlim(-1, 64)
    ax.set_title("the 64-number description", fontsize=13, color=INK2, loc="left")
    ax.set_yticks([])
    mv.add(fig, "08_heads", 4.0)

    scores, probs = acts["count_scores"], acts["count_probs"]
    best = int(np.argmax(probs))
    names = ["no hand", "0", "1", "2", "3", "4", "5"]
    colours = [BLUE if i == best else "#b9b8b2" for i in range(7)]
    fig = frame("8. Softmax: the answer",
                "A last layer turns the 64 numbers into 7 scores, one per answer. Softmax turns the scores into "
                "probabilities that add up to 1.")
    for vals, rect, title in [(scores, [0.1, 0.3, 0.3, 0.5], "7 scores"),
                              (probs, [0.63, 0.3, 0.3, 0.5], f"probabilities: '{names[best]}' at {probs[best]:.1%}")]:
        ax = fig.add_axes(rect)
        ax.barh(range(7), vals, color=colours)
        ax.set_yticks(range(7), names)
        ax.invert_yaxis()
        ax.set_title(title, fontsize=15, loc="left")
        if vals is probs:
            ax.set_xlim(0, 1)
        else:
            ax.axvline(0, color=INK2, lw=1)
    arrow(fig, 0.44, 0.54, 0.55, "softmax")
    fig.text(0.035, 0.17, f"(An optional \"is it {owner.title()}'s hand?\" check reads the same 64 numbers. "
             "It's switched off: anyone with the code can open the safe.)", fontsize=12, color=INK2)
    mv.add(fig, "08_heads", 4.5)


def _augmented(photo, n, seed=7):
    """n random versions of the photo, made by train.py's own augment()."""
    with plt.rc_context():              # train.py restyles matplotlib when it's imported
        import train
    rng = np.random.default_rng(seed)
    return [train.augment(photo, rng) for _ in range(n)]


def s09_training(mv, snapshots, n_weights, photo, results):
    if snapshots is None:
        return
    by = results.get("photos_by_person", {})
    who = ", ".join(f"{n:,} of {p.title()}'s" for p, n in sorted(by.items(), key=lambda kv: (kv[0] != results.get("owner"), kv[0])))
    fig = frame("9. Training: where the weights come from",
                f"{results.get('photos', sum(by.values())):,} photos ({who}). Every pass, each one comes back a "
                "new random way: spun, shifted, scaled, flipped, brighter or darker.")
    image(fig, [0.04, 0.2, 0.3, 0.6], photo, "gray", 0, 255, "one of my photos")
    arrow(fig, 0.36, 0.44, 0.5, "random")
    for n, img in enumerate(_augmented(photo, 6)):
        r, c = divmod(n, 3)
        image(fig, [0.47 + c * 0.17, 0.51 - r * 0.31, 0.16, 0.28], img, "gray", 0, 255)
    mv.add(fig, "09_training", 4.0)

    filt, loss = snapshots["filters"], snapshots["train_loss"]
    epochs = sorted(set([0, 1, 2, 3, 5, 8, 12, 18, len(filt) - 1]) & set(range(len(filt))))
    lim = float(np.abs(filt).max())
    for e in epochs:
        fig = frame("9. Training: where the weights come from",
                    f"Each pass, wrong answers make a loss. Backpropagation finds which way to nudge all "
                    f"{n_weights:,} weights, and gradient descent takes a small step downhill: the V-fit, scaled up.")
        for k in range(filt.shape[1]):
            numbers(fig, [0.04 + k * 0.118, 0.56, 0.1, 0.2], filt[e, k, 0], "RdBu_r", -lim, lim, "{:.1f}",
                    f"filter {k + 1}", fontsize=8)
        fig.text(0.04, 0.8, f"layer 1's filters after {e} pass{'es' if e != 1 else ''}"
                 + (" (random to start)" if e == 0 else ""), fontsize=15)
        ax = fig.add_axes([0.06, 0.24, 0.88, 0.25])
        ax.plot(np.arange(1, len(loss) + 1), loss, color=LINE, lw=2)
        if e:
            ax.plot(np.arange(1, e + 1), loss[:e], color=BLUE, lw=3)
        ax.set_xlim(0, len(loss) + 1)
        ax.set_ylabel("loss")
        ax.set_xlabel("pass over the training photos")
        mv.add(fig, "09_training", 1.2 if e in (0, epochs[-1]) else STEP * 2)


def s10_rules(mv, conf, fps, lockout, open_s):
    title, pct = "10. The safe's rules", f"{conf:.0%}"
    fig = frame(title, f"About {fps:.0f} times a second on the UNO Q. The network only says what it sees; "
                "the rules decide what happens.")
    boxes = [fig.text(0.13 + n * 0.245, 0.5, step, ha="center", va="center", fontsize=18, linespacing=1.4,
                      bbox=dict(boxstyle="round,pad=0.7", fc="white", ec=BLUE if n == 2 else INK2, lw=2))
             for n, step in enumerate(["camera\nframe", "network:\n7 probabilities", "the rules",
                                       "LEDs, latch,\nalerts"])]
    fig.canvas.draw()                   # so the boxes know their size
    edges = [fig.transFigure.inverted().transform(b.get_bbox_patch().get_window_extent())[:, 0] for b in boxes]
    for (_, right), (left, _) in zip(edges, edges[1:]):
        arrow(fig, right + 0.012, left - 0.012, 0.5)
    mv.add(fig, "10_rules", 3.0)

    def show(caption, arr, note, seconds):
        fig = frame(title, caption)
        led(fig, [0.3, 0.3, 0.4, 0.4], arr, note)
        mv.add(fig, "10_rules", seconds)

    show("Asleep: the LEDs stay dark until someone presses the button.", leds.render({"state": "idle"}),
         "asleep", 1.5)
    show("Press the button: it wakes up for one code. A faint dot for each digit, and a padlock.",
         leds.render({"state": "locked", "reading": "none", "entered": 0, "code_len": 3, "hold": 0}),
         "awake: 0 of 3 digits", 2.0)
    times = np.round(np.arange(0, 1.31, 0.1), 2)
    prob = np.clip(0.15 + 2.5 * times, 0, 0.95)          # an illustration, not a recording
    t_sure = float(times[np.argmax(prob >= conf)])       # when it first gets sure enough
    for n, t in enumerate(times):
        sure = prob[n] >= conf
        held = t - t_sure if sure else 0.0
        accepted = sure and held + LP.EPS >= LP.HOLD_S
        status = {"state": "locked", "reading": "3" if sure else None, "hold": min(1, held / LP.HOLD_S),
                  "entered": 1 if accepted else 0, "code_len": 3, "need_clear": accepted}
        fig = frame(title, f"A digit counts once the network has been at least {pct} sure of the same answer "
                    f"for {LP.HOLD_S:g} s. The bar under the digit fills while you hold it.")
        ax = fig.add_axes([0.06, 0.26, 0.5, 0.55])
        ax.plot(times[:n + 1], prob[:n + 1], color=BLUE, lw=3)
        ax.axhline(conf, color=INK2, ls="--")
        ax.text(0.01, conf + 0.02, pct, color=INK2)
        ax.set_xlim(0, times[-1] + 0.05)
        ax.set_ylim(0, 1)
        ax.set_xlabel("seconds since the hand arrived")
        ax.set_title("probability of '3' (a made-up example)", fontsize=14, loc="left")
        led(fig, [0.62, 0.35, 0.33, 0.3], leds.render(status), "the safe's LED matrix")
        fig.text(0.62, 0.25, "digit accepted" if accepted else
                 (f"holding... {held:.1f} / {LP.HOLD_S:g} s" if sure else "not sure yet"),
                 fontsize=18, weight="bold", color=GREEN if accepted else INK)
        mv.add(fig, "10_rules", 1.5 if accepted else STEP)
        if accepted:
            break
    show("Then the hand leaves the mat (the digit dims) before the next one can start.",
         leds.render({"state": "locked", "reading": "none", "entered": 1, "code_len": 3, "hold": 0,
                      "need_clear": True}), "1 of 3 digits in", 2.0)
    show(f"After the third digit, the right code swings the latch open. It locks again after {open_s:g} s, "
         "or straight away at a button press.", leds.render({"state": "open"}), "open", 2.5)
    show("A wrong code gets an X, and the safe goes back to sleep. It never says which digit was wrong.",
         leds.screen("wrong"), "wrong code", 2.0)
    show(f"Three wrong codes in a row lock it for {lockout:g} s, counting down, and send an alert with a "
         "photo of the hand.", leds.lockout(lockout), "lockout", 2.5)
    show("The duress code opens it exactly the same way, but silently sends an alert with a photo.",
         leds.render({"state": "open"}), "duress code: looks just like open", 2.5)


def s11_end(mv, n_weights, fps):
    fig = frame("")
    fig.text(0.5, 0.56, f"{n_weights:,} weights, trained from scratch", ha="center", fontsize=34, weight="bold")
    fig.text(0.5, 0.45, f"counting fingers about {fps:.0f} times a second on an Arduino UNO Q", ha="center",
             fontsize=20, color=INK2)
    mv.add(fig, "11_end", 3.0)


# ---- Video ------------------------------------------------------------------------------------

def ffmpeg():
    for c in FFMPEG_CANDIDATES:
        p = shutil.which(c) or (c if Path(c).exists() else None)
        if p:
            return p
    return None


def write_video(items, path):
    """items: [(png, seconds)]. H.264 via ffmpeg if there is one, else OpenCV."""
    exe = ffmpeg()
    if exe:
        lst = path.with_suffix(".txt")
        lines = []
        for png, secs in items:
            lines += [f"file '{png}'", f"duration {secs:.3f}"]
        lines.append(f"file '{items[-1][0]}'")           # older ffmpegs need the last file twice...
        lst.write_text("\n".join(lines) + "\n")
        total = sum(secs for _, secs in items)          # ...newer ones then show it twice as long, so cut at the total
        subprocess.run([exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "18", "-t", f"{total:.3f}",
                        str(path)], check=True)
        lst.unlink()
        return
    import cv2
    first = cv2.imread(str(items[0][0]))
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"avc1"), 30, (first.shape[1], first.shape[0]))
    for png, secs in items:
        img = cv2.imread(str(png))
        for _ in range(max(1, round(secs * 30))):
            vw.write(img)
    vw.release()


# ---- Main ---------------------------------------------------------------------------------------

def narration_seconds(path=NARRATION, wpm=WPM):
    """{"03": seconds, ...}: how long each "## NN" block of narration.md takes to
    say, plus a breath. Lines starting with ">" are notes, not said. A number
    counts one word per digit ("4,096" is "four thousand and ninety-six")."""
    if not path.exists():
        return {}
    words, scene = {}, None
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            m = re.match(r"##\s+(\d\d)\b", line)
            scene = m.group(1) if m else None
        elif scene and not line.lstrip().startswith(">"):
            words[scene] = words.get(scene, 0) + sum(
                max(1, len(re.sub(r"\D", "", w))) if re.search(r"\d", w) else 1
                for w in line.split() if re.search(r"\w", w))
    return {s: n / wpm * 60 + BREATH_S for s, n in words.items() if n}


def _json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def pick_photo(owner, net=None, label="3"):
    """A photo of `label` fingers from the owner's newest session (the one at the
    safe): the one the trained network is surest about, else the middle one."""
    import cv2
    files = sorted((DATA_DIR / owner).glob(f"*/{label}/*.png"))
    if not files:
        return None
    stamp = lambda f: int(m.group(1)) if (m := re.match(r"(\d+)", f.stem)) else 0     # noqa: E731
    newest = max(files, key=stamp).parent.parent
    files = [f for f in files if f.parent.parent == newest]
    if net is None:
        return files[len(files) // 2]
    li = FN.COUNT_LABELS.index(label)
    return max(files, key=lambda f: net.forward(FN.net_input(cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)))[0][li])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photo", type=Path, help="a 128 x 128 grey photo from capture.py")
    ap.add_argument("--model", type=Path, default=MODEL_PATH)
    ap.add_argument("--snapshots", type=Path, default=FIG_DIR / "train_snapshots.npz")
    ap.add_argument("--untrained", action="store_true", help="random weights (to try it before training)")
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--owner", default=OWNER)
    args = ap.parse_args()

    import cv2
    trained = not args.untrained and args.model.exists()
    if not trained and not args.untrained:
        print(f"No trained model at {args.model}: using random weights.")
    net = FN.FingerNet(args.model) if trained else FN.FingerNet(weights=FN.random_weights())
    path = args.photo or pick_photo(args.owner, net if trained else None)
    if path is None:
        sys.exit("No photo: pass --photo, or take some with capture.py first.")
    photo = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if photo.shape != (FN.SAVE_SIZE, FN.SAVE_SIZE):
        photo = np.clip(np.rint(FN.shrink(photo, FN.SAVE_SIZE)), 0, 255).astype(np.uint8)
    x = FN.net_input(photo)
    _, _, acts = net.forward(x, keep=True)
    w = net.w
    # The filter followed through scenes 3-6: the most edge-like one. Its weights nearly cancel out, so it
    # answers to changes in brightness (an edge of the hand), not to brightness itself.
    w1 = w["conv1_w"][:, 0]
    k = int(np.argmin(np.abs(w1.sum(axis=(1, 2))) / np.abs(w1).sum(axis=(1, 2))))
    snapshots = dict(np.load(args.snapshots)) if args.snapshots.exists() and trained else None
    n_weights = int(sum(v.size for name, v in w.items() if name.split("_")[0] in
                        ("conv1", "conv2", "conv3", "fc", "count", "owner")))
    settings, results, bench = load_settings(), _json(FIG_DIR / "results.json"), _json(FIG_DIR / "bench.json")
    conf = settings.get("conf")             # as lock_policy.make_policy() picks it
    conf = float(conf) if conf is not None else float(net.meta.get("count_conf", LP.CONF))
    fps = float(bench.get("board", {}).get("fps", 15))

    mv = Movie(args.out)
    s01_title(mv)
    s02_pixels(mv, photo, FN.shrink(photo, FN.NET_SIZE))
    s03_convolution(mv, x, acts, w, k)
    s04_all_filters(mv, acts, w)
    s05_relu(mv, acts, k)
    s06_pooling(mv, acts, k)
    s07_deeper(mv, acts)
    s08_heads(mv, acts, args.owner)
    s09_training(mv, snapshots, n_weights, photo, results)
    s10_rules(mv, conf, fps, float(settings.get("lockout_s", LP.LOCKOUT_S)),
              float(settings.get("open_s", LP.OPEN_S)))
    s11_end(mv, n_weights, fps)

    # Each scene lasts as long as its narration takes to say: every frame stretched (or squeezed) alike.
    scenes = list(dict.fromkeys(s for s, _, _ in mv.items))
    said = narration_seconds()
    for s in scenes:
        if said.get(s[:2]):
            scale = said[s[:2]] / sum(secs for sc, _, secs in mv.items if sc == s)
            mv.items = [(sc, p, secs * scale if sc == s else secs) for sc, p, secs in mv.items]
    for s in scenes:
        write_video([(p, secs) for sc, p, secs in mv.items if sc == s], args.out / f"scene_{s}.mp4")
    write_video([(p, secs) for _, p, secs in mv.items], args.out / "infallible_safe.mp4")
    total = sum(secs for _, _, secs in mv.items)
    print(json.dumps({"photo": str(path), "frames": len(mv.items), "seconds": round(total, 1)}, indent=2))
    print("Scenes" + (f" (timed to narration.md at {WPM} words a minute):" if said else ":"))
    t = 0.0
    for s in scenes:
        secs = sum(secs for sc, _, secs in mv.items if sc == s)
        print(f"  {s:18s} {int(t // 60)}:{t % 60:04.1f}  {secs:5.1f} s")
        t += secs
    print(f"Video: {args.out / 'infallible_safe.mp4'} (+ one per scene). Frames in {mv.frames_dir}")


if __name__ == "__main__":
    main()
