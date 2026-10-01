# SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
#
# SPDX-License-Identifier: MPL-2.0

"""
Board Status
============
Shows the board's real IP address and live system metrics (CPU, memory,
disk, uptime) on the 13x8 LED matrix, cycling through each one.

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
import psutil

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
# Only the characters we actually need: A-Z, 0-9, space, ".", "%", ":".
# ---------------------------------------------------------------------------

FONT = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
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
    "%": ["10001", "10010", "00010", "00100", "01000", "01001", "10001"],
    ":": ["00000", "00100", "00000", "00000", "00000", "00100", "00000"],
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


def format_uptime(seconds: float) -> str:
    days, seconds = divmod(int(seconds), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    if days:
        return f"{days}D {hours}H"
    if hours:
        return f"{hours}H {minutes}M"
    return f"{minutes}M"


def collect_metrics() -> dict:
    return {
        "ip": read_ip(),
        "cpu": psutil.cpu_percent(interval=0.5),
        "mem": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent,
        "uptime": format_uptime(time.time() - psutil.boot_time()),
    }


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


def display_cycle(metrics: dict):
    scroll_text(f"IP {metrics['ip']}")
    scroll_text(f"CPU {metrics['cpu']:.0f}%")
    scroll_text(f"MEM {metrics['mem']:.0f}%")
    scroll_text(f"DISK {metrics['disk']:.0f}%")
    scroll_text(f"UP {metrics['uptime']}")


def loop():
    metrics = collect_metrics()
    display_cycle(metrics)


App.run(user_loop=loop)
