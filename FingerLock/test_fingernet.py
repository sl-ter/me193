"""Tests for the board's numpy network and picture preparation
(unoq/finger-lock/python/fingernet.py, photo.py, leds.py). No photos needed:
random weights and random pictures.

    venv/bin/python -m pytest FingerLock -q
"""
import io

import common  # noqa: F401  (puts the board's python folder on the path)
import numpy as np
import torch
from PIL import Image

import fingernet as FN
import leds
import photo
import train


def test_numpy_forward_matches_pytorch_on_random_weights():
    torch.manual_seed(0)
    net = train.Net().eval()
    rng = np.random.default_rng(0)
    imgs = rng.integers(0, 256, (20, FN.SAVE_SIZE, FN.SAVE_SIZE)).astype(np.uint8)
    x = train.inputs(imgs)
    p_t, o_t, d_t = train.predict(net, x)
    mu, sd, scale = train.prototypes(d_t, np.arange(20) % 7)
    weights = {**train.weights_of(net), "proto_mu": mu, "proto_sd": sd, "proto_scale": np.array(scale, np.float32)}
    assert train.check_numpy_matches_torch(net, weights, imgs) < 1e-4
    board = FN.FingerNet(weights=weights, meta={"owner_method": "prototype"})
    p, owner, acts = board.forward(x[0], keep=True)
    assert np.isclose(p.sum(), 1.0) and 0.0 <= owner <= 1.0
    assert acts["conv1"].shape == (8, 64, 64) and acts["conv3_pool"].shape == (32, 8, 8) and acts["fc"].shape == (64,)


def test_prepare_any_frame_size_and_colour_order():
    rng = np.random.default_rng(1)
    frame = rng.integers(0, 256, (480, 640, 3)).astype(np.uint8)
    x = FN.prepare(frame)
    assert x.shape == (1, FN.NET_SIZE, FN.NET_SIZE) and np.isfinite(x).all()
    assert np.allclose(x, FN.prepare(frame[..., ::-1]))           # RGB vs BGR: same input
    assert abs(float(x.mean())) < 1e-4                             # standardised


def test_shrink_is_an_area_average():
    img = np.arange(16, dtype=np.float32).reshape(4, 4)
    assert np.allclose(FN.shrink(img, 2), [[2.5, 4.5], [10.5, 12.5]])
    flat = np.full((480, 480), 77.0, np.float32)
    assert np.allclose(FN.shrink(flat, 128), 77.0)                 # non-integer factor keeps a flat picture flat
    assert FN.shrink(np.zeros((120, 160)), (60, 80)).shape == (60, 80)


def test_saved_crop_is_what_capture_writes():
    frame = np.random.default_rng(2).integers(0, 256, (720, 1280, 3)).astype(np.uint8)
    img = FN.crop_for_saving(frame)
    assert img.shape == (FN.SAVE_SIZE, FN.SAVE_SIZE) and img.dtype == np.uint8
    assert np.allclose(FN.prepare(frame), FN.net_input(img))


def test_png_round_trip():
    img = np.random.default_rng(3).integers(0, 256, (120, 160)).astype(np.uint8)
    back = np.array(Image.open(io.BytesIO(photo.png_bytes(img))))
    assert back.shape == img.shape and (back == img).all()


def test_led_frames_fit_the_matrix():
    status = {"state": "locked", "reading": "4", "hold": 0.5, "entered": 3, "code_len": 4, "need_clear": False}
    for arr in [leds.normal(status), leds.render({"state": "open"}), leds.render(status, "wrong"),
                leds.render(status, "stranger"), leds.render({"state": "lockout", "left_s": 59.0})]:
        assert arr.shape == (leds.ROWS, leds.COLS) and arr.max() <= 7


def test_aim_view_outlines_the_square_and_keeps_the_aspect():
    frame = np.full((480, 640, 3), 200, np.uint8)
    view = photo.aim_view(frame, FN.CROP_FRAC, height=240)
    assert view.shape == (240, 320)
    assert view[120, 10] == 200 and view[120, 160] == 200      # no dimming by default
    assert view[0, 40] == 255 and view[120, 40] == 255         # the square's outline
    dimmed = photo.aim_view(frame, FN.CROP_FRAC, height=240, dim=0.5)
    assert dimmed[120, 10] == 100 and dimmed[120, 160] == 200
