# SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
#
# SPDX-License-Identifier: MPL-2.0

"""
Board Status
============
Scrolls the board's real IP address on the 13x8 LED matrix, on loop,
nothing else — CPU/memory/disk/uptime live in the SSH-login dashboard
(board_dashboard.py) instead.

The app's own container runs in an isolated network namespace, so it can't
see the board's real wifi IP directly (only a Docker-internal one). Instead
a host-level cron job writes the real IP into IP_FILE (which sits in this
app's folder, bind-mounted straight into the container as /app) and this
script just reads it back out.
"""

import pathlib
import time
import unicodedata

import numpy as np

from arduino.app_utils import App, Bridge, Frame

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCROLL_DELAY_S = 0.07  # time between scroll steps

IP_FILE = pathlib.Path(__file__).resolve().parent.parent / "ip_address.txt"

MATRIX_ROWS = 8
MATRIX_COLS = 13

# ---------------------------------------------------------------------------
# 5x7 bitmap font (rows top->bottom, 7 rows tall, 5 cols wide per glyph).
# An IPv4 address only ever needs digits, ".", and space.
# ---------------------------------------------------------------------------

FONT = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "00000", "00100"],
}

GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
BRIGHTNESS = 7


def sanitize_text(text: str) -> str:
    """Strip accents/unsupported characters so every char has a glyph."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(ch if ch.upper() in FONT else " " for ch in ascii_only.upper())


def text_to_columns(text: str):
    """Turn a string into a list of 7-bit columns (one strip per pixel-column)."""
    columns = []
    for ch in text:
        glyph = FONT.get(ch, FONT[" "])
        for col in range(GLYPH_WIDTH):
            columns.append([1 if glyph[row][col] == "1" else 0 for row in range(GLYPH_HEIGHT)])
        columns.append([0] * GLYPH_HEIGHT)  # 1px spacing between characters
    return columns


def render_window(columns, offset: int) -> np.ndarray:
    """Render a MATRIX_ROWS x MATRIX_COLS frame starting at column `offset`."""
    arr = np.zeros((MATRIX_ROWS, MATRIX_COLS), dtype=np.uint8)
    for x in range(MATRIX_COLS):
        idx = offset + x
        if 0 <= idx < len(columns):
            col = columns[idx]
            for y in range(GLYPH_HEIGHT):
                if col[y]:
                    arr[y, x] = BRIGHTNESS
    return arr


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def read_ip() -> str:
    try:
        ip = IP_FILE.read_text().strip()
        return ip or "NO IP"
    except FileNotFoundError:
        return "NO IP FILE"


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def draw_frame(arr: np.ndarray):
    Bridge.call("draw", Frame(arr).to_board_bytes())


def scroll_text(text: str):
    text = sanitize_text(text).strip() or " "
    columns = text_to_columns(text)
    for offset in range(-MATRIX_COLS, len(columns)):
        draw_frame(render_window(columns, offset))
        time.sleep(SCROLL_DELAY_S)


def loop():
    scroll_text(read_ip())


App.run(user_loop=loop)
