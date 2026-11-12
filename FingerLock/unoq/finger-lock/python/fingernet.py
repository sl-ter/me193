"""The finger-counting network's forward pass in numpy, and the picture
preparation it needs.

Shared like the wearable's steps.py: FingerLock/train.py builds the same
network in PyTorch, trains it and exports the weights to fingernet_model.npz
next to this file. The board's main.py and the laptop's laptop_lock.py run it
here with numpy only (the board has no PyTorch), so both machines compute the
same numbers from the same picture.

A camera frame becomes the net's input like this:
  1. square crop from the middle of the frame (the mat)
  2. grey: the mean of the three colour channels, so RGB vs BGR order doesn't matter
  3. shrunk to 128 x 128 by area averaging, rounded to whole numbers 0-255
     (exactly what capture.py saves, so training sees the same pictures)
  4. shrunk again to 64 x 64 (each output pixel = the mean of a 2 x 2 block)
  5. standardised: minus the picture's own mean, divided by its own spread,
     so a brighter or dimmer room gives the same numbers

The network: one set of layers, two answers.
  64x64x1 -> conv 3x3, 8 filters  -> ReLU -> max pool 2x2 -> 32x32x8
          -> conv 3x3, 16 filters -> ReLU -> max pool 2x2 -> 16x16x16
          -> conv 3x3, 32 filters -> ReLU -> max pool 2x2 -> 8x8x32
          -> flatten (2048) -> fully connected 64 -> ReLU   (the hand's "description", 64 numbers)
          -> count head: 7 scores (no hand, 0, 1, 2, 3, 4, 5 fingers) -> softmax
          -> owner head: 1 score -> sigmoid = how likely the hand is the owner's

Is it the owner's hand? Two ways, and train.py keeps whichever refuses more
strangers it never trained on (meta["owner_method"]):
- "head": the owner head above, trained on the owner's hand vs friends' hands.
  With only a few friends it can learn "not like those friends" instead of
  "like the owner", and let a new person through.
- "prototype": the owner's average description for each count (and how much
  each of the 64 numbers usually varies), kept from training. A new hand
  scores 1 when it matches the owner's average for the count it shows, and
  falls towards 0 the further it is, in any direction, so someone unlike
  the owner in a way no friend was still scores low. Like a face check.
"""
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

COUNT_LABELS = ["none", "0", "1", "2", "3", "4", "5"]   # index 0 = no hand on the mat
NONE = 0
SAVE_SIZE = 128        # capture.py saves 128 x 128 grey crops
NET_SIZE = 64          # the network sees 64 x 64
CROP_FRAC = 1.0        # side of the square crop, as a fraction of the frame's short side
STD_FLOOR = 0.02       # an empty mat is nearly flat; don't blow its noise up into "detail"

LAYERS = ["conv1", "conv2", "conv3"]
MODEL_PATH = Path(__file__).resolve().parent / "fingernet_model.npz"


# ---- Picture preparation ------------------------------------------------------

def square_crop(frame, frac=CROP_FRAC):
    """The centred square, side = frac x the frame's short side."""
    h, w = frame.shape[:2]
    side = max(1, int(round(min(h, w) * frac)))
    top, left = (h - side) // 2, (w - side) // 2
    return frame[top:top + side, left:left + side]


def to_grey(frame):
    """Mean of the colour channels as float32 (0-255). Grey input passes through."""
    frame = np.asarray(frame)
    if frame.ndim == 3:
        return frame[..., :3].astype(np.float32).mean(axis=2)
    return frame.astype(np.float32)


@lru_cache(maxsize=16)
def _area_matrix(n_in, n_out):
    """(n_out, n_in) weights: output pixel i is the average of the input pixels
    under [i, i+1) x (n_in / n_out), counting partly covered pixels by how much
    of them is covered. The same idea as OpenCV's INTER_AREA resize, written out
    in numpy so the board doesn't need OpenCV."""
    scale = n_in / n_out
    m = np.zeros((n_out, n_in), np.float64)
    for i in range(n_out):
        a, b = i * scale, (i + 1) * scale
        for j in range(int(np.floor(a)), min(int(np.ceil(b)), n_in)):
            m[i, j] = max(0.0, min(b, j + 1) - max(a, j))
    return (m / scale).astype(np.float32)


def shrink(img, size):
    """Area-average a 2-D picture down (or up) to size x size, or to (height, width)."""
    img = np.asarray(img, np.float32)
    h, w = (size, size) if np.isscalar(size) else size
    return _area_matrix(img.shape[0], h) @ img @ _area_matrix(img.shape[1], w).T


def crop_for_saving(frame, frac=CROP_FRAC):
    """Camera frame -> the 128 x 128 grey uint8 picture capture.py saves."""
    small = shrink(to_grey(square_crop(frame, frac)), SAVE_SIZE)
    return np.clip(np.rint(small), 0, 255).astype(np.uint8)


def standardise(img):
    """Minus its own mean, divided by its own spread (floored)."""
    x = np.asarray(img, np.float32) / 255.0
    return ((x - x.mean()) / max(float(x.std()), STD_FLOOR)).astype(np.float32)


def net_input(img128):
    """A saved 128 x 128 picture (or a float one from training's augmentation)
    -> the (1, 64, 64) array the network takes."""
    return standardise(shrink(img128, NET_SIZE))[None]


