# SPDX-FileCopyrightText: Copyright (C) Arduino s.r.l. and/or its affiliated companies
#
# SPDX-License-Identifier: MPL-2.0

"""
Arduino Display
================
Looks up the board's current city (via IP geolocation) and local weather
(via Open-Meteo), then shows it on the 13x8 LED matrix: the city name
scrolls across, then the temperature, then a flashing weather icon. Both
APIs are free and require no API key. On any network/API failure it shows
an error icon and retries a minute later instead of crashing.
"""

import concurrent.futures
import json
import logging
import time
import unicodedata
import urllib.request
from urllib.error import URLError, HTTPError

import numpy as np

from arduino.app_utils import App, Bridge, Frame, Logger

logger = Logger("ArduinoDisplay", level=logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEMPERATURE_UNIT = "F"  # "C" or "F"
REFRESH_INTERVAL_S = 10 * 60  # re-fetch location/weather every 10 minutes
RETRY_INTERVAL_S = 60  # on failure, retry after 1 minute
SCROLL_DELAY_S = 0.07  # time between scroll steps
ICON_DURATION_S = 3.0  # how long a static icon is shown
HTTP_TIMEOUT_S = 6

MATRIX_ROWS = 8
MATRIX_COLS = 13

# ---------------------------------------------------------------------------
# 5x7 bitmap font (rows top->bottom, 7 rows tall, 5 cols wide per glyph).
# Only the characters we actually need: A-Z, 0-9, space, "!", "-", "°".
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
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
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
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "°": ["01100", "10010", "10010", "01100", "00000", "00000", "00000"],
}

GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
BRIGHTNESS = 7


def sanitize_text(text: str) -> str:
    """Strip accents/unsupported characters so every char has a glyph."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return "".join(ch if ch.upper() in FONT or ch == "." else " " for ch in ascii_only.upper()).replace(".", "")


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
# Weather icons (8 rows x 13 cols, '1' = lit pixel). Some categories blink
# between two frames to read as "moving" (rain drops, snow flakes).
# ---------------------------------------------------------------------------

def _rows_to_array(rows):
    return np.array([[BRIGHTNESS if c == "1" else 0 for c in row] for row in rows], dtype=np.uint8)


_CLOUD_TOP = [
    "0000000000000",
    "0000000000000",
    "0001111000000",
    "0011111110000",
    "0111111111000",
    "1111111111110",
]

ICONS = {
    "sunny": [
        _rows_to_array([
            "0001000100000",
            "0000000000000",
            "0011111100000",
            "0110000110000",
            "1100000011000",
            "0110000110000",
            "0011111100000",
            "0001000100000",
        ])
    ],
    "cloudy": [
        _rows_to_array(_CLOUD_TOP + ["0000000000000", "0000000000000"])
    ],
    "foggy": [
        _rows_to_array([
            "0000000000000",
            "1111111111110",
            "0000000000000",
            "0111111111100",
            "0000000000000",
            "1111111111110",
            "0000000000000",
            "0111111111100",
        ])
    ],
    "rainy": [
        _rows_to_array(_CLOUD_TOP + ["0010010010000", "0100100100000"]),
        _rows_to_array(_CLOUD_TOP + ["0000000000000", "0000000000000"]),
    ],
    "snowy": [
        _rows_to_array(_CLOUD_TOP + ["0010010010000", "0000000000000"]),
        _rows_to_array(_CLOUD_TOP + ["0000000000000", "0010010010000"]),
    ],
    "thunderstorm": [
        _rows_to_array([
            "0000000000000",
            "0001111000000",
            "0011111110000",
            "0111111111000",
            "1111111111110",
            "0000011000000",
            "0000110000000",
            "0001100000000",
        ]),
        _rows_to_array(_CLOUD_TOP + ["0000000000000", "0000000000000"]),
    ],
    "error": [
        _rows_to_array([
            "0000011000000",
            "0000011000000",
            "0000011000000",
            "0000011000000",
            "0000011000000",
            "0000000000000",
            "0000011000000",
            "0000000000000",
        ]),
        _rows_to_array([
            "0000000000000",
            "0000000000000",
            "0000000000000",
            "0000000000000",
            "0000000000000",
            "0000000000000",
            "0000000000000",
            "0000000000000",
        ]),
    ],
}

BLINK_PERIOD_S = {
    "rainy": 0.2,
    "snowy": 0.6,
    "thunderstorm": 0.4,
    "error": 0.4,
}

# Open-Meteo WMO weather codes -> simplified category.
# https://open-meteo.com/en/docs (WMO Weather interpretation codes)
WMO_CATEGORY = {
    0: "sunny", 1: "sunny",
    2: "cloudy", 3: "cloudy",
    45: "foggy", 48: "foggy",
    51: "rainy", 53: "rainy", 55: "rainy", 56: "rainy", 57: "rainy",
    61: "rainy", 63: "rainy", 65: "rainy", 66: "rainy", 67: "rainy",
    80: "rainy", 81: "rainy", 82: "rainy",
    71: "snowy", 73: "snowy", 75: "snowy", 77: "snowy", 85: "snowy", 86: "snowy",
    95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm",
}


# ---------------------------------------------------------------------------
# Data fetching (stdlib only: no extra pip dependencies required)
# ---------------------------------------------------------------------------

def _http_get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "arduino-display/1.0"})
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_location() -> dict:
    """City + coordinates from the board's own internet connection (no API key)."""
    data = _http_get_json("https://ipapi.co/json/")
    if data.get("error"):
        raise RuntimeError(f"ipapi.co error: {data.get('reason', 'unknown')}")
    return {
        "city": data.get("city") or "Unknown",
        "latitude": data["latitude"],
        "longitude": data["longitude"],
    }


