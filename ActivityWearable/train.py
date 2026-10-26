#!/usr/bin/env python3
"""Train and evaluate both models, leaving one person out at a time.

Model 1: a decision tree with 4 regions (3 learned thresholds, grown
best-first) on ONE number per window, the peak acceleration along one signed
axis. (A depth-2 tree wasted a threshold: two cuts between walk and run and
none for bike, 74% vs 80% held out.) All six directions
(+x, -x, +y, -y, +z, -z) are tried, and the one with the best held-out
accuracy is kept.
Model 2: all IMU outputs -> the features in features.py -> a decision tree
(readable), plus a random forest and k-nearest neighbours for comparison.

"Held-out" means: train on everyone but one person, test on that person,
repeat for each person. That's the demo situation (a classmate the model has
never seen), so it's the honest score.

Writes figures/ (PNG + results.json) and the final models, trained on
everyone, to unoq/activity-wearable/python/models.json for the board.

    python ActivityWearable/train.py
"""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import confusion_matrix  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.tree import DecisionTreeClassifier, plot_tree  # noqa: E402

HERE = Path(__file__).resolve().parent
BOARD_PY = HERE / "unoq" / "activity-wearable" / "python"
sys.path.insert(0, str(BOARD_PY))
import classify  # noqa: E402
import features as F  # noqa: E402
from common import DATA_DIR, LABELS, SESSION_LOG  # noqa: E402

FIG_DIR = HERE / "figures"
MODELS_JSON = BOARD_PY / "models.json"
TRIM_S = 3.0            # seconds dropped at each end of a session (1 s for the 10 s calibration)

# Reference categorical palette (dataviz skill, slots 1-4 in order), one hue per activity.
COLORS = {"still": "#2a78d6", "walk": "#eb6834", "run": "#1baf7a", "bike": "#eda100"}
CLUSTER_COLORS = ["#e87ba4", "#008300", "#6250d6", "#e34948"]   # slots 5-8: clusters aren't activities
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


# ---- Data -------------------------------------------------------------------
def load():
    rows = [r for r in csv.DictReader(open(SESSION_LOG)) if r["status"] == "kept"]
    wins, people, labels = [], [], []
    for r in rows:
        path = DATA_DIR / f"{r['session']}.csv"
        if not path.exists():
            print("  missing (run pull_data.py?):", path.name)
            continue
        data = np.loadtxt(path, delimiter=",", comments="#", skiprows=3)[:, 1:7]
        trim = 1.0 if float(r["seconds"]) <= 15 else TRIM_S
        for w in F.windows(data, trim):
            wins.append(w)
            people.append(r["person"])
            labels.append(r["label"])
    return wins, np.array(people), np.array(labels)


def leave_one_person_out(make, X, y, people):
    pred = np.empty_like(y)
    per_person = {}
    for p in sorted(set(people)):
        test = people == p
        pred[test] = make().fit(X[~test], y[~test]).predict(X[test])
        per_person[p] = float(np.mean(pred[test] == y[test]))
    return pred, per_person


def model1_make():
    return DecisionTreeClassifier(max_leaf_nodes=4, random_state=0)


MODEL2 = {
    "tree": lambda: DecisionTreeClassifier(max_depth=4, min_samples_leaf=10, random_state=0),
    "forest": lambda: RandomForestClassifier(n_estimators=100, min_samples_leaf=2, random_state=0, n_jobs=-1),
    "knn": lambda: _Knn(k=7),
}


class _Knn:
    """KNN on standardised features (distances need comparable units)."""
    def __init__(self, k):
        self.k = k

    def fit(self, X, y):
        self.scaler = StandardScaler().fit(X)
        self.knn = KNeighborsClassifier(n_neighbors=self.k).fit(self.scaler.transform(X), y)
        self.classes_ = self.knn.classes_
        return self

    def predict(self, X):
        return self.knn.predict(self.scaler.transform(X))


