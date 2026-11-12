#!/usr/bin/env python3
"""Stop-action frames that explain the safe's network, drawn from the real
trained network running on one of your photos. You add the voice-over.

    python FingerLock/movie/render.py                       # a photo of 3 fingers from data/SAM
    python FingerLock/movie/render.py --photo PATH.png      # a different 128 x 128 photo
    python FingerLock/movie/render.py --untrained           # random weights (to try it before training)

Writes PNG frames to movie/frames/<scene>/ (gitignored), one video per scene
(movie/scene_XX_<name>.mp4, so each can be stretched to fit your narration in
iMovie) and the whole thing as movie/infallible_safe.mp4. Frames change at
about 3 a second during the animated steps, for the stop-action look.
movie/narration.md has a draft voice-over per scene.

Scenes:
  01 title                 07 deeper layers
  02 pixels                08 fully connected, softmax, owner check
  03 convolution, step by step
  04 all 8 filters         09 training
  05 ReLU                  10 the safe's rules
  06 max pooling, step by step   11 end
Nothing here ever shows your real code: the rules scene uses a made-up digit.
"""
import argparse
import json
import shutil
import subprocess
import sys
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
        fig.text(0.035, 0.05, caption, fontsize=16, color=INK2, wrap=True)
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

def s01_title(mv, owner):
    fig = frame("")
    fig.text(0.5, 0.58, "The Infallible Safe", ha="center", fontsize=48, weight="bold")
    fig.text(0.5, 0.47, "How its network counts your fingers, and knows whose hand it is", ha="center",
             fontsize=20, color=INK2)
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
    fig.text(0.04, 0.53, "each filter's feature map (64 x 64):", fontsize=13, color=INK2)
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


def s08_heads(mv, acts, net, owner):
    flat = acts["conv3_pool"].reshape(1, -1)
    h = acts["fc"]
    fig = frame("7. Fully connected: the hand's description",
                "Flatten the 32 maps into one row of 2,048 numbers. Each of the next layer's 64 neurons adds up "
                "all 2,048, each with its own weight, then ReLU: 64 numbers that describe the hand.")
    image(fig, [0.05, 0.6, 0.9, 0.06], np.repeat(flat, 40, axis=0), "inferno", 0, float(flat.max()) or 1,
          "2,048 numbers in a row")
    arrow(fig, 0.5, 0.5 + 1e-3, 0.52)
    ax = fig.add_axes([0.05, 0.18, 0.9, 0.26])
    ax.bar(range(64), h, color=BLUE)
    ax.set_xlim(-1, 64)
    ax.set_title("the 64-number description", fontsize=13, color=INK2, loc="left")
    ax.set_yticks([])
    mv.add(fig, "08_heads", 4.0)

    probs, owner_score = acts["count_probs"], acts["owner"]
    best = int(np.argmax(probs))
    fig = frame("8. Two answers",
                f"Softmax turns 7 scores into probabilities that add to 1. The owner check compares the "
                f"description with {owner}'s average hand for that count.")
    ax = fig.add_axes([0.11, 0.2, 0.38, 0.6])
    names = ["no hand", "0", "1", "2", "3", "4", "5"]
    ax.barh(range(7), probs, color=[BLUE if i == best else LINE for i in range(7)])
    ax.set_yticks(range(7), names)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_title(f"how many fingers?  '{names[best]}' at {probs[best]:.2f}", fontsize=15, loc="left")
    ax2 = fig.add_axes([0.56, 0.45, 0.38, 0.12])
    t = LP.owner_threshold(net.meta, load_settings())     # the threshold the safe actually uses
    ax2.barh([0], [owner_score], color=GREEN if owner_score >= t else ORANGE)
    ax2.axvline(t, color=INK, ls="--")
    ax2.set_xlim(0, 1)
    ax2.set_yticks([])
    ax2.set_title(f"is it {owner}'s hand?  {owner_score:.2f} (threshold {t:.2f})", fontsize=15, loc="left")
    mv.add(fig, "08_heads", 4.5)


def s09_training(mv, snapshots, n_weights):
    if snapshots is None:
        return
    filt, loss = snapshots["filters"], snapshots["train_loss"]
    epochs = sorted(set([0, 1, 2, 3, 5, 8, 12, 18, len(filt) - 1]) & set(range(len(filt))))
    lim = float(np.abs(filt).max())
    for e in epochs:
        fig = frame("9. Training: how the filters got their weights",
                    f"Each pass over the photos, wrong answers give a loss, and backpropagation nudges all "
                    f"{n_weights:,} weights a little downhill, like the V-fit but at scale.")
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