def fetch_weather(latitude: float, longitude: float) -> dict:
    """Current temperature + condition from Open-Meteo (no API key)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}&current_weather=true"
    )
    data = _http_get_json(url)
    current = data["current_weather"]
    temp_c = float(current["temperature"])
    code = int(current["weathercode"])
    category = WMO_CATEGORY.get(code, "cloudy")
    return {"temp_c": temp_c, "category": category}


def fetch_city_and_weather() -> dict:
    location = fetch_location()
    weather = fetch_weather(location["latitude"], location["longitude"])
    return {"city": location["city"], "temp_c": weather["temp_c"], "category": weather["category"]}


def format_temperature(temp_c: float) -> str:
    if TEMPERATURE_UNIT == "F":
        value = round(temp_c * 9 / 5 + 32)
        return f"{value}F"
    return f"{round(temp_c)}C"


# ---------------------------------------------------------------------------
# Display primitives
# ---------------------------------------------------------------------------

def draw_frame(arr: np.ndarray):
    Bridge.call("draw", Frame(arr).to_board_bytes())


def scroll_text(text: str):
    text = sanitize_text(text).strip() or " "
    columns = text_to_columns(text)
    # start fully off-screen right, end fully off-screen left
    for offset in range(-MATRIX_COLS, len(columns)):
        draw_frame(render_window(columns, offset))
        time.sleep(SCROLL_DELAY_S)


def show_icon(category: str, duration: float = ICON_DURATION_S):
    frames = ICONS.get(category, ICONS["cloudy"])
    period = BLINK_PERIOD_S.get(category)
    if period is None or len(frames) == 1:
        draw_frame(frames[0])
        time.sleep(duration)
        return
    elapsed = 0.0
    index = 0
    while elapsed < duration:
        draw_frame(frames[index % len(frames)])
        time.sleep(period)
        elapsed += period
        index += 1


# ---------------------------------------------------------------------------
# Main loop: fetch periodically, always cycle the display, fail gracefully
# ---------------------------------------------------------------------------

_state = {"data": None, "next_fetch": 0.0, "future": None}
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="fetch")


def refresh_if_due():
    """Kick off/collect fetches on a worker thread so the display loop never
    blocks: HTTP_TIMEOUT_S only bounds the socket read, not DNS resolution,
    which can hang far longer than that at the OS level with no network."""
    now = time.time()
    future = _state["future"]

    if future is None:
        if now < _state["next_fetch"]:
            return
        _state["future"] = _executor.submit(fetch_city_and_weather)
        return

    if not future.done():
        return  # still waiting on the network; keep cycling the display

    _state["future"] = None
    try:
        data = future.result()
        logger.info(
            f"Updated: {data['city']}, {format_temperature(data['temp_c'])}, {data['category']}"
        )
        _state["data"] = data
        _state["next_fetch"] = now + REFRESH_INTERVAL_S
    except (URLError, HTTPError, KeyError, ValueError, RuntimeError) as exc:
        logger.warning(f"Fetch failed ({exc}); will retry in {RETRY_INTERVAL_S}s")
        _state["data"] = None
        _state["next_fetch"] = now + RETRY_INTERVAL_S


def display_cycle():
    data = _state["data"]
    if data is None:
        show_icon("error", duration=ICON_DURATION_S)
        return
    scroll_text(data["city"])
    scroll_text(format_temperature(data["temp_c"]))
    show_icon(data["category"])


def loop():
    refresh_if_due()
    display_cycle()


App.run(user_loop=loop)