# ---- Export (plain numbers the board can run with classify.py) ----------------
def export_tree(t, classes=None):
    """classes: the class names in the tree's own order (a forest's trees only know indices)."""
    tr = t.tree_
    names = list(t.classes_ if classes is None else classes)
    order = [names.index(c) for c in LABELS]
    val = tr.value[:, 0, :]
    val = val / val.sum(axis=1, keepdims=True)
    return {"feature": tr.feature.tolist(), "threshold": tr.threshold.tolist(),
            "left": tr.children_left.tolist(), "right": tr.children_right.tolist(),
            "value": val[:, order].tolist()}


def export_knn(m):
    return {"k": m.k, "classes": LABELS, "mean": m.scaler.mean_.tolist(), "scale": m.scaler.scale_.tolist(),
            "X": np.round(m.knn._fit_X, 6).tolist(),
            "y": [LABELS.index(c) for c in m.knn.classes_[m.knn._y]]}


def thresholds(tree):
    """The learned cut points of Model 1's tree, smallest first."""
    t = tree.tree_
    return sorted(float(t.threshold[i]) for i in range(t.node_count) if t.children_left[i] != -1)


# ---- Figures ----------------------------------------------------------------
def fig_directions(acc_by_dir, best):
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    names = list(acc_by_dir)
    vals = [acc_by_dir[d] * 100 for d in names]
    ax.barh(names, vals, height=0.6, color=["#2a78d6" if d == best else "#c3c2b7" for d in names])
    for i, v in enumerate(vals):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", color=INK)
    ax.set_xlim(0, 105)
    ax.invert_yaxis()
    ax.set_xlabel("held-out accuracy (%)")
    ax.set_title("Model 1: which direction's peak works best?")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model1_directions.png", dpi=180)
    plt.close(fig)


def fig_peaks(x, y, people, direction, cuts, tree):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    rng = np.random.default_rng(0)
    for i, label in enumerate(LABELS):
        m = y == label
        ax.scatter(x[m], i + rng.uniform(-0.25, 0.25, m.sum()), s=10, color=COLORS[label],
                   alpha=0.55, linewidths=0)
    for k, c in enumerate(cuts):   # labels alternate height so close cuts don't collide
        ax.axvline(c, color=INK, linewidth=1.2, linestyle="--")
        left = k % 2 == 0 and k + 1 < len(cuts) and cuts[k + 1] - c < 1.0   # crowded: label on the left
        ax.text(c, len(LABELS) - 0.45, f"{c:.2f} g " if left else f" {c:.2f} g", color=INK, fontsize=9,
                va="bottom", ha="right" if left else "left")
    # Name each region by what the tree predicts there.
    edges = [x.min() - 0.3] + cuts + [x.max() + 0.3]
    for lo, hi in zip(edges[:-1], edges[1:]):
        pred = tree.predict([[(lo + hi) / 2]])[0]
        ax.text((lo + hi) / 2, -0.85, pred, ha="center", color=INK2, fontsize=8.5)
    ax.set_yticks(range(len(LABELS)), LABELS)
    ax.set_ylim(-1.1, len(LABELS) + 0.2)
    ax.set_xlabel(f"peak acceleration along {direction} in a 2 s window (g)")
    ax.set_title(f"Model 1: three thresholds on the {direction} peak")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model1_peaks.png", dpi=180)
    plt.close(fig)