def s10_rules(mv):
    for state, caption, note in [("idle", "Walk up and press the button: the LEDs light up.", "asleep"),
                                 ("locked", "Walk up and press the button: the LEDs light up.", "awake: 0 of 3 digits")]:
        fig = frame("10. The safe's rules", caption)
        led(fig, [0.3, 0.3, 0.4, 0.4], leds.render({"state": state, "entered": 0, "code_len": 3,
                                                    "hold": 0, "need_clear": True}), note)
        mv.add(fig, "10_rules", 1.2)
    times = np.round(np.arange(0, 1.21, 0.1), 2)
    prob = np.clip(0.2 + 3.5 * times, 0, 0.94)            # an illustration, not a recording
    for n, t in enumerate(times):
        held = max(0.0, t - 0.2)
        accepted = held >= LP.HOLD_S
        status = {"state": "locked", "reading": "3" if prob[n] >= LP.CONF else None, "hold": min(1, held / LP.HOLD_S),
                  "entered": 2 if accepted else 1, "code_len": 3, "need_clear": accepted}
        fig = frame("10. The safe's rules",
                    "A digit counts after 0.8 s at 80%+. Then the hand leaves the mat before the next one.")
        ax = fig.add_axes([0.06, 0.2, 0.5, 0.6])
        ax.plot(times[:n + 1], prob[:n + 1], color=BLUE, lw=3)
        ax.axhline(LP.CONF, color=INK2, ls="--")
        ax.text(0.01, LP.CONF + 0.02, "80%", color=INK2)
        ax.set_xlim(0, 1.25)
        ax.set_ylim(0, 1)
        ax.set_xlabel("seconds since the hand arrived")
        ax.set_title("probability of '3' (illustration)", fontsize=14, loc="left")
        led(fig, [0.62, 0.35, 0.33, 0.3], leds.render(status), "the safe's LED matrix")
        fig.text(0.62, 0.25, "digit accepted" if accepted else f"holding... {held:.1f} / {LP.HOLD_S} s",
                 fontsize=18, weight="bold", color=GREEN if accepted else INK)
        mv.add(fig, "10_rules", STEP if not accepted else 1.5)
        if accepted:
            break
    status = {"state": "locked", "reading": None, "hold": 0, "entered": 3, "code_len": 3, "need_clear": True}
    lockout = float(load_settings().get("lockout_s", LP.LOCKOUT_S))
    fig = frame("10. The safe's rules", f"The right 3 digits open it. Three refused codes in a row lock it "
                f"for {lockout:g} s.")
    led(fig, [0.3, 0.3, 0.4, 0.4], leds.render(status), "3 of 3 digits in")
    mv.add(fig, "10_rules", 1.6)
    fig = frame("10. The safe's rules", "Open. (The duress code opens it exactly the same way, "
                "and silently sends an alert with a photo.)")
    led(fig, [0.3, 0.3, 0.4, 0.4], leds.render({"state": "open"}), "open")
    mv.add(fig, "10_rules", 3.0)


def s11_end(mv, owner):
    fig = frame("")
    fig.text(0.5, 0.56, "One network, two answers", ha="center", fontsize=40, weight="bold")
    fig.text(0.5, 0.45, f"how many fingers, and whether it's {owner}'s hand", ha="center", fontsize=20, color=INK2)
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
        lines.append(f"file '{items[-1][0]}'")           # the concat demuxer needs the last file twice
        lst.write_text("\n".join(lines) + "\n")
        subprocess.run([exe, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "18", str(path)], check=True)
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

def pick_photo(owner):
    for label in ("3", "4", "2", "5", "1"):
        files = sorted((DATA_DIR / owner).glob(f"*/{label}/*.png"))
        if files:
            return files[len(files) // 2]
    return None


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
    path = args.photo or pick_photo(args.owner)
    if path is None:
        sys.exit("No photo: pass --photo, or take some with capture.py first.")
    photo = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if photo.shape != (FN.SAVE_SIZE, FN.SAVE_SIZE):
        photo = np.clip(np.rint(FN.shrink(photo, FN.SAVE_SIZE)), 0, 255).astype(np.uint8)
    if args.untrained or not args.model.exists():
        if not args.untrained:
            print(f"No trained model at {args.model}: using random weights.")
        net = FN.FingerNet(weights=FN.random_weights())
    else:
        net = FN.FingerNet(args.model)
    x = FN.net_input(photo)
    _, _, acts = net.forward(x, keep=True)
    w = net.w
    k = int(np.argmax([np.abs(acts["conv1"][i]).mean() for i in range(8)]))     # the busiest filter
    snapshots = dict(np.load(args.snapshots)) if args.snapshots.exists() and not args.untrained else None
    n_weights = int(sum(v.size for name, v in w.items() if name.split("_")[0] in
                        ("conv1", "conv2", "conv3", "fc", "count", "owner")))

    mv = Movie(args.out)
    s01_title(mv, args.owner)
    s02_pixels(mv, photo, FN.shrink(photo, FN.NET_SIZE))
    s03_convolution(mv, x, acts, w, k)
    s04_all_filters(mv, acts, w)
    s05_relu(mv, acts, k)
    s06_pooling(mv, acts, k)
    s07_deeper(mv, acts)
    s08_heads(mv, acts, net, args.owner)
    s09_training(mv, snapshots, n_weights)
    s10_rules(mv)
    s11_end(mv, args.owner)

    scenes = list(dict.fromkeys(s for s, _, _ in mv.items))
    for s in scenes:
        write_video([(p, secs) for sc, p, secs in mv.items if sc == s], args.out / f"scene_{s}.mp4")
    write_video([(p, secs) for _, p, secs in mv.items], args.out / "infallible_safe.mp4")
    total = sum(secs for _, _, secs in mv.items)
    summary = {s: round(sum(secs for sc, _, secs in mv.items if sc == s), 1) for s in scenes}
    print(json.dumps({"photo": str(path), "frames": len(mv.items), "seconds": round(total, 1), "scenes": summary},
                     indent=2))
    print(f"Video: {args.out / 'infallible_safe.mp4'} (+ one per scene). Frames in {mv.frames_dir}")


if __name__ == "__main__":
    main()
