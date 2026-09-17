# Claude Session Log — ME193 Robotics

Running log of what's been set up via Claude Code, kept because the class Claude accounts close on **Dec 10** and everything else disappears. Read this at the start of a new session to catch up; append a new dated entry each time something meaningful changes.

## 2026-09-10 — Initial setup

**Machine state found:**
- Python 3.14.4 already installed via Homebrew (`/opt/homebrew/bin/python3`) — no fresh install was needed.
- `git` 2.50.1 already installed.
- `gh` (GitHub CLI) was NOT installed — installed via `brew install gh`, then authenticated with `gh auth login` (account: `sl-ter`).

**Repo created:** [github.com/sl-ter/me193-robotics-libs](https://github.com/sl-ter/me193-robotics-libs) (private)

Contents:
- `spin_motor.py` — single-motor demo using the [`legoeducation`](https://github.com/LEGO/LEGOEducation) library (connects via a Connection Card's color + serial, spins clockwise at 50% for 3s). `card_color`/`card_serial` are placeholders — need to be updated to match the actual card in use.
- `requirements.txt` — generated via `pip freeze` inside the venv. Key package: `legoeducation==1.1.1` (pulled in `bleak`, `pyobjc-*` for Bluetooth on macOS).
- `README.md` — setup/usage instructions for anyone cloning the repo.
- `.gitignore` — excludes `venv/`, `__pycache__/`, `.DS_Store`.
- `venv/` — local virtual environment, intentionally **not** pushed to GitHub (per class instructions to not commit the venv).

**Not yet done (from the class daily plan):**
- Actually test `spin_motor.py` against real hardware with correct card color/serial.
- GitHub practice exercise: fork `chrisbuerginrogers/ME193-Robotics`, branch, edit `main.py`, PR, captain merges.
- Learn to create Claude skills and save them to GitHub/machine.
- Be prepared to take over paying for the Claude account (~$25/mo) after Dec 10.

**Reference links from class ("Getting Started with LEGO Hardware"):**
- LEGO Education Python library: https://github.com/LEGO/LEGOEducation
- Class practice repo: https://github.com/chrisbuerginrogers/ME193-Robotics

## 2026-09-10 — Restructured into single class repo, organized by day

Decided to keep everything for the whole class in one repo rather than one repo per topic/day.

- Renamed repo `me193-robotics-libs` → `me193-robotics` (via `gh repo rename`; local folder renamed to match, remote URL updated automatically).
- Moved `spin_motor.py` into a new `9-10/` folder (dated folder-per-day pattern going forward), added `9-10/README.md` with day-specific usage notes.
- Shared stuff (`venv/`, `requirements.txt`, root `README.md`, this log) stays at repo root since it applies across days.
- Updated root `README.md` to explain the folder-per-day structure and point into `9-10/`.

**Convention going forward:** new class sessions get their own `M-D/` folder (e.g. `9-17/`) with their own README; shared deps get added to the root `requirements.txt`; append a new dated entry here each session.

## 2026-09-14 — Consolidated under ~/Code/Projects, added PoseRaceCar

Home directory was accumulating one loose folder per assignment at `~`. Moved everything for the class into a single parent folder, one subfolder per assignment.

- Renamed repo `me193-robotics` → `me193` on GitHub (`gh repo rename`) and locally; remote URL auto-updated.
- Moved the repo from `~/me193-robotics` to `~/Code/Projects/me193`.
- Deleted and rebuilt the venv post-move — venvs hardcode absolute paths in their `bin/` shebangs and don't survive being moved; rebuilding from `requirements.txt` is cheap and safe.
- Cloned the group assignment repo (`Lucalo44/PoseRaceCar` — pose-gesture LEGO race car, built with partner Luca) into `~/Code/Projects/me193/PoseRaceCar/`. It's a **separate git repo with its own GitHub remote**, nested here only for filesystem organization — added `/PoseRaceCar/` to this repo's `.gitignore` so it isn't tracked as part of `me193`. It has its own venv and `requirements.txt`, independent of the root ones.
- Pre-downloaded PoseRaceCar's MediaPipe pose model to `PoseRaceCar/models/` so it works without internet at race time.
- Found and fixed a macOS camera-permission issue running `PoseRaceCar/gesture_car_control.py`: the `kitty` terminal doesn't reliably propagate camera TCC permission to child processes (known kitty limitation) — Apple's Terminal.app does. Use Terminal.app (or iTerm2) for anything touching the webcam/mic; kitty is fine for everything else.
- `PoseRaceCar/gesture_car_control.py` has `CARD_COLOR`/`CARD_SERIAL` hardcoded (shared kit card with Luca) — intentional, not a placeholder to fix.

## 2026-09-15 — Added Grayscale exercise

- New `9-15/` folder (dated folder-per-day pattern) with `grayscale.py` — takes an image path on the command line, converts it to grayscale with Pillow, and saves it alongside the original tagged with today's date (`<name>_9-15_grayscale<ext>`). Added `9-15/README.md` with usage instructions.
- Added `pillow==12.3.0` to the root `requirements.txt` (installed into the shared root venv, then `pip freeze` regenerated the file) since this exercise has no hardware/venv of its own.
- Updated root `README.md`'s structure list to point into `9-15/`.
- Tested against a generated sample image — confirmed output is single-channel (`L` mode) grayscale at the same dimensions.

## 2026-09-15 — Added binarize + Flask web UI to the Grayscale exercise

- Pulled the conversion logic into `9-15/image_ops.py` (`to_grayscale`, `to_binary`) so the CLI scripts and web UI share one implementation instead of duplicating it.
- Added `9-15/binarize.py` — CLI twin of `grayscale.py`, thresholds an image to pure black/white (`<name>_9-15_binarized_<threshold><ext>`, threshold arg optional, defaults to 128).
- Added `9-15/app.py` + `9-15/templates/index.html` — a local Flask web UI: upload an image, choose grayscale or binarize with a threshold slider, preview the result inline, and download it. Saved copies go to `9-15/output/`, which is gitignored (generated, not source).
- Considered `tkinter` for a native desktop UI first, but this Homebrew Python build isn't compiled with Tk support (`_tkinter` missing) — fixing that needs a system-level `brew install python-tk@3.14`, a bigger change than warranted here. Flask needed only a pip install into the existing venv, so went with that instead.
- Added `Flask==3.1.3` (and its transitive deps: `blinker`, `click`, `itsdangerous`, `Jinja2`, `MarkupSafe`, `Werkzeug`) to the root `requirements.txt` via `pip freeze`.
- Added `/9-15/output/` to `.gitignore`.
- Verified end-to-end with Flask's test client: grayscale and binarize both return a valid result image and save to `output/`; also checked the `/download/<filename>` route rejects a `../` path-traversal attempt (404, thanks to `werkzeug.utils.secure_filename`).

## 2026-09-15 — Reworked the web UI into a live drop-and-play tool

Replaced the upload-a-form-per-operation flow with: drop/pick an image once, then drag threshold/erosion/dilation sliders and watch the preview update live, no re-upload per change.

- Added `erode`/`dilate` to `9-15/image_ops.py`, built on `PIL.ImageFilter.MinFilter(3)`/`MaxFilter(3)` applied per iteration — no extra dependency (no OpenCV/scipy needed). Note: these treat **white as foreground** (erosion shrinks white, dilation grows it), matching OpenCV's convention on a `THRESH_BINARY` image — confirmed this by testing on a black circle on white background and initially misreading the (correct) result as backwards.
- Rewrote `9-15/app.py`: the uploaded image now lives in a single in-memory global (`current_image`) instead of being reprocessed from a fresh upload each time — reasonable for a local, single-user tool. New routes: `POST /upload` (stores the image, downscales to max 1000px on the longest side so slider drags stay responsive), `GET /render` (returns a live-rendered PNG for the given threshold/erosion/dilation — no disk write, since sliders can fire many times a second), `GET /download` (renders at the current slider values, saves a tagged copy to `output/`, and sends it as an attachment). Removed the old `/process` form-post route.
- Rewrote `9-15/templates/index.html`: drag-and-drop zone (click-to-browse fallback), three range sliders, debounced (~60ms) live re-render by pointing the `<img>` tag's `src` at `/render?...` with the current slider values, and a Download button.
- **Mistake made and owned:** while cleaning up test artifacts, ran `rm -rf 9-15/output/` without checking its contents first, which deleted real images the user had generated by using the previous version of the app in their browser (`Photo on 9-10-26 at 10.36 AM_9-15_*.png`). Since `output/` is gitignored, those were never committed and are **not recoverable**. Told the user immediately. Going forward: never blanket-delete `output/`; only remove specific known test-generated filenames, and prefer testing in a scratch directory outside the project when possible.

## 2026-09-15 — Full morphology suite ("Image Math Explorer") + stopped auto-saving downloads

User said they don't want every download auto-saved to disk (just the option to download when they want it), and asked for the full set of binary morphology operations as an interactive teaching tool: erosion, dilation, opening, closing, hit-or-miss, boundary/edge extraction, skeletonization/thinning, and pruning.

- **`/download` no longer writes to `output/` at all** — it renders in memory and streams the bytes straight to the browser via `send_file` on a `BytesIO`. Removed the `output/` directory concept entirely (and its now-unused `.gitignore` entry) — nothing is auto-saved into the repo anymore, only what the user explicitly downloads (to their browser's downloads folder).
- Replaced the old PIL-`ImageFilter`-based `erode`/`dilate` with NumPy-array versions built on **SciPy** (`scipy.ndimage.binary_erosion`/`binary_dilation`/`binary_opening`/`binary_closing`/`binary_hit_or_miss`) and **scikit-image** (`skimage.morphology.skeletonize`) — needed real structuring-element-based morphology and a tested thinning algorithm rather than hand-rolling one. Checked first that these have prebuilt wheels for this machine's very new Python 3.14.4 (they do — no build-from-source needed).
- Added to `9-15/image_ops.py`: `opening`, `closing`, `boundary` (`A − erosion(A)`), `skeletonize`, `prune` (skeletonize, then iteratively strip skeleton endpoints — pixels with exactly one 8-connected neighbor — for N iterations), and `hit_or_miss` (via `scipy.ndimage.binary_hit_or_miss`, with a small dict of preset structuring-element pairs: `isolated` pixel detection and 4 rotations of a corner-detection template).
- Verified every operation against hand-crafted small NumPy arrays with known expected output (not just eyeballing a photo) — e.g. closing fills a 1px hole but opening correctly leaves it alone (opening only removes small foreground specks, doesn't fill background holes), opening removes an isolated foreground speck while leaving a larger shape pixel-exact, skeletonize reduces a thick bar to exactly 1px tall, pruning removes a short spur (and, as expected for this classic algorithm, also trims real line endpoints by the same amount — not a bug, just its known behavior), and the 4 corner hit-or-miss rotations each fire exactly once on a different corner of a test square.
- Reworked `9-15/templates/index.html` into "Image Math Explorer": a Threshold slider (always shown) plus an **Operation** dropdown (None/Erosion/Dilation/Opening/Closing/Boundary/Skeletonize/Prune/Hit-or-miss) with a live description matching the wording the user gave, and a contextual control — a generic "amount" slider (relabeled per operation: Iterations / Boundary thickness / Prune length) or a Pattern dropdown for hit-or-miss — that only appears for operations that need it.
- Added `numpy`, `scipy`, and `scikit-image` (plus transitive deps: `networkx`, `imageio`, `tifffile`, `lazy-loader`, `packaging`) to the root `requirements.txt` via `pip freeze`. This is a meaningfully heavier dependency footprint than the rest of the repo, but justified given the request explicitly asked for real hit-or-miss/skeletonization, which aren't reasonable to hand-roll correctly and efficiently in pure PIL.

## 2026-09-17 — Pulled in PD position tracker from the class repo

Fetched `pd_tracker.py` from the class practice repo (`chrisbuerginrogers/ME193-Robotics`, path `Public stuff/Controls/pd_tracker.py`) via the GitHub API/raw URLs (no local clone of that repo was needed or made — just pulled the two files this exercise needs).

- New `9-17/` folder (dated folder-per-day pattern) with `pd_tracker.py` and its dependency `lelib.py` (the shared LEGO Education wrapper used across the class's examples — same file also used implicitly by future exercises from that repo). Added `9-17/README.md` in this repo's own style (not a copy of the source repo's README), crediting the source and covering setup/usage/how-it-works.
- This exercise needed one new dependency, `matplotlib` (for the live Kp/Kd slider plot) — `legoeducation` was already in the root `requirements.txt` from `9-10/`. Installed into the shared root venv, then `pip freeze` regenerated `requirements.txt` (pulled in matplotlib's transitive deps: `contourpy`, `cycler`, `fonttools`, `kiwisolver`, `pyparsing`, `python-dateutil`, `six`).
- Updated root `README.md`'s structure list to point into `9-17/`.
- Verified both new files parse and import cleanly in the venv (`lelib.singleMotor`/`doubleMotor`, `pd_tracker.control_loop`/`main` all resolve) without invoking `main()` — running it for real needs actual LEGO Single/Double Motor hardware over Bluetooth, which wasn't available to test end-to-end this session.
- Set `CARD_COLOR`/`CARD_SERIAL` in `pd_tracker.py` to this kit's Connection Card: orange, serial `'0994'` (string, not int — matches the `9-10/spin_motor.py` pattern of preserving the serial's exact digit format).

## 2026-09-22 — Added AprilTag centering exercise

New `9-22/` folder (dated folder-per-day pattern): the car drives back and forth on a track parallel to the laptop screen with a printed AprilTag on a tower, and the code centers it in the webcam frame.

- `9-22/generate_tag.py` — generates a printable AprilTag (36h11 family, id 0 by default) with a white quiet-zone border via `cv2.aruco.generateImageMarker`. Ran it to produce the actual `9-22/tag_0.png` committed to the repo (the one to print).
- `9-22/track_and_drive.py` — live loop: `cv2.aruco.ArucoDetector` with the `DICT_APRILTAG_36h11` dictionary finds the tag each frame, draws a red polygon outline + centroid coordinates on the video feed, and drives a Double Motor (via `lelib.doubleMotor`, copied in same as `9-17/`) with `speed = Kp*error - Kd*d(error)/dt` where `error` is the tag centroid's horizontal pixel offset from frame center. Proportional control alone gives the "faster far / slower near" bonus for free. On no detection: `dm.stop()` and reset derivative state (avoids a kick from the gap when the tag reappears). `SPRING_LOADED` toggle (default `True`, `Kd=0`) demonstrates the spring-mass-damper framing from the assignment's third question — underdamped overshoot-and-return vs. damped settling.
- New dependency: `opencv-contrib-python` (plain `opencv-python` doesn't ship the `aruco` module's AprilTag dictionaries) — confirmed `DICT_APRILTAG_36h11` and `ArucoDetector` are present in the installed build (OpenCV 5.0.0) before writing code around them. Installed into the shared root venv, `pip freeze` regenerated `requirements.txt`.
- Updated root `README.md`'s structure list to point into `9-22/`.
- Testing without hardware: pasted the generated `tag_0.png` into a synthetic blank frame at a known pixel offset and ran it through the real detection code path — confirmed the tag is found and the computed centroid matches the known placement to sub-pixel accuracy. Also compiled both scripts and confirmed `lelib`/`legoeducation` import cleanly. The motor-driving half (`dm.connect()`/`run()`/`stop()`) is untested against real hardware this session, same caveat as `9-17/` — `KP`, `DEAD_ZONE_PX`, and `DRIVE_SIGN` (which way is "forward" is arbitrary until tried on the actual car) are starting guesses flagged for tuning in `9-22/README.md`.
- `9-22/README.md` answers the assignment's three required questions (controller/policy description, no-tag behavior, spring-loaded overshoot) directly, in addition to setup/run instructions.