def fig_confusions(results):
    fig, axes = plt.subplots(1, len(results), figsize=(4.3 * len(results), 4.1))
    for ax, (title, y, pred) in zip(np.atleast_1d(axes), results):
        cm = confusion_matrix(y, pred, labels=LABELS)
        frac = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(frac, cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
            "blue", ["#f4f8fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]), vmin=0, vmax=1)
        for i in range(len(LABELS)):
            for j in range(len(LABELS)):
                ax.text(j, i, f"{frac[i, j] * 100:.0f}%", ha="center", va="center",
                        color="white" if frac[i, j] > 0.55 else INK, fontsize=10)
        ax.set_xticks(range(len(LABELS)), LABELS)
        ax.set_yticks(range(len(LABELS)), LABELS)
        ax.set_xlabel("predicted")
        ax.set_ylabel("actually doing")
        ax.set_title(f"{title}: {np.mean(y == pred) * 100:.0f}%")
        ax.grid(False)
    fig.suptitle("Held-out accuracy (each person tested by a model trained on the others)",
                 x=0.01, ha="left", color=INK2, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "confusion.png", dpi=180)
    plt.close(fig)


def fig_tree(tree):
    fig, ax = plt.subplots(figsize=(11, 6))
    plot_tree(tree, feature_names=F.FEATURE_NAMES, class_names=list(tree.classes_), filled=False,
              impurity=False, proportion=True, rounded=True, precision=2, fontsize=10, ax=ax)
    ax.set_title("Model 2: the decision tree (trained on everyone). Left = yes, right = no")
    ax.text(0, 0, "value = share of " + ", ".join(tree.classes_) + " windows reaching that box",
            transform=ax.transAxes, color=INK2, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model2_tree.png", dpi=150)
    plt.close(fig)


def fig_importance(forest):
    imp = forest.feature_importances_
    top = np.argsort(imp)[::-1][:12]
    fig, ax = plt.subplots(figsize=(6.4, 4))
    ax.barh([F.FEATURE_NAMES[i] for i in top], imp[top] * 100, height=0.6, color="#2a78d6")
    ax.invert_yaxis()
    ax.set_xlabel("share of the forest's decisions (%)")
    ax.set_title("Model 2: which features matter most")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "model2_importance.png", dpi=180)
    plt.close(fig)


def fig_kmeans(X, y):
    Z = StandardScaler().fit_transform(X)
    P = PCA(n_components=2, random_state=0).fit_transform(Z)
    clusters = KMeans(n_clusters=4, n_init=10, random_state=0).fit_predict(Z)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True, sharey=True)
    for label in LABELS:
        m = y == label
        axes[0].scatter(P[m, 0], P[m, 1], s=8, color=COLORS[label], alpha=0.6, linewidths=0, label=label)
    axes[0].legend(frameon=False, markerscale=2)
    axes[0].set_title("What people were doing")
    for c in range(4):
        m = clusters == c
        axes[1].scatter(P[m, 0], P[m, 1], s=8, color=CLUSTER_COLORS[c], alpha=0.6, linewidths=0,
                        label=f"group {c + 1}")
    axes[1].legend(frameon=False, markerscale=2)
    axes[1].set_title("What k-means found on its own (no labels)")
    for ax in axes:
        ax.set_xlabel("principal component 1")
    axes[0].set_ylabel("principal component 2")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "kmeans.png", dpi=180)
    plt.close(fig)
    return {f"group {c + 1}": {label: int(np.sum((clusters == c) & (y == label))) for label in LABELS}
            for c in range(4)}


