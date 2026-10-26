"""Run the trained models from models.json without scikit-learn (for the board).

train.py exports each scikit-learn model as plain numbers and checks that
these functions give exactly the same predictions as scikit-learn did.
"""
import json

import numpy as np

from features import peak, vector


def tree_proba(tree, x):
    """Walk one exported decision tree: go left when x[feature] <= threshold."""
    node = 0
    while tree["left"][node] != -1:
        node = tree["left"][node] if x[tree["feature"][node]] <= tree["threshold"][node] else tree["right"][node]
    return np.array(tree["value"][node])


def forest_proba(forest, x):
    return np.mean([tree_proba(t, x) for t in forest["trees"]], axis=0)


def knn_proba(knn, x):
    z = (x - np.array(knn["mean"])) / np.array(knn["scale"])
    d = np.linalg.norm(np.array(knn["X"]) - z, axis=1)
    nearest = np.array(knn["y"])[np.argsort(d)[:knn["k"]]]
    return np.bincount(nearest, minlength=len(knn["classes"])) / knn["k"]


class Models:
    def __init__(self, path):
        with open(path) as f:
            self.m = json.load(f)
        self.classes = self.m["classes"]

    def model1(self, window):
        m1 = self.m["model1"]
        p = tree_proba(m1["tree"], [peak(window, m1["direction"])])
        return self.classes[int(np.argmax(p))], p

    def model2(self, window, kind=None):
        kind = kind or self.m["model2_default"]
        x = vector(window)
        spec = self.m["model2"][kind]
        p = {"tree": tree_proba, "forest": forest_proba, "knn": knn_proba}[kind](spec, x)
        return self.classes[int(np.argmax(p))], p
