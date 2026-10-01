# Arduino Display — 10/1

Looks up the current city and local weather and shows them on the Arduino UNO Q's
13x8 LED matrix: the city name scrolls across, then the temperature, then a
flashing icon for the current condition. No API keys needed. Unlike the rest
of this repo (LEGO Education hardware), this exercise runs as an
[Arduino App Lab](https://docs.arduino.cc/software/app-lab/) app on an
Arduino UNO Q.

- `python/main.py` — all the logic: fetches the city from
  [`ipapi.co`](https://ipapi.co/) (IP geolocation, the board's own internet
  connection) and the current temperature/condition from
  [`open-meteo.com`](https://open-meteo.com/) (both free, no API key), then
  renders a hand-rolled 5x7 bitmap font and small weather icons as
  `numpy` frames pushed to the microcontroller via
  `Bridge.call("draw", ...)`. On a failed fetch it shows a flashing "!" icon
  and retries a minute later instead of crashing.
- `sketch/sketch.ino` — a small generic frame receiver (same pattern as App
  Lab's core "LED Matrix Frame" example): it just keeps redrawing whatever
  frame Python last sent, so all the actual display logic lives in Python.
- `app.yaml` / `sketch/sketch.yaml` — Arduino App Lab app manifest and sketch
  platform config.

## Before running

Both live at the top of `python/main.py`:

```python
TEMPERATURE_UNIT = "F"          # "C" or "F"
REFRESH_INTERVAL_S = 10 * 60    # how often to re-fetch city/weather
RETRY_INTERVAL_S = 60           # retry delay after a failed fetch
```

## Run it

Open this folder as an app in Arduino App Lab (UNO Q or VENTUNO Q) and press
Run — it builds `sketch/sketch.ino` for the microcontroller and starts
`python/main.py` on the Linux side automatically. No `pip install` needed:
only the Python standard library (`urllib`) plus `numpy`, which App Lab's
Python environment already provides.

## Verified

Ran live on an Arduino UNO Q: correctly geolocated to Cambridge, pulled
16°C / cloudy from Open-Meteo, and cycled the matrix (scroll city → scroll
temperature → flash the cloud icon) with no errors.
