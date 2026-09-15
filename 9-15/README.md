# 9/15 — Grayscale

Image processing exercise: convert an image to grayscale, then binarize it (pure black/white via a threshold).

- `image_ops.py` — shared conversion functions (`to_grayscale`, `to_binary`) used by both the CLI scripts and the web UI.
- `grayscale.py` — CLI: loads an image and converts it to grayscale, saving the result tagged with today's date (`<name>_9-15_grayscale<ext>`).
- `binarize.py` — CLI: loads an image and binarizes it at a given threshold (0-255, default 128), saving the result tagged with today's date and threshold (`<name>_9-15_binarized_<threshold><ext>`).
- `app.py` + `templates/index.html` — a local [Flask](https://flask.palletsprojects.com/) web UI: upload an image, pick grayscale or binarize (with a threshold slider), preview the result in the browser, and download it. Saved copies land in `output/` (gitignored — generated, not source).

## Run it

From the repo root, with the venv active (see root [README](../README.md)):

```bash
# CLI
python 9-15/grayscale.py path/to/image.jpg
python 9-15/binarize.py path/to/image.jpg 100   # threshold optional, defaults to 128

# Web UI
python 9-15/app.py
# then open http://127.0.0.1:5000
```
