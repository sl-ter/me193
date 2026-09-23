# Image Math Explorer — 9/15

Image processing exercise: convert an image to grayscale/binary, then explore binary morphology ("image math") interactively.

- `image_ops.py` — shared image operations:
  - `to_grayscale`, `to_binary` (PIL-based) — used by the CLI scripts.
  - `to_binary_array`, `array_to_image`, `erode`, `dilate`, `opening`, `closing`, `boundary`, `skeletonize`, `prune`, `hit_or_miss` (NumPy/[SciPy](https://scipy.org/)/[scikit-image](https://scikit-image.org/)-based) — used by the web UI.
- `grayscale.py` — CLI: loads an image and converts it to grayscale, saving the result tagged with today's date (`<name>_9-15_grayscale<ext>`).
- `binarize.py` — CLI: loads an image and binarizes it at a given threshold (0-255, default 128), saving the result tagged with today's date and threshold (`<name>_9-15_binarized_<threshold><ext>`).
- `app.py` + `templates/index.html` — a local [Flask](https://flask.palletsprojects.com/) web UI, "Image Math Explorer": drop or pick an image **once**; it stays loaded in memory while you play with a **Threshold** slider and pick from a menu of binary morphology operations, each with a live description and its own control. The preview re-renders live as you drag (no re-upload needed), and nothing is written to disk until you explicitly click **Download** — which streams the currently-shown result straight to your browser's downloads, tagged with today's date and the settings used (`<name>_9-15_<operation>_threshold-<t>_amount-<a>.png`). Nothing is auto-saved into the repo.

  Operations available (all treat **white as the foreground**, matching OpenCV's convention on a `THRESH_BINARY` image):
  - **Erosion** — shrinks foreground regions; removes small bright noise; breaks thin connections.
  - **Dilation** — grows foreground regions; fills small gaps/holes; connects nearby components.
  - **Opening** (erode → dilate) — removes small objects/specks while preserving larger shapes.
  - **Closing** (dilate → erode) — fills small holes and gaps; smooths boundaries.
  - **Boundary/edge extraction** — `boundary = A − erosion(A)`.
  - **Skeletonization / thinning** — reduces shapes to 1-pixel-wide centerlines (keeps topology), via [`skimage.morphology.skeletonize`](https://scikit-image.org/docs/stable/api/skimage.morphology.html#skimage.morphology.skeletonize).
  - **Pruning** — skeletonizes, then iteratively removes skeleton endpoints for N iterations, trimming spurs shorter than N pixels. Note: this also shortens legitimate line endpoints by the same amount, not just spurs — a known property of this classic technique.
  - **Hit-or-miss** — detects a specific binary pattern using two structuring elements (`scipy.ndimage.binary_hit_or_miss`); pick a pattern (isolated pixel, or one of four corner orientations) from the dropdown that appears.

  Large photos are downscaled to a max of 1000px on the longest side on upload, so the live preview stays responsive.

## Run it

From the repo root, with the venv active (see root [README](../README.md)):

```bash
# CLI
python ImageMathExplorer/grayscale.py path/to/image.jpg
python ImageMathExplorer/binarize.py path/to/image.jpg 100   # threshold optional, defaults to 128

# Web UI
python ImageMathExplorer/app.py
# then open http://127.0.0.1:5000, drop in an image, pick an operation, and drag the sliders
```