def prepare(frame, frac=CROP_FRAC):
    """Camera frame -> network input, through the same 128 x 128 picture capture.py saves."""
    return net_input(crop_for_saving(frame, frac))


# ---- Layers ---------------------------------------------------------------------

def conv3x3(x, w, b):
    """3 x 3 convolution, padding 1, stride 1, as PyTorch's Conv2d does it (no flip).
    x (C, H, W), w (O, C, 3, 3), b (O,) -> (O, H, W)."""
    xp = np.pad(x, ((0, 0), (1, 1), (1, 1)))
    windows = np.lib.stride_tricks.sliding_window_view(xp, (3, 3), axis=(1, 2))   # (C, H, W, 3, 3)
    return np.tensordot(w, windows, axes=([1, 2, 3], [0, 3, 4])) + b[:, None, None]


def relu(x):
    return np.maximum(x, 0.0)


def maxpool2(x):
    """2 x 2 max pooling, stride 2. (C, H, W) -> (C, H/2, W/2)."""
    c, h, w = x.shape
    return x[:, :h // 2 * 2, :w // 2 * 2].reshape(c, h // 2, 2, w // 2, 2).max(axis=(2, 4))


def softmax(z):
    e = np.exp(z - z.max())
    return e / e.sum()


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def proto_scores(h, cls, mu, sd, scale):
    """How much each hand looks like the owner's (1 = the owner's average hand
    for that count, towards 0 = unlike it). h (N, 64) descriptions, cls (N,)
    count class indices (1-6; 'no hand' scores 0), mu/sd (6, 64) the owner's
    mean and spread per count, scale: the owner's typical squared distance."""
    h, cls = np.atleast_2d(h), np.atleast_1d(cls)
    out = np.zeros(len(h), np.float32)
    hand = cls != NONE
    if hand.any():
        z = (h[hand] - mu[cls[hand] - 1]) / sd[cls[hand] - 1]
        out[hand] = np.exp(-0.5 * np.mean(z * z, axis=1) / scale)
    return out


# ---- The network ------------------------------------------------------------------

class FingerNet:
    """The trained network, loaded from fingernet_model.npz (train.py's export)."""

    def __init__(self, path=MODEL_PATH, weights=None, meta=None):
        if weights is None:
            with np.load(path, allow_pickle=False) as f:
                weights = {k: f[k] for k in f.files if k != "meta"}
                meta = json.loads(str(f["meta"])) if "meta" in f.files else {}
        self.w = {k: np.asarray(v, np.float32) for k, v in weights.items()}
        self.meta = meta or {}
        self.labels = self.meta.get("labels", COUNT_LABELS)
        self.owner_method = self.meta.get("owner_method", "head")
        if self.owner_method == "prototype" and "proto_mu" not in self.w:
            raise ValueError("owner_method is 'prototype' but the model file has no proto_mu/proto_sd")

    def forward(self, x, keep=False):
        """x: (1, 64, 64) from prepare(). Returns (count probabilities (7,),
        owner score, activations). The owner score comes from the head or the
        prototype check (meta["owner_method"]). Activations (only with
        keep=True) are every layer's output by name, for the movie and figures."""
        acts = {"input": x} if keep else None
        for name in LAYERS:
            z = conv3x3(x, self.w[name + "_w"], self.w[name + "_b"])
            r = relu(z)
            x = maxpool2(r)
            if keep:
                acts[name] = z
                acts[name + "_relu"] = r
                acts[name + "_pool"] = x
        h = relu(self.w["fc_w"] @ x.reshape(-1) + self.w["fc_b"])
        count_scores = self.w["count_w"] @ h + self.w["count_b"]
        probs = softmax(count_scores)
        owner_head = float(sigmoid((self.w["owner_w"] @ h + self.w["owner_b"])[0]))
        owner_proto = None
        if "proto_mu" in self.w:
            owner_proto = float(proto_scores(h, int(np.argmax(probs)), self.w["proto_mu"],
                                             self.w["proto_sd"], float(self.w["proto_scale"]))[0])
        owner = owner_proto if self.owner_method == "prototype" else owner_head
        if keep:
            acts.update(fc=h, count_scores=count_scores, count_probs=probs,
                        owner_head=owner_head, owner_proto=owner_proto, owner=owner)
        return probs, owner, acts

    def __call__(self, frame, frac=CROP_FRAC):
        """Camera frame -> (count probabilities, owner probability)."""
        probs, owner_p, _ = self.forward(prepare(frame, frac))
        return probs, owner_p


def random_weights(seed=0):
    """Untrained weights with the right shapes (for timing on the board before
    any training, and for the tests). Same scale as PyTorch's default init."""
    rng = np.random.default_rng(seed)
    shapes = {"conv1": (8, 1, 3, 3), "conv2": (16, 8, 3, 3), "conv3": (32, 16, 3, 3),
              "fc": (64, 32 * 8 * 8), "count": (7, 64), "owner": (1, 64)}
    w = {}
    for name, shape in shapes.items():
        fan_in = int(np.prod(shape[1:]))
        bound = 1.0 / np.sqrt(fan_in)
        w[name + "_w"] = rng.uniform(-bound, bound, shape).astype(np.float32)
        w[name + "_b"] = rng.uniform(-bound, bound, shape[0]).astype(np.float32)
    return w
