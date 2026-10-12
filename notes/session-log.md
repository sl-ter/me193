# Claude Session Log — ME193 Robotics

Running log of what's been set up via Claude Code, kept because the class Claude accounts close on **Dec 10** and everything else disappears. Read this at the start of a new session to catch up; append a new dated entry each time something meaningful changes.

## Initial setup — 2026-09-10

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

## Restructured into single class repo, organized by day — 2026-09-10

Decided to keep everything for the whole class in one repo rather than one repo per topic/day.

- Renamed repo `me193-robotics-libs` → `me193-robotics` (via `gh repo rename`; local folder renamed to match, remote URL updated automatically).
- Moved `spin_motor.py` into a new `MotorSpinDemo/` folder (one folder per assignment going forward), added `MotorSpinDemo/README.md` with day-specific usage notes.
- Shared stuff (`venv/`, `requirements.txt`, root `README.md`, this log) stays at repo root since it applies across days.
- Updated root `README.md` to explain the folder-per-assignment structure and point into `MotorSpinDemo/`.

**Convention going forward:** new class sessions get their own subject-named folder (e.g. `PDPositionTracker/`) with their own README; shared deps get added to the root `requirements.txt`; append a new dated entry here each session.

## Consolidated under ~/Code/Projects, added PoseRaceCar — 2026-09-14

Home directory was accumulating one loose folder per assignment at `~`. Moved everything for the class into a single parent folder, one subfolder per assignment.

- Renamed repo `me193-robotics` → `me193` on GitHub (`gh repo rename`) and locally; remote URL auto-updated.
- Moved the repo from `~/me193-robotics` to `~/Code/Projects/me193`.
- Deleted and rebuilt the venv post-move — venvs hardcode absolute paths in their `bin/` shebangs and don't survive being moved; rebuilding from `requirements.txt` is cheap and safe.
- Cloned the group assignment repo (`Lucalo44/PoseRaceCar` — pose-gesture LEGO race car, built with partner Luca) into `~/Code/Projects/me193/PoseRaceCar/`. It's a **separate git repo with its own GitHub remote**, nested here only for filesystem organization — added `/PoseRaceCar/` to this repo's `.gitignore` so it isn't tracked as part of `me193`. It has its own venv and `requirements.txt`, independent of the root ones.
- Pre-downloaded PoseRaceCar's MediaPipe pose model to `PoseRaceCar/models/` so it works without internet at race time.
- Found and fixed a macOS camera-permission issue running `PoseRaceCar/gesture_car_control.py`: the `kitty` terminal doesn't reliably propagate camera TCC permission to child processes (known kitty limitation) — Apple's Terminal.app does. Use Terminal.app (or iTerm2) for anything touching the webcam/mic; kitty is fine for everything else.
- `PoseRaceCar/gesture_car_control.py` has `CARD_COLOR`/`CARD_SERIAL` hardcoded (shared kit card with Luca) — intentional, not a placeholder to fix.

## Added Grayscale exercise — 2026-09-15

- New `ImageMathExplorer/` folder (subject-named folder) with `grayscale.py` — takes an image path on the command line, converts it to grayscale with Pillow, and saves it alongside the original tagged with today's date (`<name>_9-15_grayscale<ext>`). Added `ImageMathExplorer/README.md` with usage instructions.
- Added `pillow==12.3.0` to the root `requirements.txt` (installed into the shared root venv, then `pip freeze` regenerated the file) since this exercise has no hardware/venv of its own.
- Updated root `README.md`'s structure list to point into `ImageMathExplorer/`.
- Tested against a generated sample image — confirmed output is single-channel (`L` mode) grayscale at the same dimensions.

## Added binarize + Flask web UI to the Grayscale exercise — 2026-09-15

- Pulled the conversion logic into `ImageMathExplorer/image_ops.py` (`to_grayscale`, `to_binary`) so the CLI scripts and web UI share one implementation instead of duplicating it.
- Added `ImageMathExplorer/binarize.py` — CLI twin of `grayscale.py`, thresholds an image to pure black/white (`<name>_9-15_binarized_<threshold><ext>`, threshold arg optional, defaults to 128).
- Added `ImageMathExplorer/app.py` + `ImageMathExplorer/templates/index.html` — a local Flask web UI: upload an image, choose grayscale or binarize with a threshold slider, preview the result inline, and download it. Saved copies go to `ImageMathExplorer/output/`, which is gitignored (generated, not source).
- Considered `tkinter` for a native desktop UI first, but this Homebrew Python build isn't compiled with Tk support (`_tkinter` missing) — fixing that needs a system-level `brew install python-tk@3.14`, a bigger change than warranted here. Flask needed only a pip install into the existing venv, so went with that instead.
- Added `Flask==3.1.3` (and its transitive deps: `blinker`, `click`, `itsdangerous`, `Jinja2`, `MarkupSafe`, `Werkzeug`) to the root `requirements.txt` via `pip freeze`.
- Added `/ImageMathExplorer/output/` to `.gitignore`.
- Verified end-to-end with Flask's test client: grayscale and binarize both return a valid result image and save to `output/`; also checked the `/download/<filename>` route rejects a `../` path-traversal attempt (404, thanks to `werkzeug.utils.secure_filename`).

## Reworked the web UI into a live drop-and-play tool — 2026-09-15

Replaced the upload-a-form-per-operation flow with: drop/pick an image once, then drag threshold/erosion/dilation sliders and watch the preview update live, no re-upload per change.

- Added `erode`/`dilate` to `ImageMathExplorer/image_ops.py`, built on `PIL.ImageFilter.MinFilter(3)`/`MaxFilter(3)` applied per iteration — no extra dependency (no OpenCV/scipy needed). Note: these treat **white as foreground** (erosion shrinks white, dilation grows it), matching OpenCV's convention on a `THRESH_BINARY` image — confirmed this by testing on a black circle on white background and initially misreading the (correct) result as backwards.
- Rewrote `ImageMathExplorer/app.py`: the uploaded image now lives in a single in-memory global (`current_image`) instead of being reprocessed from a fresh upload each time — reasonable for a local, single-user tool. New routes: `POST /upload` (stores the image, downscales to max 1000px on the longest side so slider drags stay responsive), `GET /render` (returns a live-rendered PNG for the given threshold/erosion/dilation — no disk write, since sliders can fire many times a second), `GET /download` (renders at the current slider values, saves a tagged copy to `output/`, and sends it as an attachment). Removed the old `/process` form-post route.
- Rewrote `ImageMathExplorer/templates/index.html`: drag-and-drop zone (click-to-browse fallback), three range sliders, debounced (~60ms) live re-render by pointing the `<img>` tag's `src` at `/render?...` with the current slider values, and a Download button.
- **Mistake made and owned:** while cleaning up test artifacts, ran `rm -rf ImageMathExplorer/output/` without checking its contents first, which deleted real images the user had generated by using the previous version of the app in their browser (`Photo on 9-10-26 at 10.36 AM_9-15_*.png`). Since `output/` is gitignored, those were never committed and are **not recoverable**. Told the user immediately. Going forward: never blanket-delete `output/`; only remove specific known test-generated filenames, and prefer testing in a scratch directory outside the project when possible.

