"""
What did training do? Four panels from the saved log and table:

  1. % of steps on target (|yaw| < 2 deg) per episode -- should climb
  2. epsilon per episode -- exploring at first, exploiting later
  3. yaw over each step for the first and last few episodes
  4. the Q-table as a heatmap; the dot marks the best action per state

    python plot_training.py          # the robot's training
    python plot_training.py --sim    # the simulator's training
    python plot_training.py --save   # also write training.png / training_sim.png
"""

import argparse
import csv
import json
import os
from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from qlearn import (ACTION_NAMES, LOG_PATH, LOG_SIM_PATH, QTABLE_PATH, QTABLE_SIM_PATH,
                    STATE_NAMES, HERE)

BLUE, RED, GRAY_MID = "#2a78d6", "#e34948", "#f0efec"
INK, MUTED, GRID, EARLY = "#0b0b0b", "#898781", "#e1e0d9", "#c3c2b7"
N_TRACES = 3


def load(log_path, table_path):
    by_ep = defaultdict(list)
    with open(log_path) as f:
        for row in csv.DictReader(f):
            if row["learning"] == "1":
                by_ep[int(row["episode"])].append(row)
    with open(table_path) as f:
        table = json.load(f)
    return dict(sorted(by_ep.items())), table


def style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(EARLY)
    ax.tick_params(colors=MUTED, labelsize=9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", action="store_true")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    log_path, table_path = (LOG_SIM_PATH, QTABLE_SIM_PATH) if args.sim else (LOG_PATH, QTABLE_PATH)
    if not os.path.exists(log_path):
        raise SystemExit(f"No log yet at {log_path} -- run qlearn.py{' --sim' if args.sim else ''} first.")
    episodes, table = load(log_path, table_path)
    eps_ids = list(episodes)

    fig, axs = plt.subplots(2, 2, figsize=(13, 8.5))
    fig.suptitle("Silly Walks Q-learning" + (" (simulator)" if args.sim else ""), x=0.01,
                 ha="left", fontsize=14, color=INK)

    ax = axs[0][0]
    on_target = [100 * sum(float(r["reward"]) > 0 for r in rows) / len(rows) for rows in episodes.values()]
    ax.plot(eps_ids, on_target, color=BLUE, linewidth=2, marker="o", markersize=4)
    ax.set_ylim(0, 100)
    ax.set_xlabel("episode", color=MUTED)
    style(ax, "% of steps on target (|yaw| < 2°)")

    ax = axs[0][1]
    epsilon = [float(rows[0]["epsilon"]) for rows in episodes.values()]
    ax.plot(eps_ids, epsilon, color=BLUE, linewidth=2)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("episode", color=MUTED)
    style(ax, "ε at the start of each episode (chance of a random action)")

    ax = axs[1][0]
    first, last = eps_ids[:N_TRACES], eps_ids[-N_TRACES:]
    for ep in first:
        ys = [0.0] + [float(r["next_yaw"]) for r in episodes[ep]]
        ax.plot(range(len(ys)), ys, color=EARLY, linewidth=2,
                label=f"first {N_TRACES} episodes" if ep == first[0] else None)
    if len(eps_ids) > N_TRACES:
        for ep in last:
            ys = [0.0] + [float(r["next_yaw"]) for r in episodes[ep]]
            ax.plot(range(len(ys)), ys, color=BLUE, linewidth=2,
                    label=f"last {N_TRACES} episodes" if ep == last[0] else None)
    ax.axhspan(-2, 2, color=GRAY_MID, zorder=0)
    ax.axhline(0, color=EARLY, linewidth=1)
    ax.set_xlabel("step", color=MUTED)
    ax.set_ylabel("yaw error (°)  + = drifted right", color=MUTED)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    style(ax, "Heading during an episode (shaded = on target)")

    ax = axs[1][1]
    q = table["q"]
    lim = max(0.01, max(abs(v) for row in q for v in row))
    cmap = LinearSegmentedColormap.from_list("div", [RED, GRAY_MID, BLUE])
    im = ax.imshow(q, cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    for s, row in enumerate(q):
        for a, v in enumerate(row):
            ax.text(a, s, f"{v:.1f}", ha="center", va="center", fontsize=8, color=INK)
        if any(row):
            best = max(range(len(row)), key=lambda a: row[a])
            ax.plot(best + 0.38, s - 0.3, marker="o", markersize=7, color=INK)
    ax.set_xticks(range(len(ACTION_NAMES)), ACTION_NAMES, rotation=20)
    ax.set_yticks(range(len(STATE_NAMES)), [f"s{i}  {n}°" for i, n in enumerate(STATE_NAMES)])
    style(ax, "Q-table (blue = good, red = bad, ● = chosen action)")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8).outline.set_visible(False)

    fig.tight_layout()
    if args.save:
        out = os.path.join(HERE, "training_sim.png" if args.sim else "training.png")
        fig.savefig(out, dpi=130)
        print(f"saved {out}")
    plt.show()


if __name__ == "__main__":
    main()
