#!/usr/bin/env python3
"""Draw both models as one diagram for the write-up: figures/models_overview.png.

Everything shown is read from the trained models (unoq/.../models.json) and
train.py's held-out scores (figures/results.json), so re-running train.py and
then this script keeps the picture true.

    python ActivityWearable/figure_models.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE / "unoq/activity-wearable/python/models.json").read_text())
RESULTS = json.loads((HERE / "figures/results.json").read_text())
OUT = HERE / "figures/models_overview.png"

COLORS = {"still": "#2a78d6", "walk": "#eb6834", "run": "#1baf7a", "bike": "#eda100"}
INK, INK2, MUTED, LINE, CARD, SURFACE = "#0b0b0b", "#52514e", "#8a8985", "#c9c8c2", "#ffffff", "#f6f5f2"

# Plain-English names for the features the forest's trees start with.
PLAIN = {
    "gyro_x_absmax": ("fastest shin swing", "°/s"), "gyro_mag_mean": ("average rotation speed", "°/s"),
    "gyro_mag_max": ("fastest rotation", "°/s"), "gyro_z_absmax": ("fastest twist (Z axis)", "°/s"),
    "gyro_x_std": ("how much the shin swings", "°/s"), "gyro_y_std": ("rotation spread (Y axis)", "°/s"),
    "acc_mag_std": ("spread of total acceleration", "g"), "acc_mag_max": ("hardest total acceleration", "g"),
    "acc_y_std": ("spread of push up the shin", "g"), "acc_y_mean": ("gravity along the shin (upright?)", "g"),
    "acc_y_min": ("lowest push up the shin", "g"), "acc_y_max": ("hardest push up the shin", "g"),
    "acc_z_mean": ("forward lean of the shin", "g"), "acc_z_min": ("lowest forward acceleration", "g"),
    "acc_jerk": ("how sharp the impacts are", "g/s"), "cadence_share": ("how rhythmic the swing is", ""),
}


def box(ax, x, y, w, h, text, fill=CARD, edge=LINE, color=INK, size=10.5, weight="normal", lw=1.2):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                facecolor=fill, edgecolor=edge, linewidth=lw))
    ax.text(x, y, text, ha="center", va="center", fontsize=size, color=color, weight=weight, linespacing=1.3)


def leaf(ax, x, y, label, w=0.105, h=0.06):
    box(ax, x, y, w, h, label, fill=COLORS[label], edge=COLORS[label], color="white", size=11, weight="bold")


def arrow(ax, x0, y0, x1, y1, label=None, side="left"):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.2, shrinkA=0, shrinkB=0, mutation_scale=11))
    if label:
        ax.text((x0 + x1) / 2 + (-0.012 if side == "left" else 0.012), (y0 + y1) / 2, label,
                ha="right" if side == "left" else "left", va="center", fontsize=9, color=INK2)


def card(ax, x0, x1, title, subtitle, score):
    ax.add_patch(FancyBboxPatch((x0, 0.04), x1 - x0, 0.9, boxstyle="round,pad=0,rounding_size=0.02",
                                facecolor=CARD, edgecolor="#e2e1dc", linewidth=1))
    ax.text(x0 + 0.02, 0.905, title, fontsize=15, weight="bold", color=INK, va="top")
    ax.text(x0 + 0.02, 0.86, subtitle, fontsize=10.5, color=INK2, va="top")
    ax.text(x1 - 0.02, 0.905, f"{score * 100:.0f}%", fontsize=22, weight="bold", color=INK, va="top", ha="right")
    ax.text(x1 - 0.02, 0.855, "right on people it\nnever trained on", fontsize=8.5, color=MUTED, va="top",
            ha="right", linespacing=1.2)


def model1(ax):
    m1 = MODELS["model1"]
    lo, mid, hi = m1["thresholds_g"]
    card(ax, 0.01, 0.40, "Model 1 · decision tree", "one number: the peak push up the shin in the last 2 s",
         RESULTS["model1"][m1["direction"]]["acc"])
    cx = 0.205
    box(ax, cx, 0.74, 0.30, 0.07, "2 s of motion  →  peak acceleration\nalong the shin (+Y), in g",
        fill=SURFACE, edge=SURFACE, size=10)
    arrow(ax, cx, 0.705, cx, 0.655)
    # The learned tree, exactly as trained: run | walk | bike | still.
    box(ax, cx, 0.62, 0.17, 0.065, f"peak ≤ {hi:.2f} g ?")
    arrow(ax, cx - 0.04, 0.5875, 0.135, 0.505, "yes")
    arrow(ax, cx + 0.04, 0.5875, 0.33, 0.505, "no", side="right")
    leaf(ax, 0.33, 0.47, "run")
    box(ax, 0.135, 0.47, 0.17, 0.065, f"peak ≤ {mid:.2f} g ?")
    arrow(ax, 0.095, 0.4375, 0.095, 0.355, "yes")
    arrow(ax, 0.175, 0.4375, 0.25, 0.355, "no", side="right")
    leaf(ax, 0.25, 0.32, "walk")
    box(ax, 0.095, 0.32, 0.12, 0.065, f"peak ≤ {lo:.2f} g ?")
    arrow(ax, 0.075, 0.2875, 0.07, 0.205, "yes")
    arrow(ax, 0.115, 0.2875, 0.155, 0.205, "no", side="right")
    leaf(ax, 0.07, 0.17, "still", w=0.075)
    leaf(ax, 0.155, 0.17, "bike", w=0.075)
    ax.text(0.205, 0.085, "The 3 cutoffs were learned from the recordings, not chosen by hand.\n"
            "Weak spot: air-biking peaks about as hard as standing still.",
            ha="center", va="center", fontsize=9, color=INK2, linespacing=1.4)


def plain(feature, threshold):
    name, unit = PLAIN.get(feature, (feature, ""))
    return f"{name}\n≤ {threshold:.0f} {unit} ?" if abs(threshold) >= 10 else f"{name}\n≤ {threshold:.2f} {unit} ?"


def model2(ax):
    trees = MODELS["model2"]["forest"]["trees"]
    names = MODELS["feature_names"]
    card(ax, 0.42, 0.99, "Model 2 · random forest",
         f"{len(trees)} decision trees vote, using all six IMU outputs", RESULTS["model2"]["forest"]["acc"])
    box(ax, 0.705, 0.74, 0.52, 0.07, "2 s of ax, ay, az, gx, gy, gz  →  31 measurements\n"
        "(shin swing, gravity direction, impacts, step rhythm, …)", fill=SURFACE, edge=SURFACE, size=10)
    xs = [0.51, 0.655, 0.80]
    for i, x in enumerate(xs):
        t = trees[i]
        arrow(ax, 0.705 + (x - 0.705) * 0.35, 0.705, x, 0.655)
        ax.text(x, 0.668, f"tree {i + 1}", ha="center", va="bottom", fontsize=8.5, color=MUTED)
        box(ax, x, 0.615, 0.135, 0.075, plain(names[t["feature"][0]], t["threshold"][0]), size=8.8)
        left, right = t["left"][0], t["right"][0]
        arrow(ax, x - 0.03, 0.5775, x - 0.035, 0.505, "yes")
        arrow(ax, x + 0.03, 0.5775, x + 0.035, 0.505, "no", side="right")
        leaf_label = MODELS["classes"][max(range(4), key=lambda k: t["value"][left][k])]
        leaf(ax, x - 0.035, 0.475, leaf_label, w=0.06, h=0.05)
        box(ax, x + 0.035, 0.475, 0.06, 0.05, "more\nquestions", size=8, color=INK2)
    ax.text(0.925, 0.615, f"… {len(trees) - 3}\nmore trees", ha="center", va="center", fontsize=10, color=INK2)
    # Each tree gives an answer; the forest's answer is the most votes.
    for x in xs:
        arrow(ax, x, 0.44, 0.705 + (x - 0.705) * 0.25, 0.345)
    arrow(ax, 0.905, 0.57, 0.9, 0.345)   # the other trees: straight down, clear of tree 3
    box(ax, 0.705, 0.31, 0.44, 0.065, "vote: each tree answers, the most votes wins", fill=SURFACE, edge=SURFACE,
        size=10.5, weight="bold")
    bars_y, bar_x0, bar_w = 0.215, 0.53, 0.30
    example = {"still": 0.03, "walk": 0.90, "run": 0.03, "bike": 0.04}
    for i, (label, share) in enumerate(example.items()):
        y = bars_y - i * 0.032
        ax.text(bar_x0 - 0.01, y, label, ha="right", va="center", fontsize=9, color=INK2)
        ax.add_patch(FancyBboxPatch((bar_x0, y - 0.009), bar_w, 0.018, boxstyle="round,pad=0,rounding_size=0.009",
                                    facecolor="#ecebe7", edgecolor="none"))
        ax.add_patch(FancyBboxPatch((bar_x0, y - 0.009), max(bar_w * share, 0.012), 0.018,
                                    boxstyle="round,pad=0,rounding_size=0.009", facecolor=COLORS[label],
                                    edgecolor="none"))
        ax.text(bar_x0 + bar_w + 0.01, y, f"{share * 100:.0f}%", va="center", fontsize=9, color=INK)
    leaf(ax, 0.93, 0.168, "walk", w=0.09, h=0.06)
    ax.annotate("", xy=(0.885, 0.168), xytext=(0.865, 0.168),
                arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.2, mutation_scale=11))
    ax.text(0.705, 0.072, "Example vote while walking. Each tree learned its own questions from a random "
            "sample of the recordings;\nthe first ones shown are real, from the trained forest.",
            ha="center", va="center", fontsize=9, color=INK2, linespacing=1.4)


def main():
    fig = plt.figure(figsize=(16, 8.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.01, 0.975, "Two ways to tell standing still, walking, running and air-biking apart",
            fontsize=17, weight="bold", color=INK, va="top")
    model1(ax)
    model2(ax)
    fig.savefig(OUT, facecolor=SURFACE)
    print("wrote", OUT.relative_to(HERE))


if __name__ == "__main__":
    main()