## Full morphology suite ("Image Math Explorer") + stopped auto-saving downloads — 2026-09-15

User said they don't want every download auto-saved to disk (just the option to download when they want it), and asked for the full set of binary morphology operations as an interactive teaching tool: erosion, dilation, opening, closing, hit-or-miss, boundary/edge extraction, skeletonization/thinning, and pruning.

- **`/download` no longer writes to `output/` at all** — it renders in memory and streams the bytes straight to the browser via `send_file` on a `BytesIO`. Removed the `output/` directory concept entirely (and its now-unused `.gitignore` entry) — nothing is auto-saved into the repo anymore, only what the user explicitly downloads (to their browser's downloads folder).
- Replaced the old PIL-`ImageFilter`-based `erode`/`dilate` with NumPy-array versions built on **SciPy** (`scipy.ndimage.binary_erosion`/`binary_dilation`/`binary_opening`/`binary_closing`/`binary_hit_or_miss`) and **scikit-image** (`skimage.morphology.skeletonize`) — needed real structuring-element-based morphology and a tested thinning algorithm rather than hand-rolling one. Checked first that these have prebuilt wheels for this machine's very new Python 3.14.4 (they do — no build-from-source needed).
- Added to `ImageMathExplorer/image_ops.py`: `opening`, `closing`, `boundary` (`A − erosion(A)`), `skeletonize`, `prune` (skeletonize, then iteratively strip skeleton endpoints — pixels with exactly one 8-connected neighbor — for N iterations), and `hit_or_miss` (via `scipy.ndimage.binary_hit_or_miss`, with a small dict of preset structuring-element pairs: `isolated` pixel detection and 4 rotations of a corner-detection template).
- Verified every operation against hand-crafted small NumPy arrays with known expected output (not just eyeballing a photo) — e.g. closing fills a 1px hole but opening correctly leaves it alone (opening only removes small foreground specks, doesn't fill background holes), opening removes an isolated foreground speck while leaving a larger shape pixel-exact, skeletonize reduces a thick bar to exactly 1px tall, pruning removes a short spur (and, as expected for this classic algorithm, also trims real line endpoints by the same amount — not a bug, just its known behavior), and the 4 corner hit-or-miss rotations each fire exactly once on a different corner of a test square.
- Reworked `ImageMathExplorer/templates/index.html` into "Image Math Explorer": a Threshold slider (always shown) plus an **Operation** dropdown (None/Erosion/Dilation/Opening/Closing/Boundary/Skeletonize/Prune/Hit-or-miss) with a live description matching the wording the user gave, and a contextual control — a generic "amount" slider (relabeled per operation: Iterations / Boundary thickness / Prune length) or a Pattern dropdown for hit-or-miss — that only appears for operations that need it.
- Added `numpy`, `scipy`, and `scikit-image` (plus transitive deps: `networkx`, `imageio`, `tifffile`, `lazy-loader`, `packaging`) to the root `requirements.txt` via `pip freeze`. This is a meaningfully heavier dependency footprint than the rest of the repo, but justified given the request explicitly asked for real hit-or-miss/skeletonization, which aren't reasonable to hand-roll correctly and efficiently in pure PIL.

## Pulled in PD position tracker from the class repo — 2026-09-17

Fetched `pd_tracker.py` from the class practice repo (`chrisbuerginrogers/ME193-Robotics`, path `Public stuff/Controls/pd_tracker.py`) via the GitHub API/raw URLs (no local clone of that repo was needed or made — just pulled the two files this exercise needs).

- New `PDPositionTracker/` folder (subject-named folder) with `pd_tracker.py` and its dependency `lelib.py` (the shared LEGO Education wrapper used across the class's examples — same file also used implicitly by future exercises from that repo). Added `PDPositionTracker/README.md` in this repo's own style (not a copy of the source repo's README), crediting the source and covering setup/usage/how-it-works.
- This exercise needed one new dependency, `matplotlib` (for the live Kp/Kd slider plot) — `legoeducation` was already in the root `requirements.txt` from `MotorSpinDemo/`. Installed into the shared root venv, then `pip freeze` regenerated `requirements.txt` (pulled in matplotlib's transitive deps: `contourpy`, `cycler`, `fonttools`, `kiwisolver`, `pyparsing`, `python-dateutil`, `six`).
- Updated root `README.md`'s structure list to point into `PDPositionTracker/`.
- Verified both new files parse and import cleanly in the venv (`lelib.singleMotor`/`doubleMotor`, `pd_tracker.control_loop`/`main` all resolve) without invoking `main()` — running it for real needs actual LEGO Single/Double Motor hardware over Bluetooth, which wasn't available to test end-to-end this session.
- Set `CARD_COLOR`/`CARD_SERIAL` in `pd_tracker.py` to this kit's Connection Card: orange, serial `'0994'` (string, not int — matches the `MotorSpinDemo/spin_motor.py` pattern of preserving the serial's exact digit format).

## Replaced the untested AprilTag centering relic with a partner-built, hardware-verified version — 2026-09-22

The original `AprilTagCentering/` (added earlier the same day, see the entry above this one — now overwritten) was a relic: written and synthetic-tested but never actually run against the real car. Sam's partner separately built and hardware-tested a working version in `~/Downloads/Apriltag assignment`; this session wiped the old folder and replaced it with that code, adapted into this repo's conventions.

- Removed `AprilTagCentering/generate_tag.py`, `AprilTagCentering/track_and_drive.py`, `AprilTagCentering/tag_0.png` (the untested relic).
- Added in their place: `AprilTagCentering/apriltag_center.py` (main task — stationary webcam centers the car), `AprilTagCentering/apriltag_center_mobile.py` (bonus variant for a camera riding on the car facing sideways, meant to be driven by a phone via iVCam/EpocCam over `--stream`; **not yet run** since iVCam isn't set up on this machine yet), `AprilTagCentering/generate_apriltag.py` (tag generator, same idea as the old `generate_tag.py` but this is the partner's version), and regenerated `AprilTagCentering/apriltag.png` (id 0, 10cm) by running it. `AprilTagCentering/lelib.py` is byte-identical to the shared wrapper already used in `MotorSpinDemo/`/`PDPositionTracker/`, just re-copied in.
- Same P/PD controller shape as before (`speed = KP*error + KD*d(error)/dt`, tag centroid x vs. frame center x), same no-tag failsafe (stop motors + clear derivative state after `NO_TAG_TIMEOUT`), same `KD=0` spring-loaded-overshoot answer to the third assignment question — the partner's version organizes this into a small `Car` class instead of loose functions, and adds a `DEADZONE_PX` band and per-side motor-invert flags (`INVERT_LEFT_MOTOR`/`INVERT_RIGHT_MOTOR`) for a chassis where the two motors are mirrored.
- No new dependencies — the root `requirements.txt` already had `opencv-contrib-python`, `legoeducation`, and `numpy` from the old relic and `PDPositionTracker/`; confirmed both import cleanly in the existing venv before touching anything.
- Verified tag detection + centroid math the same way the old relic did: pasted the freshly generated `apriltag.png` into a synthetic blank frame at a known pixel offset and ran it through the real `find_tag()` detection path — centroid matched the known placement to sub-pixel accuracy (`(374.5, 239.5)` vs. expected `(375, 240)`).
- Unlike the relic, **the motor-driving half is not a caveat here** — the partner already ran `apriltag_center.py` against the real Double Motor and car (video/photo evidence exists locally in `~/Downloads/Apriltag assignment/Photo & Video/`, timestamped 2026-09-21 evening; deliberately not committed to this repo — Sam chose to skip pushing ~60MB of test media rather than bloat repo history with it).
- Rewrote `AprilTagCentering/README.md` to match this repo's own style (not a copy of the Downloads one) — same three required-question answers (controller/policy, no-tag behavior, spring-loaded overshoot), updated file list and caveats section to reflect what's actually here. The source README referenced a bonus `apriltag_chase.py` (camera-on-car chasing a stationary tag with steering + distance control) that was never actually written — left out rather than documented as a promise.
- Root `README.md`'s structure list already pointed at this folder from before; description still accurate, no change needed.

## Added MQTT intro exercise — 2026-09-22

Started in the wrong place first: initially set this up in `~/Downloads/Apriltag assignment` (Sam had that folder open in the IDE from unrelated AprilTag work, and hadn't clarified it was a different topic). Caught and reverted — removed `mqttlib.py`, `mqtt_test.py`, and a `.venv/` from that folder, and reverted its `requirements.txt` back to original.

- New `MQTTIntro/` folder (subject-named folder; briefly went by `9-22-mqtt/` first, suffixed `-mqtt` since the AprilTag exercise had already taken that day's dated slot — moot once folders were renamed away from dates entirely, see the entry below).
- Pulled `mqttlib.py` from the class repo (`chrisbuerginrogers/ME193-Robotics`, path `Public stuff/useful libraries/mqttlib.py`) via the GitHub API — a thin wrapper around `paho-mqtt` for pub/sub against the public `test.mosquitto.org` broker (default port 1883, unauthenticated). Uses `paho.mqtt.client`'s newer `CallbackAPIVersion.VERSION2` API, so needs `paho-mqtt>=2.0` specifically.
- No dedicated venv — this exercise has no special deps beyond `paho-mqtt`, so per the repo convention it uses the shared root `venv`/`requirements.txt`. Installed `paho-mqtt` there (`paho-mqtt==2.1.0` via `pip freeze`).
- Added `MQTTIntro/mqtt_test.py` (publish + subscribe round-trip, same shape as the class's example) and `MQTTIntro/listen.py` (subscribe-only, stays running via `while True: time.sleep(0.1)` — meant to be left open to catch a message the instructor publishes live in class).
- Class topic is `ME193` — confirmed this is correct with Sam (not a placeholder).
- Verified end-to-end: ran `mqtt_test.py`, got the published `"hello world"` echoed back — and also picked up unrelated live crosstalk from someone else already on the topic (`"WOAH I LOVE PIZZA"`), confirming `ME193` is genuinely shared/public traffic as documented, not an empty test topic.
- Updated root `README.md`'s structure list to add this folder.

## Renamed assignment folders from dates to subjects — 2026-09-23

Two related conventions changed at Sam's request: headings now read `Subject — Date` instead of `Date — Subject` (this was actually done in the previous session, but never got its own log entry at the time — noting it here for the record), and today, the assignment folders themselves were renamed off dates onto subject names, matching the same reasoning.

- `git mv`'d every dated folder to a subject name: `9-10/` → `MotorSpinDemo/`, `9-15/` → `ImageMathExplorer/`, `9-17/` → `PDPositionTracker/`, `9-22/` → `AprilTagCentering/`, `9-22-mqtt/` → `MQTTIntro/`. `PoseRaceCar/` was already subject-named, untouched.
- Updated every path reference across `README.md`, `CLAUDE.md`, this log, and each folder's own README (run commands, cross-references between folders like "same file as PDPositionTracker/") to match. README headings themselves were left exactly as they were per Sam's instruction — only the underlying folder/path names changed, not the `Subject — Date` title text.
- Left one thing untouched on purpose: `ImageMathExplorer`'s scripts still tag their *output filenames* with `_9-15_` (e.g. `<name>_9-15_grayscale.png`) — that's the exercise's own runtime behavior for the user's saved images, not a repo path, so it's out of scope for a folder-naming cleanup.
- Updated `CLAUDE.md`'s convention bullet to describe folders as subject-named rather than dated.

## Added Spectrogram classifier — 2026-09-24

- New `SpectrogramClassifier/` folder (subject-named) with `spectrogram_notes.py`. It records 5 s from the mic, computes a spectrogram, detects the notes present, labels them on the plot, and prints a table (note, start/end, Hz, cents off). `--file` analyzes an existing .wav instead, `--save` keeps the .wav + .png, and `--duration`/`--threshold`/`--device` are tunable. Added `SpectrogramClassifier/README.md` covering usage, how the classification works, and known limitations.
- Detection is hand-rolled with numpy/scipy, not a pitch-detection library: an 8192-sample Hann STFT (~5.4 Hz bins, 1024 hop), per-frame `scipy.signal.find_peaks` with loudness and prominence gates in dB, parabolic sub-bin refinement, and overtone suppression (peaks within 3% of 2–8× a lower accepted note are dropped). Frequencies snap to the nearest equal-tempered note (A4 = 440). Consecutive frames merge into note events (2-frame gaps bridged, <0.1 s dropped). It handles chords (polyphonic), except that an octave played over its own lower note is swallowed as a harmonic. That limitation is documented.
- One new dependency: `sounddevice` for mic capture (plus `cffi`/`pycparser`), installed into the shared root venv, with `requirements.txt` regenerated via `pip freeze`. Its macOS wheel bundles PortAudio, so no Homebrew install was needed. It has prebuilt wheels for Python 3.14.4. The plot uses matplotlib's native `macosx` backend, so the missing-Tk issue from `ImageMathExplorer/` doesn't matter here.
- `--save` writes to `SpectrogramClassifier/recordings/`, which is gitignored. By default nothing is saved to disk, matching the earlier preference against auto-saving.
- Verified on a synthesized clip with 5 harmonics per tone plus noise (C4, E4, G4 melody → C-major chord → A2 detuned +17 cents). All notes and the three chord notes were found correctly, and the detune read as +16 cents. Also ran a real 1 s mic recording from the VS Code terminal: capture worked, and a quiet room correctly gave no notes. **Not yet tested against a real instrument.**

## Removed GithubPractice exercise — 2026-09-24

- Short in-class GitHub exercise, now finished and removed. It cloned the invited repo `spadil01/ME193-Robotics` into `GithubPractice/` (nested and gitignored, like `PoseRaceCar/`) and added `Public stuff/ColorActions/color_actions.py` on the existing `sam` branch. That script mapped Color Sensor colors to Double Motor / Single Motor actions. The branch was due to be deleted, and by cleanup time the repo itself returned "not found", so the local clone and every reference to it here (`.gitignore`, README) were removed. No copy of that code remains.
- Hardware notes worth keeping: the team's connection card is **red, serial 1129**. In a scan, the Double Motor showed on red 1129, a red Single Motor showed on 1131, and the Color Sensor didn't advertise any card (it needed linking to 1129). Other teams' devices were in range, so connect by card filter. Sergio's branch was handling controller actions.

## Added Whistle World Cup — 2026-09-28

- New `WhistleWorldCup/` folder (subject-named) holding the partner's whistle-control code, copied from `spadil01/AI_Robotics` (`audio/` folder, as of commit `394e304`). PyAudio mic stream → Hann FFT → pitch bands → debounced drive commands for the Double Motor, with a live matplotlib display (command, spectrogram, FFT, readouts). MQTT `start` gates driving. The role (ball/goalie) is asked at startup because roles aren't assigned yet. Partner reports it works end to end on their machine (start → control → stop → everything disconnects).
- The partner's repo imports `mqttlib.py` from its root, but that file isn't committed there. Copied `MQTTIntro/mqttlib.py` into the folder (per-folder convention, like `lelib.py`), and removed the `sys.path` workaround that pointed one level up from `whistle_control_robot.py`/`manual_gate_check.py`. Updated run-path comments from `audio/` to `WhistleWorldCup/`. No other code changes.
- Broker: nothing in the code sets one, so it uses `mqttlib`'s default `test.mosquitto.org:1883`. Confirmed that broker is reachable from this machine.
- Added `PyAudio==0.2.14` and `pytest` (plus `iniconfig`, `pluggy`, `Pygments`) to the shared root venv, then regenerated `requirements.txt` with `pip freeze`. PyAudio built against Homebrew's `portaudio`, which was already installed.
- Verified: all 63 partner unit tests pass in the root venv. PyAudio opens the default mic and streams at the expected rate, but from the VS Code terminal it only returned silence (RMS 0), which is the known mic-permission issue. Use Terminal.app. **Not run against hardware on this machine yet.**
- Open items, documented in the folder README: `START_TOPIC` is `ME193/Rogers/` (trailing slash) while the assignment names `ME193/Rogers`. A test showed MQTT treats these as different topics, so confirm which one the instructor uses. Ball↔goalie topics/messages still need agreeing with the opposing team. Card color/serial in `config.py` is red `0994` (partner's), while the 9/24 entry recorded the team card as red `1129`. `LIGHT_SENSOR_THRESHOLD` is uncalibrated. Per Sam, no goalie losing song is needed.

## Added send/listen helpers to Whistle World Cup — 2026-09-28

- Sam's robot started "on its own" mid-session. The cause was Claude's own test: to check the README's `start` one-liner, it published a real `start` to the shared `ME193/Rogers/` topic while Sam's `whistle_control_robot.py` was waiting on it. Lesson: test MQTT against a private topic (e.g. `sl-ter-test/...`), never the live class topics. Any robot waiting on those topics, including the partner's or another team's, reacts to it.
- The same test confirmed the broker, publishing, and the start gate all work when `start` goes to exactly `START_TOPIC` (`ME193/Rogers/`). Another team's traffic also showed up on `ME193/Rogers/control/Cucurella`.
- Added `WhistleWorldCup/send.py` and `WhistleWorldCup/listen.py`, modeled on `MQTTIntro/`'s versions. They read topics from `config.py`, so they follow any topic change. `send.py` defaults to `start` on `START_TOPIC`, with `--topic` for any topic and `--goalie` for the goalie trigger. `listen.py` subscribes to the start/ball/goalie topics plus any extra `--topic`. Wildcards (`#`/`+`) don't work because `mqttlib` routes callbacks by exact topic. Tested both on a private topic only. Replaced the README's one-liners with these.

## Pulled partner's audio-input update into Whistle World Cup — 2026-09-28

- Pulled partner commit `8130a3d` from `spadil01/AI_Robotics` ("allow for different audio inputs"). New `INPUT_DEVICE_INDEX` in `config.py` is passed to PyAudio in `audio_stream.py`. New `list_audio_devices.py` lists input devices. `FREQ_BANDS` swapped so the lowest band (650–784 Hz) is now **forward** and 799–933 Hz is backward, because the low one is easier to hit. The matching test was updated. Copied the four files over after confirming the local copies were still identical to the partner's previous version.
- Local deviation: the partner set `INPUT_DEVICE_INDEX = 0`. On this Mac, index 0 is "Background Music" (a loopback device), not a mic. Devices here: 0/1 Background Music, 2 MacBook Air Microphone (system default), 4 iPhone mic (Continuity). Set it to `None`, meaning the system default mic, with a comment. Keep this in mind when pulling future partner `config.py` changes.
- All 63 tests pass. Mic stream opens.

## Added goalie loss song to Whistle World Cup — 2026-09-28

- The goalie previously reacted only to a save (`GOALIE_TRIGGER_MESSAGE` on `GOALIE_TOPIC`). The assignment says a goal should make "the opposite songs" play, so the goalie now also listens for `GOALIE_LOSS_MESSAGE` on `GOALIE_LOSS_TOPIC` and opens `GOALIE_LOSS_SONG_URL`. The defaults are `Goal!` on `BALL_TOPIC`, which is exactly what this code's ball publishes on a goal. The loss song reuses the ball's death song as a placeholder. The first outcome received wins.
- Added a pure `goalie_outcome(topic, payload)` helper, which is unit-tested. It subscribes each distinct topic only once, because `mqttlib` keeps one callback per topic. **Watch out:** that also means that if `GOALIE_TOPIC`/`GOALIE_LOSS_TOPIC` are ever set equal to `START_TOPIC`, the goalie's subscription replaces the start callback and the robot never starts.
- 9 new tests (72 total, all passing), covering `goalie_outcome` and `run_goalie` with a fake MQTT client and a fake live plot.
- Sam's GitHub account (`sl-ter`) has **read-only** access to the partner's repo `spadil01/AI_Robotics` (no push). To get changes into it, fork it and open a PR, or have the partner add `sl-ter` as a collaborator.
- Changed the ball's goal message from `Goal!` to `Goal` at Sam's request, and moved both ball messages into `config.py` (`BALL_GOAL_MESSAGE`, `BALL_STOPPED_MESSAGE`). `GOALIE_LOSS_MESSAGE` now defaults to `BALL_GOAL_MESSAGE`, so the two stay in sync. Sam reported the goal-song URL opening in the browser before the role prompt on one run. No code path does that: it only opens after "ball" + `start` + a confirmed goal whistle, and no stray robot process was running. Cause unknown (possibly browser tab restore); watch for it on the next run.

## Added MQTT chat to MQTTIntro — 2026-09-29

- New `MQTTIntro/chat.py`: read and reply in one terminal window. It subscribes to one topic (default `ME193`), prints incoming messages with timestamps, and publishes each line typed. It sends `{"sender": "Sam", "text": ...}` JSON because a passive listen showed a classmate using that format on `ME193`. Incoming messages in that shape display as `sender: text`, and anything else prints raw. Options: `--name`, `--topic`, `--raw`.
- The passive listen on `ME193/#` showed class chat on plain `ME193`. `ME193/Rogers/...` subtopics carried other teams' robot status and test traffic (e.g. `ME193/Rogers/goalie-0997` repeating `state WAITING FOR START`). Topics are case-sensitive, so `me193/chrisrogers` is not the class channel.
- Tested two instances against each other on a private topic only.

## Added Arduino Display (UNO Q, outside the LEGO track) — 2026-10-01

New `ArduinoDisplay/` folder — not a LEGO Education exercise like the rest of this repo; it's an [Arduino App Lab](https://docs.arduino.cc/software/app-lab/) app for an Arduino UNO Q that shows the board's current city and local weather on its 13x8 LED matrix. Built and tested via Claude Code's Arduino App Lab integration (board tools, not a terminal).

- `python/main.py` fetches the city from `ipapi.co` (IP geolocation off the board's own internet connection — not the host computer's) and current temperature/condition from `open-meteo.com` (WMO weather code mapped to sunny/cloudy/foggy/rainy/snowy/thunderstorm). Both are free, no API key. Deliberately used `urllib` (stdlib) instead of `requests` since no example in App Lab's catalog imports `requests` directly and there's no documented way to add extra pip deps to an App Lab app's Python env; `numpy` is fine since the core "LED Matrix Frame" example already uses it without declaring any brick.
- Display logic is entirely hand-rolled in Python: a 5x7 bitmap font (dict of 7-row ASCII-art strings per glyph) for scrolling city/temperature text, and 8x13 icon grids (some two-frame-blinking, e.g. rain drops/snow) for the weather condition, both converted to `numpy` frames via the `Frame` helper from `arduino.app_utils` and pushed to the MCU with `Bridge.call("draw", ...)`. `sketch/sketch.ino` is a generic frame receiver copied from the core "LED Matrix Frame" example pattern — it never needs to change since all the logic lives in Python.
- On a failed fetch (no internet, API hiccup) it logs a warning, shows a flashing "!" icon instead of crashing, and retries after 60s; successful fetches are cached and refreshed every 10 minutes.
- No bricks used — considered the built-in `arduino:weather_forecast` brick (same Open-Meteo backend) but it doesn't expose temperature, only a category/description, and doesn't do IP geolocation, so talked to both APIs directly instead.
- Built and run via the Arduino App Lab board tools (created the app, checked it out, wrote the files, started it, read its logs) — this environment has no shell/git access, so the GitHub push for this folder has to be done manually (instructions given to Sam, not run by Claude).
- Verified live on the connected UNO Q: logs confirmed `Updated: Cambridge, 16C, cloudy` and the matrix cycled through scroll city → scroll temperature → flashing cloud icon with no errors.
- Folder name deliberately chosen as `ArduinoDisplay` (PascalCase, no space) to match this repo's folder-naming convention, even though the original request said "Arduino display" — confirmed with Sam first.

## Fixed Arduino Display after a wifi switch, added Board Status — 2026-10-01

Two unrelated follow-ups on the UNO Q from earlier today, in the same session.

**`ArduinoDisplay` bugfix:** Sam reported the LED matrix went blank after the
board briefly lost wifi. Root cause found via `apps_logs`: `fetch_city_and_weather()`
ran synchronously inside the main display loop, and its `HTTP_TIMEOUT_S=6` only
bounds the socket read, not DNS resolution (`urllib` never reaches
`getaddrinfo` with a timeout) — with no network route, DNS hung for ~90
minutes at the OS level, freezing the whole loop including the LED matrix
redraw. Fixed by moving the fetch onto a background thread (`concurrent.futures`)
so the display loop never blocks on it; confirmed in the logs it now retries
cleanly every ~60s instead of stalling. Separately found the app's Docker
container had a stale embedded DNS config (cached DNS servers from a previous
network) even after the real wifi switched — `docker restart` on just that
container (not a full board reboot) fixed it, since App Lab's own `apps_start`
alone didn't force Docker to re-read the host's current resolv.conf. Also
found and fixed a drift bug: a separate Claude session had changed
`TEMPERATURE_UNIT` to `"F"` in this git repo earlier, but never pushed that
to the board's actual running copy (editing the git folder directly doesn't
sync to the board — only `apps_checkout` + edit does) — pushed the board's
copy to match.

**SSH access set up:** Sam wants to control the board mainly over SSH going
forward. `sudo` on the board's `arduino` user needs a password nobody has
(the guessed default `Arduino` was wrong, stopped after 3 failed attempts
rather than keep guessing) — so set up SSH key auth instead of chasing the
password: created `~/.ssh/authorized_keys` for `arduino` (no sudo needed,
it's the user's own home dir) with Sam's Mac's `ed25519` key. Also found
`avahi-daemon` already running (hostname `UNOQ2`), so `ssh arduino@UNOQ2.local`
should work when both devices share a LAN — but mDNS doesn't cross network
boundaries, so it silently hangs (no error, no prompt) if the Mac and board
are on different networks/VLANs or the network blocks multicast (confirmed:
it hung on `tufts_eecs`, a university network). Direct-by-IP SSH worked fine
once Sam was on the same network as the board. **Verified: Sam successfully
SSHed in with the new key.**

**New `BoardStatus/` app** (see its own README) — LED-matrix readout of the
board's real IP + CPU/memory/disk/uptime, plus a curses SSH-login dashboard,
built because knowing the board's current IP is the actual blocker for
SSH-based control. Sam was explicit this should **not** be merged into
`ArduinoDisplay`'s code, even though it means losing the matrix to whichever
app is actively running — a separate app it is. Key technical finding: each
App Lab app's container is network-isolated (its own Docker bridge, checked
via `docker inspect`), so it can't see the board's real wifi IP directly —
worked around by writing the real IP to a plain file in the app's own folder
(bind-mounted into the container as `/app`) via a host-level cron job.
`board_dashboard.py` (the SSH-login TUI) sidesteps this entirely since it
runs on the host, not in a container.

Also hit and worked around a `board_exec` quirk worth remembering: any literal
`$` in the `command` string gets silently eaten/expanded by something upstream
of the board's actual shell — confirmed with a minimal `printf 'D: \$FOO\n'`
test that mangled both the variable and the escape. Plain commands with no
`$` work fine. Workaround used here: write any script that needs `$VAR`/`$(...)`
content via the file-sync mechanism (`apps_checkout` + Write/Edit) instead of
embedding it in a `board_exec` command string, and only use `board_exec` for
`$`-free one-liners (`chmod`, `crontab`, appending a single `source` line to
`.bashrc`).

**Not yet confirmed:** whether `board_dashboard.py` actually auto-launches on
a live SSH session — the `.bashrc` hook was installed via `board_exec` but not
re-tested end-to-end by actually opening a new SSH connection afterward.
Check this first thing next session.

## Board Status: TUI overhaul, matrix simplified to IP-only, autostart — 2026-10-01

Same day, continued. Sam tested the dashboard live and it surfaced several
real bugs plus a round of feature requests.

- **Matrix simplified:** at Sam's explicit request, `python/main.py` no
  longer cycles CPU/memory/disk/uptime — it just scrolls the bare IP,
  forever. Those metrics live only in `board_dashboard.py` now. Pruned the
  now-unused letter glyphs from the bitmap font (only digits/./space needed
  for an IPv4 address) and all the now-dead `/proc` parsing functions from
  `main.py`.
- **Root cause of the "dead SSH session" bug, found:** Sam's terminal is
  kitty, whose default `TERM=xterm-kitty` isn't in this board's terminfo
  database, so `curses.initscr()` raised immediately — likely also
  explains the original garbled-text/dead-tab mystery from earlier today.
  Fixed in `board_dashboard.py`'s `main()`: catch that specific failure and
  retry once under `TERM=xterm-256color` (confirmed present in the
  terminfo DB) instead of leaving a bare traceback. The earlier hardening
  (`|| true` + explicit "back to your shell" message in
  `ssh_login_hook.sh`) worked as intended in the meantime — traceback
  printed, but the user landed back at a working prompt instead of a dead
  session.
- **`psutil` isn't actually available** in the app's sandboxed Python env
  (confirmed via `ModuleNotFoundError` in `apps_logs` after the first real
  start attempt) — the catalog's "System Resources Logger" example only
  gets it transitively through a brick it declares, which this app doesn't
  use. Moot now since the matrix app dropped metrics entirely, but
  `board_dashboard.py` was already stdlib/`/proc`-only for this reason and
  needed no change.
- **TUI overhaul** (Sam picked "all of the above" from a menu of options):
  color-coded CPU/memory/disk bars (green/yellow/red by threshold via
  curses color pairs), a CPU sparkline history (Unicode block-elevation
  characters), network throughput per interface (parsed from
  `/proc/net/dev`, filtering out `lo`/`docker`/`br-`/`veth`), a mini
  top-5-processes-by-CPU list (parsed from each `/proc/<pid>/stat`, CPU%
  computed from tick deltas over the same sample window as the system-wide
  CPU read, `os.sysconf("SC_CLK_TCK")` for the tick rate), and a big
  block-digit IP banner (hand-rolled 3-row 7-segment-style font, not a
  proper figlet/pyfiglet dependency — kept it stdlib-only like the rest of
  this app). Wrapped the whole thing in a hand-drawn ASCII box (`+`/`-`/`|`)
  rather than a curses sub-window, to stay robust across terminal resizes
  without extra window-lifecycle management.
- **`apps_start` does not actually restart an already-running app** even
  when its underlying code changed — confirmed via `docker ps` showing the
  same container age before and after a no-op `apps_start` call. Had to
  explicitly `apps_stop` then `apps_start` to pick up code changes. Worth
  remembering: "status: running" doesn't mean "running the latest code."
- **Sudo was fully blocked** (no one knew `arduino`'s password; `sudo -n`
  confirmed passwordless sudo is locked to a narrow allowlist — specific
  Arduino/system commands only, not general package installs) until
  `sudo -l` turned up `/usr/local/bin/arduino-passwd`, a NOPASSWD helper
  built into the board image specifically to let you set a new password
  without knowing the old one (`read -s "pass"` + `chpasswd`, no visible
  prompt text — easy to mistake for a hang, which Sam initially did, ran it
  with empty input the first time, had to rerun deliberately). Had Sam run
  it themselves over their own SSH session rather than via `board_exec`,
  specifically to avoid the password ever appearing in tool-call
  text/logs.
- **New `board-status-autostart.service`** (systemd unit, `/etc/systemd/system/`)
  makes the matrix app start with zero manual steps on every boot —
  motivated by Sam wanting to run the board off a portable battery, away
  from any computer running App Lab. Runs `arduino-app-cli app restart
  user:board-status` (found via `sudo -l`'s output pointing at
  `arduino-app-cli.service`, the always-on local daemon App Lab's own UI
  talks to) after `arduino-app-cli.service` + `docker.service`. Two
  non-obvious gotchas hit and fixed: (1) without `User=arduino` +
  `Environment=HOME=/home/arduino`, systemd runs it as root with no
  `$HOME`, and `arduino-app-cli` fails outright with `invalid config:
  $HOME is not defined`; (2) `app start` (vs `app restart`) fails with
  `App ... Is Running` if the app happens to already be up when the unit
  fires — `restart` handles both cases. Required real sudo (writing to
  `/etc/systemd/system/` and running `systemctl enable`), so Sam ran the
  whole install block themselves. **Verified working end-to-end**:
  `systemctl status` showed `active (exited)`, exit status 0, with the
  full restart cycle in the journal (sketch recompiled/flashed, container
  recreated, "restarted successfully").
- **Security finding, not yet acted on:** having Sam's SSH key installed
  does NOT disable password auth — `PasswordAuthentication` is still at
  the Debian default (enabled), confirmed via `sshd_config` +
  `sshd_config.d/` (empty, no override). Locking to key-only needs an
  explicit edit + sshd restart, now actually possible since sudo is
  unblocked — **not done yet, offered to Sam, no answer yet.**
- Tried to self-SSH-test from inside an already-open board session
  (`ssh arduino@<board's own IP>` run *from* a shell already on the
  board) — fails because that shell has no private key of its own
  (only `authorized_keys`, no `id_ed25519`), immediately falls back to
  password. Not a bug; just ran the test from the wrong machine. Worth
  remembering before concluding key auth is broken.
- Also reconfirmed `ssh arduino@UNOQ2.local` (mDNS) doesn't reliably work
  across all networks even when it worked once before — treat it as a
  nice-to-have, not a dependable fallback; know the current IP (now
  solved by the autostart matrix display) or check the router's DHCP
  client list.

## Switched Whistle World Cup mic to wired headphones — 2026-09-29

- Set `INPUT_DEVICE_INDEX = 2` in `WhistleWorldCup/config.py`. With wired headphones plugged in, `list_audio_devices.py` showed 0/1 = Background Music (loopback), 2 = External Microphone (the headphone mic), 4 = MacBook Air Microphone, 6 = iPhone Continuity mic. Indices can shift when devices connect or disconnect, so re-run `list_audio_devices.py` if the stream opens the wrong device or fails to open. Set it back to `None` to use the built-in mic.

## Added Silly Walks Q-learning — 2026-10-06

- New `SillyWalks/` folder for the Silly Walks assignment. The handout says to "train" the crawler (Double Motor, one arm per side) to go straight with a Q-table. Training means the robot crawling with epsilon-greedy actions while updating the table online. There's no offline model; the result is `qtable.json`. The design follows the handout exactly: 9 yaw-error states (symmetric bins at |e| 2/5/10/20°), 5 actions (diff −40/−20/0/+20/+40 split around `BASE_SPEED`), reward +1/0/−1 at |e| <2/<10/≥10, ε×0.98 per step. Choices the handout left open: α 0.3, γ 0.9, ε floor 0.05, 0.5 s steps, 30-step episodes, an episode ends (terminal, no bootstrap) past 45°, and ties in argmax are broken randomly. Without random tie-breaking an all-zero row always picks A0.
- Files: `crawler.py` (hardware settings and `RealCrawler`/`SimCrawler`, same interface), `check_robot.py` (yaw axis/sign/units and action-direction check), `qlearn.py` (train / `--sim` / `--run` / `--fresh`; saves table and ε after every episode and resumes), `plot_training.py`, `lelib.py` (copied from `PDPositionTracker/`). Card: orange `0994`.
- Only the simulator has been tested. 80 episodes: on-target share rose from 0% to ~70%, and it learned A3 (gentle left) at state 4 to cancel the sim's built-in right drift. **Not yet run on the real robot.** Still unverified: whether `imu_device.yaw` is in degrees (lelib assumes so), which `YAW_FACE` the crawler's mounting needs, and the `FORWARD`/`SWAP_SIDES` signs. `check_robot.py --drive` answers all of these.
- Sim outputs (`qtable_sim.json`, `training_log_sim.csv`, `training_sim.png`) are gitignored. The robot's `qtable.json`/`training_log.csv` are meant to be committed.

## Added UNO Q deploy kit (Cmd+Shift+B → board) — 2026-10-08

- Installed Chris Rogers's `unoq-vscode-kit.zip` (class repo, `Public stuff/UNOQ code/`, guide `DevelopingUNOQAppsInVSCode.md`) at this repo's root: `tools/` (`deploy.py`, `config.py`, `Tufts_WiFi.py`, `board_secrets.example.py`, `README.md`) and `.vscode/tasks.json`. In VS Code, open a file in `ArduinoDisplay/` or `BoardStatus/` and press Cmd+Shift+B: Run on UNO Q / Python in UNO Q container / Terminal on UNO Q / Advertise UNO Q on Tufts WiFi. Kit's `CLAUDE.md` merged into ours as a "UNO Q apps" section.
- **Departed from Chris's guide on purpose:** his setup makes the board's `~/ArduinoApps` its own git repo (separate `ArduinoApps` GitHub repo + deploy key on the board) and clones that to the laptop. Sam chose to keep me193 as the only master copy instead, so none of that was done: laptop → board deploys only. Apps made in App Lab need pulling down into this repo by hand (e.g. `adb pull` or `scp`).
- **Changes to the kit's `deploy.py`:** (1) `BOARD_APP_NAMES` maps our PascalCase folders to the kebab-case names App Lab already gave them on the board (`ArduinoDisplay` → `arduino-display`, `BoardStatus` → `board-status`). Without it, deploying would create a duplicate app, and `board-status-autostart.service` runs `user:board-status` specifically. (2) If `adb` isn't on PATH, it uses App Lab's own copy at `~/Library/Arduino15/packages/arduino/tools/adb/<ver>/adb`. That's the same version as the adb server App Lab keeps running, so it doesn't restart it.
- The Advertise task runs from `venv/bin/python` (Homebrew's `python3` refuses system-wide pip installs); `zeroconf` (+ `ifaddr`) added to `requirements.txt`.
- `tools/board_secrets.py` (gitignored) has `HOSTS = ["10.5.13.215", "UNOQ2.local"]`, `BOARD_NAME = "UNOQ2"`.
- **Network finding:** on Tufts EECS the Mac (10.5.13.129) can't reach the board (10.5.13.215) at all, even on the same /21 subnet. ARP never resolves ("No route to host"), so the Wi-Fi isolates clients. **USB works:** with the board plugged in, `deploy.py` goes over adb and needs no network. Over Wi-Fi it needs a network that allows device-to-device traffic (home Wi-Fi, a phone hotspot).
- **Verified:** `deploy.py --cmd` over USB, and a full `deploy.py BoardStatus/...` (stop → copy → sketch flash → container start → logs). It restarted `board-status` in place with no duplicate folder. Before deploying, diffed both apps against the board's copies: code identical, only READMEs differed (ours newer).
- Also on the board, not in this repo: `mqtt-minifig-car` (based on Chris's MQTT Minifig Monitor, adds DC-motor drive) and `dlv` (empty template). Pull them into me193 before editing them via the kit.
- Board clock reads 2026-10-01 in the app logs, a week behind. Not investigated.

## Added Custom Robot Centering (YOLO minifig car) — 2026-10-11

- New `CustomRobotCentering/` folder: the `day5/` folder of Chris Liang's repo (`github.com/ChrisLiang33/mobile-robotics`, last commit `67adaab`) copied in without git history. The rest of that repo (day3/day4) was dropped. The repo folder was deleted, so pull fresh from GitHub to get any upstream changes.
- Laptop side: `track_minifig.py` runs the team's trained `models/minifig.pt` (YOLOv8n) on the webcam and publishes `{"x","y","w","h",...,"found"}` to `ME193/minifig/chris` on `test.mosquitto.org`. The UNO Q app (`unoq/mqtt-minifig-car/`, which is also on the board as `mqtt-minifig-car`) subscribes to that topic and drives. The topics must match: `MQTT_TOPIC` in `common.py` and in the board's `main.py`, or pass `--topic`.
- Has its **own** `.venv` (Python **3.11**, because the root venv is 3.14 and PyTorch wheels lag) + `requirements.txt` (pip freeze). Run with `CustomRobotCentering/.venv/bin/python track_minifig.py`. Verified: the model loads (class `green_minifig`), MPS available, broker reachable. Cameras: 0 = MacBook Air Camera (default), 1 = Sam's iPhone.
- Sam says the board is already programmed and the hardware works. Nothing was deployed from here. Its `unoq/unoq.sh deploy` script is Chris's own deployer; prefer `tools/deploy.py` (add a `BOARD_APP_NAMES` mapping to `mqtt-minifig-car` first) if it ever needs redeploying.

## Added Virtual ping-pong midterm — 2026-10-12

- New `PingPong/` folder for the midterm: ping-pong against a virtual wall with the **LEGO Double Motor as the paddle**. Sam considered the UNO Q too but chose LEGO as simpler; the comparison is in the README. Requirements as given: pose (paddle in the right place), IMU (is the player swinging), AprilTag for level/ball speed and game start, score on MQTT `ME193/Rogers/Sam` as a float = record continuous-hit streak, plus something new (haptics).
- Design:
  - MediaPipe wrist x → paddle x. It runs on the *un-mirrored* frame so MediaPipe's left/right is the person's own; x is mirrored afterwards.
  - Gyro magnitude swing detector: threshold = resting mean + k·std from a 2 s still calibration, with a floor of 50 raw units; rising-edge events with a 400 ms refractory period.
  - Hit = paddle under the ball **and** a swing in [−0.30, +0.15] s around the crossing.
  - Tags 1/2/3 = easy/medium/hard, tag 0 = pause.
  - Record is published on every hit and miss.
  - Haptics come from an off-center LEGO weight on the left motor output (`motor_run_for_time` pulses), plus `light_color` and `beep`.
- **`legoeducation` IMU notifications default to every 100 ms (10 Hz)**: `DEFAULT_DEVICE_NOTIFICATION_DELAY` in `basic_device.py`, min 15 ms. `LegoPaddle` connects with `device_notification_delay=20` instead of using `lelib`'s connect, which doesn't expose it. Useful for anything else reading the IMU (SillyWalks reads yaw at the default rate).
- Own `PingPong/venv` (Python 3.14; MediaPipe 0.10.35 does run on 3.14, as PoseRaceCar's venv shows) + `requirements.txt` (pip freeze). Pose model is copied from PoseRaceCar and auto-downloads if missing; `PingPong/models/` and `.pytest_cache/` are gitignored.
- Verified without hardware:
  - 17 pytest tests pass.
  - Headless smoke test: tag ID read after the hold time, MediaPipe loads, a frame renders, MQTT round trip of `"7.0"` on `ME193/Rogers/Sam/selftest`.
  - A scripted-bot run of the real `main()` loop (fake camera with tag 3, perfect-tracking pose, auto-swing) went through tag → calibrate → countdown → rally → hits/misses → re-serve.
- **Not yet run on the real Double Motor or webcam.** Sam was getting the hardware. Still to check: gyro units/rate and haptic feel (`check_paddle.py --haptics`), the threshold floor, `SWING_LATE`, and `MAX_SPEED` (2.2 court heights/s may be too fast for hard).
- Ideas discussed for extras: IMU-shaped shots (spin from gyro axis sign), AprilTag power-up cards, anticipation rumble, and two-player over the internet. For two-player, a friend opens a GitHub Pages link running MediaPipe in the browser; mqtt.js over wss to test.mosquitto.org; each side simulates its own half and hands the ball off at the net.

## Ping-pong: spin, approach rumble, card 0994 — 2026-10-12

- Card corrected: Sam's Double Motor card is **orange 0994**, now the default `--card-color/--card-serial` in `pong.py` and `check_paddle.py`. The "red 1129" in the earlier 9/28 log entry was a different team setup.
- Two-player-over-the-internet idea **scrapped** by Sam.
- **Spin**:
  - Each IMU sample now carries (gx, gy, gz).
  - `SwingDetector` records spin = twist-axis gyro / |ω| at the swing's peak, in −1..1 with no units.
  - `game.py` applies `vx += CURVE·spin·speed·dt`, with a 0.25 deadzone; the wall keeps half the spin.
  - The twist axis and sign depend on the mount. `check_paddle.py` step 2 has Sam twist right and prints `--twist-axis/--twist-sign`.
- **Haptics are now two layers**:
  - A light approach rumble (`tick` = 30 ms at 35%). It starts 1 s before arrival, every 0.40 s, speeding up to every 0.09 s. Ticks are dropped whenever anything else is queued or playing.
  - A stiff contact kick: 45 ms forward + 45 ms reverse at full power. The reversal makes it feel distinct from the buzz.
- `KeyboardPaddle`: z/x = swing twisting left/right.
- 23 tests pass. The headless bot run through `main()` showed spins ±0.8 reaching the ball, 39 rumble ticks, and kicks on hits. Still not run on real hardware.

## Ping-pong: tag cards, first connect attempt — 2026-10-12

- `PingPong/make_tags.py` writes `tags/tags.pdf`: 4 US Letter pages, 36h11 IDs 0–3, 14 cm, each labeled pause/easy/medium/hard. It also writes `tag0-3.png` for showing on a phone screen. Each page was checked: the game's own `TagReader` reads the right ID back at webcam scale.
- First `check_paddle.py` run failed 3×: `Could not find device matching Card color 9, Card serial 0994`. The Double Motor was flashing red.
  - A raw `bleak` scan saw 69 BLE devices but **zero** with LEGO's manufacturer ID 0x0397, so the Mac's Bluetooth works and the motor simply wasn't advertising.
  - No local process was holding it.
  - Likely cause: low battery (the red flashing), or it was still connected to another device. The card settings match SillyWalks/PoseRaceCar.
