# 9/15 — Grayscale

Image processing exercise: convert an image to grayscale, binarize it (pure black/white via a threshold), then clean it up with erosion/dilation.

- `image_ops.py` — shared conversion functions (`to_grayscale`, `to_binary`, `erode`, `dilate`) used by both the CLI scripts and the web UI.
- `grayscale.py` — CLI: loads an image and converts it to grayscale, saving the result tagged with today's date (`<name>_9-15_grayscale<ext>`).
- `binarize.py` — CLI: loads an image and binarizes it at a given threshold (0-255, default 128), saving the result tagged with today's date and threshold (`<name>_9-15_binarized_<threshold><ext>`).
- `app.py` + `templates/index.html` — a local [Flask](https://flask.palletsprojects.com/) web UI. Drop or pick an image **once**; it stays loaded in memory while you play with sliders for threshold, erosion, and dilation, and the preview re-renders live as you drag (no re-upload needed). Click Download to save the currently-shown result, tagged with today's date and the slider values used (`<name>_9-15_threshold-<t>_erode-<e>_dilate-<d>.png`) — into `output/` (gitignored — generated, not source) and to your browser's downloads.
  - Erosion/dilation treat **white as the foreground**: erosion shrinks white regions, dilation grows them — the standard convention (matches OpenCV's `erode`/`dilate` on a `THRESH_BINARY` image).
  - Large photos are downscaled to a max of 1000px on the longest side on upload, so the live preview stays responsive.

## Run it

From the repo root, with the venv active (see root [README](../README.md)):

```bash
# CLI
python 9-15/grayscale.py path/to/image.jpg
python 9-15/binarize.py path/to/image.jpg 100   # threshold optional, defaults to 128

# Web UI
python 9-15/app.py
# then open http://127.0.0.1:5000, drop in an image, and drag the sliders
```