# ---- Main -------------------------------------------------------------------
def main():
    FIG_DIR.mkdir(exist_ok=True)
    wins, people, y = load()
    print(f"{len(wins)} windows of {F.WINDOW_S:g} s from {len(set(people))} people")
    for p in sorted(set(people)):
        counts = {label: int(np.sum((people == p) & (y == label))) for label in LABELS}
        print(f"  {p:8s} {counts}")

    # Model 1: try every direction.
    peaks = {d: np.array([[F.peak(w, d)] for w in wins]) for d in F.DIRECTIONS}
    m1 = {}
    for d in F.DIRECTIONS:
        pred, per = leave_one_person_out(model1_make, peaks[d], y, people)
        m1[d] = {"pred": pred, "per_person": per, "acc": float(np.mean(pred == y))}
    best = max(m1, key=lambda d: m1[d]["acc"])
    print("\nModel 1 (one peak), held-out accuracy by direction:")
    for d in F.DIRECTIONS:
        print(f"  {d}: {m1[d]['acc'] * 100:5.1f}%" + ("   <- best" if d == best else ""))

    # Model 2: all features.
    X = np.array([F.vector(w) for w in wins])
    m2 = {}
    for name, make in MODEL2.items():
        pred, per = leave_one_person_out(make, X, y, people)
        m2[name] = {"pred": pred, "per_person": per, "acc": float(np.mean(pred == y))}
    default = max(m2, key=lambda k: (round(m2[k]["acc"], 3), k == "tree"))
    print("\nModel 2 (all IMU outputs), held-out accuracy:")
    for name in MODEL2:
        per = "  ".join(f"{p} {a * 100:.0f}%" for p, a in m2[name]["per_person"].items())
        print(f"  {name:6s} {m2[name]['acc'] * 100:5.1f}%   ({per})" + ("   <- live default" if name == default else ""))
    per1 = "  ".join(f"{p} {a * 100:.0f}%" for p, a in m1[best]["per_person"].items())
    print(f"\nModel 1 ({best}) per person: {per1}")

    # Final models, trained on everyone.
    tree1 = model1_make().fit(peaks[best], y)
    cuts = thresholds(tree1)
    final = {name: make().fit(X, y) for name, make in MODEL2.items()}
    print(f"Model 1 thresholds on {best}: " + ", ".join(f"{c:.2f} g" for c in cuts))

    models = {"classes": LABELS, "window_s": F.WINDOW_S, "step_s": F.STEP_S,
              "feature_names": F.FEATURE_NAMES,
              "model1": {"direction": best, "thresholds_g": cuts, "tree": export_tree(tree1)},
              "model2_default": default,
              "model2": {"tree": export_tree(final["tree"]),
                         "forest": {"trees": [export_tree(t, final["forest"].classes_) for t in final["forest"].estimators_]},
                         "knn": export_knn(final["knn"])},
              "trained_on": sorted(set(people)), "windows": len(wins)}
    MODELS_JSON.write_text(json.dumps(models))
    print(f"Wrote {MODELS_JSON.relative_to(HERE)} ({MODELS_JSON.stat().st_size / 1e6:.1f} MB)")

    # Check the board's runner gives the same answers as scikit-learn.
    runner = classify.Models(MODELS_JSON)
    check = {"model1": np.mean([runner.model1(w)[0] == p for w, p in zip(wins, tree1.predict(peaks[best]))])}
    for name in MODEL2:
        sk = final[name].predict(X)
        check[name] = np.mean([runner.model2(w, name)[0] == p for w, p in zip(wins, sk)])
    print("Board runner matches scikit-learn: " + ", ".join(f"{k} {v * 100:.1f}%" for k, v in check.items()))

    # Figures.
    fig_directions({d: m1[d]["acc"] for d in F.DIRECTIONS}, best)
    fig_peaks(peaks[best][:, 0], y, people, best, cuts, tree1)
    fig_confusions([(f"Model 1 ({best} peak)", y, m1[best]["pred"]),
                    (f"Model 2 ({default})", y, m2[default]["pred"])])
    fig_tree(final["tree"])
    fig_importance(final["forest"])
    groups = fig_kmeans(X, y)
    print("\nk-means groups (no labels used) vs. what people were doing:")
    for g, counts in groups.items():
        print(f"  {g}: {counts}")

    results = {"people": sorted(set(people)), "windows": len(wins),
               "model1": {d: {"acc": m1[d]["acc"], "per_person": m1[d]["per_person"]} for d in F.DIRECTIONS},
               "model1_best": best, "model1_thresholds_g": cuts,
               "model2": {k: {"acc": v["acc"], "per_person": v["per_person"]} for k, v in m2.items()},
               "model2_default": default, "kmeans_groups": groups,
               "runner_matches_sklearn": {k: float(v) for k, v in check.items()}}
    (FIG_DIR / "results.json").write_text(json.dumps(results, indent=2))
    print(f"\nFigures in {FIG_DIR.relative_to(HERE)}/")


if __name__ == "__main__":
    main()
