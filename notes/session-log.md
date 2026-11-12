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

## Ping-pong: paddle connected, twist axis by PCA — 2026-10-12

- After charging, `check_paddle.py` connected (orange 0994), and steps 1–2 ran. The red flashing was the battery.
- The twist test showed the mount (buttons/charging port down, the module's top facing forward) puts the twist **diagonally** between gyro axes: right-twist peaks were y +325, x −249, z +111. A single-axis pick loses part of the twist, and a peak-based sign can flip because a twist-and-return hits both signs.
  - Replaced with `swing.find_twist_axis`: the principal component of the moving gyro samples, with its sign taken from the first strong movement (the right twist). Purity = share of motion on that axis; it warns below 75%.
  - `check_paddle.py` now saves steps 1–2 (IMU rate, rest/swing peaks, twist axis, purity) to `PingPong/paddle_calib.json`, which `pong.py` loads automatically. `--twist-axis/--twist-sign` still override it.
- The `Future exception was never retrieved ... Device disconnected unexpectedly` at exit was harmless. `disconnect()` fails any command still awaiting a reply, and `stop()` had just sent `light_color(blocking=False)`. `LegoPaddle.stop()` now joins the haptic thread and uses blocking calls before disconnecting. Step 3 only runs with `--haptics`, and the script now says when it's skipped.

## Ping-pong: spin is roll, not yaw — 2026-10-12

- Second calibration run: IMU at **32 Hz** (50 requested), |ω| resting peak 25 vs. swinging peak **567**, so swing detection has a ~20× margin. Sam had been "twisting" in yaw, which gave a twist axis of (+0.75, −0.66, −0.02) with 66% purity: yaw twist mixes with the arm's own yaw.
- Spin is now defined as **roll**: nose pointed at the screen, roll right = clockwise as seen by the player. A forehand swing is mostly yaw, so roll keeps spin independent of the swing. With the module's top facing forward, roll should show up mainly on gyro z. That's a sanity check for the next run.
- `check_paddle.py` runs haptics by default now. Use `--haptics-only` to run only the haptics, or `--skip-haptics` to run only steps 1–2. The prompts say "roll".

## Ping-pong: haptics too weak, haptic lab — 2026-10-12

- Third calibration run: roll axis (−0.95, +0.21, −0.21), purity **80%**. The roll is mostly on gyro x, not z as predicted, so the module's axes aren't where I assumed. It's fine, because the calibration measures the axis instead of assuming it. Resting peak was 243 this time (vs. 25 before), so the paddle probably moved during "hold still". `pong.py` recalibrates at every game start anyway.
- **Haptics were barely felt** (maybe one faint pulse in the whole demo). Likely causes, from reading the library:
  - `motor_run_for_time` is speed-regulated with an acceleration ramp, so 30–120 ms pulses barely move the motor.
  - In the contact "kick", the reverse command overrides the forward one almost immediately.
  - LEGO motors are geared down to a few turns per second, so an off-center weight can't spin fast enough to buzz like a phone's vibration motor.
- Added `PingPong/haptic_lab.py`. It tries raw `motor_set_duty_cycle` pulses (no ramp), out-and-back jolts, back-and-forth shakes, a light tick, and a 1.5 s spin, all with BRAKE end state. It measures the weight's actual rotation from `dm.motor[0].position`, asks Sam to rate each 0–3, and saves `haptic_lab.json`. Waiting on Sam's results before rewriting the haptics in `paddles.py`.

## Ping-pong: haptics rebuilt on raw duty cycle — 2026-10-12

- Sam's `haptic_lab.json`:

  | Variant | Swing | Rating | Note |
  |---|---|---|---|
  | A: old run_for_time 120 ms | 13° | 1 | |
  | B: duty 100% 150 ms | 144° | 2 | "half turn", clear |
  | C: 400 ms | 579° | 3 | "only useful for a start" |
  | E: "jolt" 150/150 | 298° | 2 | "solid but not too much" |
  | F/G: shakes | | 1 | wiggles |
  | H: 40% 60 ms | 17° | 1 | "very slight, I like it" |
  | I: 1.5 s spin | 2832° | 3 | about 5 rev/s at full speed |

- **Firmware behavior, measured from the motor's `power` field:** duty cycle ramps at ~100% per ~200 ms in both directions, and `motor_set_acceleration(100, 100)` doesn't change that. Commands take effect ~60 ms after sending. So "out then straight back" jolts can't reverse; the reverse just ramps power down. That's why D–G ended at their max position. Reversal itself works (tested at 40%).
- New haptics in `paddles.py`, using `motor_set_duty_cycle` + `motor_stop` with BRAKE end state:

  | Event | Pulse | Swing (mean of 5) |
  |---|---|---|
  | Tick (approach rumble) | 45% for 75 ms far → 100 ms near | ~17° → ~35° |
  | Contact | 100% for 200 ms | ~141° |
  | Sweet spot | 100% for 300 ms | ~300° |
  | Miss | 3 × 75% for 140 ms, alternating direction | |
  | Start | 400 ms | |

  The rumble floor is 0.17 s between ticks. Swing per pulse varies run to run (2–54° for ticks), depending on where the weight rests relative to gravity. Pulse length matters more than duty, because of the ramp.
- The shutdown warning came back with non-blocking duty commands (some replies never arrive). `LegoPaddle._cancel_unanswered()` cancels pending reply futures before `disconnect()`. It uses the library's private `_pending_responses`, best-effort only.

## Ping-pong: start/end wobble — 2026-10-12

- Sam's feel check: the approach rumble builds nicely, and hit vs. sweet spot are "just different enough". But the start pulse felt too much like hit/sweet.
- Start and end are now the same **big wobble**: 4 × 100% duty for 260 ms, alternating direction, 110 ms gaps. On hardware it swings the weight across ~340–440° with 4 direction changes, about 3× the miss wobble's range (~145°). Start adds a rising beep + green light; end adds a triple beep + light off.
- The game had no real "end" (a miss just re-serves), so **end** = quitting (`q`/Esc/Ctrl-C) or switching level mid-game. `LegoPaddle.stop()` now waits up to 3 s for queued haptics to finish, so the end wobble plays before disconnecting. A lives/game-over mode is an option if Sam wants a real end.

## Ping-pong: UI redesign, 60 fps, sweet-spot streak — 2026-10-12

- First real game went well. The haptics were good.
- Sam asked for a smoother, more modern UI that's "sleek and effective", not generic vibe-coded, keeping every existing element. Sam also asked for a sweet-spot streak counter.
- **Sweet-spot streak**: `Game.sweet_streak` / `sweet_record`. It counts consecutive sweet-spot hits; a non-sweet hit, a miss, or a level change resets it. Tested.
- **Smoothness**:
  - New `vision.VisionWorker` runs camera + MediaPipe + tags on a background thread.
  - `pong.py` draws at 60 fps and eases the paddle toward each pose reading (time constant 45 ms). The eased position is also what the hit rule uses, so what you see is what counts. Pose EMA was loosened from 0.6 to 0.75 to make up for the extra easing.
  - The bot run through the real `main()` measured ~52 fps average, including startup.
- **New `ui.py`** (all drawing moved out of `pong.py`):
  - Look: broadcast sports graphics. Ink #0A0C0F background, competition-blue table gradient + vignette, white lines.
  - One accent, ball orange #FF8A3D, for the ball and the best score. Azure #3FC5F0 for sweet-spot things (matches the paddle's light). Red only for misses.
  - Type: **OpenCV 5's `cv2.FontFace` loads `/System/Library/Fonts/SFNS.ttf` (a variable font, weights 100–1000)**. Hershey is the fallback if it's missing.
  - Elements:
    - Tracked uppercase labels; numbers pop when they go up.
    - Ball: shadow + highlight. The trail fades into the table.
    - Paddle: ivory capsule with an azure sweet-spot band and a crisp outline flash on a swing.
    - An expanding ring at contact; toasts that drift up and fade; the hit line flashes red on a miss.
    - Camera card: rounded, with a pose status chip, tag outlines + labels, and a hold-progress bar.
    - Stats card: streak/best, sweet-spot streak + best, level pill, speed and spin meters, Paddle/IMU/MQTT status dots.
    - Keycap footer.
    - Modal cards over a blurred table. The start screen's level chip fills while that tag is held; calibration and countdown have progress rings.
  - The static layer is cached, so rally frames take ~4.4 ms and overlay frames ~5.5 ms. Re-masking the overlay blur was restricted to the 4 rounded corners after it took 11.6 ms over the whole table.

## Added Sumo wrestling (HW5) — 2026-10-19

- New `SumoWrestling/` folder: Mohammed Almheiri's `Mohammed's Projects/Sumo Wrestling/` from `github.com/mohdalmheiri/ME193-Robotics` (commit `57946e0`, 2026-10-18), copied in without git history. The code is unchanged. To pick up upstream changes, re-copy from GitHub.
- What it does: a human drives with the LEGO Controller. A behavior tree on the laptop (`behavior_tree.py`, run by `sumo.py` at 20 Hz) checks OUT → NO_EDGE → EDGE_PUSH → EDGE → BOOST → DRIVE.
  - The Color Sensor's hue/saturation detects the blue tape and blocks forward.
  - An HC-SR04 on the UNO Q publishes distance to `ME193/Mohammed/sumo/distance`, and an opponent within 30 cm while charging gives full power.
  - Enter in the terminal = "out" (sad trombone).
  - LEGO parts pair with the orange 0994 card, the same as PingPong.
- MQTT topics were left as `ME193/Mohammed/...` because the board app and `sumo.py` must match. Change `DISTANCE_TOPIC` in `sumo.py` and `TOPIC` in the board's `main.py` together if needed.
- Own `SumoWrestling/venv` (Python 3.14) + the upstream `requirements.txt`, because it pins `legoeducation==1.2.0` ("works with our controller") and the root venv has 1.1.1. Verified: `test_behavior_tree.py` passes (19 checks), `sumo`/`sad_song` import, and the trombone WAV generates. No hardware was tested. Don't import `watch_distance.py` to test it, because it runs `loop_forever()` at import.
- UNO Q app moved from upstream `unoq_app/` to `SumoWrestling/unoq/sumo-distance/`, the folder App Lab makes for "Sumo Distance".
- `tools/deploy.py` used to take the first path component as the app, so nested apps couldn't deploy. It now walks up from the given path to the nearest folder with an `app.yaml` (within the repo) and uses that folder's name. Root-level apps behave as before. Also fixes `CustomRobotCentering/unoq/mqtt-minifig-car`, which now deploys directly as `mqtt-minifig-car`.
- Not deployed: the board wasn't reachable (no adb; no answer at the `HOSTS` addresses), so it's unknown whether a sumo app is already on it and under what name. List `/home/arduino/ArduinoApps` before the first deploy, and add a `BOARD_APP_NAMES` mapping if it's not `sumo-distance`.

## Sumo wrestling: synced upstream tape threshold — 2026-10-19

- After Sam's successful test run, pulled Mohammed's `b3b2dd9` ("Lower tape saturation threshold for new ring tape"). The new ring tape reads hue ~208, saturation ~52–56, so `TAPE_MIN_SATURATION` in `sumo.py` dropped from 55 to 45. The floor reads saturation ~29–41 and fails the hue check by a wide margin anyway. The README's measured-tape table was updated to match.
- To sync again: re-clone `mohdalmheiri/ME193-Robotics`, diff `Mohammed's Projects/Sumo Wrestling/` against `SumoWrestling/` (its `unoq_app/` is our `unoq/sumo-distance/`), copy code files over, and patch README hunks so this repo's adaptations stay.

## Activity wearable: plan + IMU bench check — 2026-10-26

- New assignment: a UNO Q wearable that tells standing still, walking, running and air-biking apart, with two models. Model 1 uses only the peak acceleration on one axis; Model 2 uses all the IMU outputs. No neural nets. Three classmates each try one activity live. The full plan (rubric, models, data plan, assembly steps) is in the Obsidian note `me193; ActivityWearable`. Sam handles the Notion page and the reflections.
- Decisions:
  - The "5060" is an MPU-6050 on a GY-521.
  - Placement: board + IMU together in Sam's 3D-printed case, in a sock-sleeve pocket on the front of the lower shin, powered by a power bank over USB-C.
  - Orientation: USB-C up, GY-521 components out with its Y arrow toward the knee. That gives +Y up the shin, +Z forward and +X to the wearer's left.
  - Models: decision trees, with KNN as a comparison. Both run live side by side; Model 2 is the official identifier.
  - Testing leaves one person out, since the demo is on people the model hasn't seen.
- Wiring: GY-521 VCC→3.3V, GND→GND, SDA→SDA, SCL→SCL (header pins by AREF), with male-to-female jumpers. XDA/XCL/AD0/INT are not connected.
- New `ActivityWearable/unoq/imu-check/` App Lab app. The sketch scans `Wire`/`Wire1`/`Wire2` and configures the MPU-6050 (±16 g, ±2000 °/s, DLPF ~44 Hz, 100 Hz). Python prints readings at 5 Hz plus which axis is up.
  - The scan probes each address with a 1-byte `requestFrom`, because this core's `endTransmission()` does a zero-length `i2c_write`, which STM32 I2C can reject.
  - The Bridge calls are `provide_safe`, so they run from `__loopHook` on the loop thread. An empty `loop()` is fine.
  - Per the variant overlay, `Wire`=i2c2, `Wire1`=i2c4, `Wire2`=i2c3.
- First run:
  - `Wire: 0x68`, nothing on Wire1/Wire2, so **the header SDA/SCL pins are `Wire`**.
  - WHO_AM_I is 0x68, and ACCEL_CONFIG reads back 0x18.
  - At rest, |a| = 0.99 g; the gyro bias is 1–3 °/s.
  - **The Bridge round trip is about 9.5 ms per call (~106/s)**, so the logger should sample on the STM32 and send batches, not one call per sample.
- The board rebooted once mid-session: Sam was clipping the GY-521's header leads, and a lead probably shorted something. It was fine after.
- The board's Wi-Fi IP is now 172.16.9.166 (added to `HOSTS` in `tools/board_secrets.py`). Deploying `imu-check` stops BoardStatus until the next reboot.

## Activity wearable: recording app + guided recorder — 2026-10-26

- Sam assembled the wearable: the GY-521 is hot-glued to the UNO Q's 3D-printed case, in a sock-sleeve pocket, on the **right** leg every time. Decided: lying still on your back counts as "still"; walking and running get recorded in a hallway; the app gets started over Wi-Fi each time (no autostart).
- New board app `ActivityWearable/unoq/activity-wearable/`:
  - **Sketch:** samples at 100 Hz on its own clock (`micros()` schedule; when it falls far behind it skips ticks rather than bursting) into a 128-sample ring. `imu_batch()` returns at most 7 samples as hex: **the Bridge's RPC buffer is 256 bytes** (`DECODER_BUFFER_SIZE / 4` in RPClite 0.3.1). It also draws frames on the LED matrix.
  - **Python:** saves each session to `/app/data` (the app folder), times the countdown and the recording itself, and talks MQTT (`ME193/Sam/wear/{cmd,status,event,imu}`).
- Laptop side:
  - `common.py`: the 11-step protocol, about 5.5 min of recording per person.
  - `record.py`: a guided terminal UI (no sound; Sam asked for no voice) with on-screen cues, an orientation check, a big countdown, rough quality checks, and redo. It keeps `data/live/` copies and `data/session_log.csv`.
  - `pull_data.py`: copies sessions off the board using `tools/deploy.py`'s transport.
- Network findings:
  - **The board's MAC is now `14:b5:cd:f7:fd:9b`.** The `B6:28:D9:3E:A7:E6` in Sam's notes is a locally-administered (randomized) address. Tufts_Wireless redirected everything to device registration until Sam registered the new MAC. After that the board got 10.243.82.39 (added to `HOSTS`), and SSH works from the laptop on Tufts Secure.
  - **`test.mosquitto.org:1883` is unreachable from both Tufts networks**, so the project uses `broker.hivemq.com`.
  - The board's clock is unsynced (it reads 2026-10-01), so the laptop sends `laptop_time` for each file's header.
- `tools/deploy.py`: `UNOQ_HOST=<ip>` is tried before `HOSTS`, because the board's Wi-Fi IP changes.
- **BoardStatus IP display was stale** (it showed 10.5.13.215). The cron job had been failing with "Permission denied", because `update_ip.sh` had lost its execute bit; the repo had it as 100644, and deploys copy that. Fixed with `chmod +x` on the board, and the three BoardStatus scripts are now 100755 in git. A crontab change to `/bin/sh update_ip.sh` was blocked as persistence, and is no longer needed if the mode bit sticks.
- End-to-end test over USB + MQTT: a 5 s session saved 500/500 rows with 0 gaps and 0 drops, the live copy arrived, and `pull_data.py` copied it. The 381 startup drops are from before Python starts draining; they're counted per session, so they don't matter. The test file was deleted afterwards.
- Follow-ups the same evening:
  - **Pinned the board's MAC:** `nmcli con modify Tufts_Wireless 802-11-wireless.cloned-mac-address 14:B5:CD:F7:FD:9B`, at Sam's request, so it can't use up another registration.
  - **Removed the voice prompts** from `record.py`; cues are on screen only.
  - **UI test:** drove the real UI through a pseudo-terminal (fit → orientation → a 10 s calibration). It saved 1000/1000 samples with 0 gaps, and the orientation check correctly flagged the board lying flat. Test files deleted.

## Activity wearable: 3 people recorded, both models trained — 2026-10-26

- **Data:** SL, TEOROM and MAYA each did the full protocol; every kept session has all its samples and no gaps.
  - The fast runs failed record.py's rough check only because it compared the combined |a| (up to 19.7 g) with the ±16 g per-axis limit. No single axis went past 14.3 g, so nothing clipped. That check has been removed.
  - Earlier fix: the walking check no longer caps the peak. Tall walkers hit 7–9 g.
- **New files:**
  - `unoq/activity-wearable/python/features.py`: 2 s windows every 0.5 s, plus 31 features for Model 2 and `peak()` for Model 1. It's numpy only and imported by both train.py and the board.
  - `classify.py`: runs the exported trees, forest and KNN.
  - `ActivityWearable/train.py`: leave-one-person-out evaluation, figures, and `models.json` (0.6 MB). Its runner matches scikit-learn 100%.
- scikit-learn 1.9.1 (+ joblib, threadpoolctl) added to the root venv and `requirements.txt`.
- **Results (held out):**
  - **Model 1: +Y peak, 80%.** Thresholds 1.20 / 1.71 / 3.69 g separate still / bike / walk / run. A `max_leaf_nodes=4` tree beats depth 2 (74%), and +Y beats every other direction; Z, the original guess, got 61%.
  - **Model 2: forest 99.3%, KNN 97.5%, tree 95.3%.**
  - Model 1's weakness is **bike**: only 33% right, with 44% called still, because the +Y peak during air-biking overlaps standing at about 1 g.
  - Model 2's tree uses gyro_x_std, then acc_y_mean (lying down), then acc_z_mean (forward lean when running).
  - k-means: still and bike come out as clean groups; walking and easy jogging land in one group, fast running in another.
- **Not committed yet:** the person IDs include "MAYA", which looks like a first name rather than initials, so I'm asking Sam before pushing the data to GitHub.

## Activity wearable: live mode + dashboard — 2026-10-26

- Sam said keep the person IDs as they are and push everything; pushed `a59821a`, with the data, train.py and figures.
- **Board `main.py`, `Live` class:**
  - Keeps a 200-sample window; every 50 new samples it runs `classify.Models` (Model 1 + Model 2, default forest) and publishes `ME193/Sam/wear/live`.
  - Each answer is the most common of the last 3. It also publishes the +Y peak, thresholds, forest probabilities, cadence, acc_y_mean and gyro_x_std.
  - A gap in `seq` restarts the window.
  - The LED matrix shows `<M1><M2>` letters.
  - New command `{"cmd": "model2", "kind": "tree"|"forest"|"knn"}`.
  - Tested by replaying sessions through `Live` with board-only parts stubbed out (0.6 ms per answer on the laptop), then on the board: an answer every ~0.5 s, and switching works.
- **`ActivityWearable/dashboard.html`:** one page using mqtt.js 5.10.1 from jsDelivr and `wss://broker.hivemq.com:8884/mqtt`.
  - Two model cards (a gauge for Model 1, vote bars + posture/swing/cadence for Model 2), an agree/disagree banner, a 60 s timeline and the +Y signal.
  - Palette: the dataviz skill's reference slots 1–4. Node isn't installed, so the validator wasn't run; that palette is pre-validated, and every class is also named in text.
  - Checked with headless Chrome over the DevTools protocol (a throwaway venv with websocket-client in the scratchpad): live data, `?demo`, light and dark, and 390 px wide with no horizontal scroll.
  - Chrome's `--timeout` screenshots don't wait in real time, so they never showed live data.
  - Launching Chrome from VS Code's terminal set off a macOS "prevented from modifying apps" prompt (Chrome trying to update itself). It's harmless.
- Sam asked for Model 2 to be definitive, so the dashboard's Tree/Forest/KNN selector is gone. The cards now read "Model 1 · decision tree" and "Model 2 · random forest". The board still accepts the `model2` command, but nothing sends it.

## Activity wearable: "goes offline after a while" fixed — 2026-10-26

- Symptom: the dashboard went offline after a while, and Sam rebooted to recover. When it happened, the matrix still showed changing letters, so the app was alive and the network path was what had broken.
- Findings:
  - **Wi-Fi drops:** wlan0 disconnected for about 2 s (one per boot in journalctl), and the board switches APs as Sam walks the hall (3 AP BSSIDs in the kernel log). The app kept an ESTABLISHED socket to HiveMQ with data queued, while nothing arrived at the laptop.
  - **Slow broker:** HiveMQ itself stalled CONNACK for 5–9 s on 3 of 8 connects, from both the laptop and the board.
  - **Corrupt log:** the Docker log file had null bytes from earlier power pulls, so `docker logs` failed.
- Fixes in `main.py`:
  - `mqtt_watchdog`: the board subscribes to `.../status` and checks that its own `board` id echoes back. After 8 s without an echo it reconnects (disconnect, `loop_stop`, `connect_async`, `loop_start`).
  - keepalive 30 → 15 s; `reconnect_delay_set(1, 5)`.
  - `.../imu` sends every 4th sample when not recording (25 Hz). `record.py`'s `recent()` and the dashboard's signal chart now go by `seq` instead of counting samples.
- **Broker switched to `broker.emqx.io`** in `main.py`, `common.py` and `dashboard.html` (`wss://broker.emqx.io:8084/mqtt`). It connected in about 0.4 s on 8/8 from both sides.
- Removed the container (`docker rm activity-wearable-main-1`) so the log is fresh; logs are readable again.
- Verified:
  - Watchdog: tested on the laptop with stubbed hardware on topic `ME193/Sam/weartest`; it reconnects about 8 s after messages are cut off, then echo resumes.
  - Board on EMQX: live answers twice a second, sensor samples at 25 Hz when idle.
  - Dashboard: live at 101 Hz via headless Chrome.
  - `record.py`: connects, and its orientation check works on the 25 Hz idle data.

## Activity wearable: "How far" distance per activity stretch — 2026-10-27

- Sam asked for an estimate of how far each activity went, with its limits shown.
- **Stride counter on the board** (`Live.add`): counts −gx swing peaks: enter 120 °/s, re-arm below 40 °/s, at least 0.55 s apart.
  - Tuned on all 27 sessions against each session's spectral stride rate: median error about 3%, 0 strides on still sessions.
  - Raising the gap from 0.45 to 0.55 s fixed double counts on fast runs.
  - −gx was chosen because its peaks come about once per stride (+gx gives about two per walking stride).
- **Bouts** (`update_bout`): a new Model 2 answer must hold for 2 answers before a new bout starts. `.../live` carries `bout`, `strides_total` and `recent_bouts` (6); `.../bout` gets each bout as it ends.
  - Replaying TEOROM stand → walk → run → lie → bike: 5 bouts, lengths within about 2 s of the sessions.
- **Dashboard "How far" panel** (moved into the bottom row, beside the timeline + signal):
  - Distance = strides × stride length, shown as a range. The rules of thumb: 0.74–0.90 × height walking, 1.0–1.6 × running. With no height, 155–195 cm is assumed. Plus ±5% counting.
  - Height input (parses 6'5 / 196 / 1.96 m / 5ft 8in). Walk/run calibration over a measured distance gives ±8%. Both are saved in localStorage.
  - Bike shows pedal turns; still shows its duration.
  - Tested in headless Chrome: parsing, ranges, and calibration (18 strides over 30 m → 1.67 m stride).
- **Sources:** a web search found only weak support for a fixed step/height ratio. Scientific American says pedometers use the height link; a treadmill study found step length related to height (R² about 0.4). So the ratios are labelled as rough heuristics in the UI and README.
- Deployed. The board's live messages carry the bout fields.

## Activity wearable: models overview figure — 2026-10-28

- For the Notion page's "graphical representation of the models": `ActivityWearable/figure_models.py` draws `figures/models_overview.png`.
  - Left: Model 1's learned tree as it really is (≤3.69 → ≤1.71 → ≤1.20 g, giving run / walk / bike / still).
  - Right: Model 2's forest, showing 3 real trees' first questions in plain English (all of them send "yes" to still), "… 97 more", the vote, and an example vote that's labelled as an example.
  - Both cards carry the held-out accuracy (80% / 99%).
  - Everything shown is read from `models.json` and `results.json`, so re-run the script after `train.py`.

## Wall stop loss regression — 2026-10-29

- Class handout "Solving things by minimizing a loss or error": fit `speed = m·reflection + b` by gradient descent, in Excel first and then Python.
- New folder `wallstop_lossregression/`:
  - `annacode-data.csv`: Sam's logged run from Anna's site (time, reflection, speed; 5 approaches).
  - The fit uses the 120 rows with reflection > 0 and speed ≠ 0, i.e. the robot sees the wall and is still slowing.
  - `build_workbook.py` → `gradient_descent.xlsx`: example tabs (handout's y = 2x data, raw and centered) plus wall tabs (raw and standardized), one formula row per epoch, with SLOPE/INTERCEPT check cells.
  - `wall_fit.py`: the same thing in numpy.
- Result: speed ≈ 0.153·reflection − 17.6 (MSE 8.7), matching `np.polyfit`.
- Raw x blows up at lr 0.0005 because reflection spans 6–96. Centering alone isn't enough (lr must be < ~0.0017). Standardizing (÷ std, like Anna's code) converges in about 20 epochs at lr 0.5.
- The handout's centered-intercept fix `mean(x) + b` should be `b − m·mean(x)`; the README notes this.
- Bug fixed along the way: renaming openpyxl sheets *after* adding charts leaves the charts pointing at `'Sheet'`, which Excel then reports as a broken external link (blank chart + "UNABLE TO REFRESH"). Set sheet titles before building charts.
- Added `openpyxl` (+ `et-xmlfile`) to the root requirements.

## One-neuron ReLU loss regression — 2026-10-29

- Handout part 2 ("what if I have an activation layer?"): Sam was asked for a loss regression with one neuron and one activation layer, in PyTorch, plus an Excel version. Sam specified **ReLU** (the activation the class uses).
- New folder `relu_lossregression/`:
  - `annacode-v.tsv`: example data from Anna's site, a V ≈ |2x − 120| + noise.
  - `one_neuron.py`: PyTorch `Linear(1,1)` → `ReLU`, `MSELoss`, SGD lr 0.1, 50 epochs, start m = b = 1, float64. Saves `one_neuron_fit.png`.
  - `build_workbook.py` → `one_neuron_relu.xlsx`: a Training tab with one row per epoch, and an "Epoch 0 by hand" tab with the per-point chain rule.
  - The workbook uses MSELoss's 2/N factor so its rows equal PyTorch's.
- Checked: the formula math, evaluated in numpy, equals PyTorch's m, b, dm, db and loss at epochs 0, 1, 2 and 50. LibreOffice isn't installed, so the workbook itself wasn't recalculated here.
- Result: y = ReLU(−0.0332x + 41.12), loss 567. The ReLU ends "on" for all 120 points, which is the same as a plain line. One ReLU can't bend both ways, so it can't fit the V.
  - In earlier testing, an abs activation got loss 3.7 (y = |2.008x − 120.4|).
  - Two ReLU neurons (ReLU(z) + ReLU(−z)) would fit the V. Not built yet; offered to Sam.
- torch isn't in the root venv. The script runs with `CustomRobotCentering/.venv` (torch 2.14.1).

## Activity wearable: neural-net step counter — 2026-11-02

- Week 2 assignment: "extend your walker to now count your steps using a neural net and PyTorch. Use every sensor you can to make it as accurate as possible."
- Sam's decisions:
  - No second MPU is available (the lab drawer has an MSA311 accelerometer only), so the second sensor is an **iPhone in the left front pocket**.
  - Ground truth is **tap mode**, not video.
  - Train in PyTorch, run on the board in numpy.
  - Keep the activity classifier.
  - **Remove the old stride counter**, keeping a copy in `train_steps.py` only to compare against.
- New files:
  - `ActivityWearable/phone/index.html`: streams DeviceMotion over MQTT to `ME193/Sam/wear/phone`.
  - `python/steps.py`: inputs, the numpy forward pass, and the live `StepCounter`, shared by the board and training.
  - `train_steps.py`: PyTorch training, leave-one-person-out comparison, figures, `steps_model.json`.
- The phone page is served by GitHub Pages from `main` (root). A `.nojekyll` file at the repo root stops Jekyll from processing the repo.
- `main.py` changes:
  - Phone samples go onto the seq clock using the smallest (arrival − phone time) over the last 20 s.
  - Each session also writes `<session>_phone.csv`.
  - The `saved` event carries `first_seq`.
  - Stride code is gone; `steps_total`, `step_rate_spm`, `step_net` and `phone` are added to `.../live`, and `phone` to `.../status`.
- `record.py` changes:
  - `--protocol steps` is now the default; `activity` gives week 1's protocol.
  - Tap mode: f = left foot, j = right foot, space = either.
  - Taps are saved to `data/<session>_taps.csv` on the board's clock (from the arrival times of the live samples).
  - The header shows the phone, and a phone-check step was added.
- `common.STEP_PROTOCOL`: calib, walk, walk 30 counted steps, turns, stop-start, fidget, stairs, jog, run, air-bike. Sessions that mix activities are labelled "mixed", and `train.py` now skips them.
- Dashboard: How far uses steps × step length (0.37–0.45 × height walking, 0.5–0.8 running) plus the net's held-out error. It no longer shows pedal turns, and the header shows the phone.
- torch 2.14.1 (and its dependencies) added to the root venv and `requirements.txt`.
- Tested with no real tap data:
  - Synthetic pipeline (scratch only): numpy vs torch differed by at most 5e-10, and the live counter equals the offline count.
  - Real week-1 bike sessions: the old rule counts about 115 steps/min.
  - Board `main.py` simulated with a fake Bridge and MQTT: 76 steps vs 79 taps, and 898/900 phone samples in the session file.
  - Headless screenshots of the phone page (390 px) and the dashboard demo.
- **Not yet:**
  - deploying to the board (it wasn't reachable: no adb, no answer at any host)
  - the phone page on a real iPhone
  - recordings, and a trained `steps_model.json`

## Activity wearable: recording over patchy Wi-Fi — 2026-11-02

- First real tap-mode run (Sam): sessions stuck on GO, a stop that never came back, sessions that didn't start, and "offline" mid-walk.
- What the board logs showed:
  - Two sessions were aborted at about 400 rows: `record.py` never got the "recording" event and sent stop after 4 s.
  - Sessions the board saved never reached the laptop's log.
  - One walk lost 1757 samples. The watchdog's `loop_stop()` ran on the main loop and waited on paho's stuck connect.
- Fixes:
  - `main.py`: reconnects run in a thread with backoff; QoS 1 for cmd and event; repeated record commands are ignored (the last 20 names are remembered); `first_seq` is written on the `# end` line.
  - `record.py`: resends the command until the board's status shows it; takes the start from the status's `remaining` or the event; no auto-abort; an "unconfirmed" screen keeps the session and its taps, which are saved as seq when `first_seq` is unknown.
  - `train_steps.py` reads seq-only tap files using the CSV's `first_seq`, and skips a session if it can't.
  - The offline hint no longer mentions a phone hotspot (Sam isn't using one).
- Tested: a fake-board harness (normal, lost first command, lost events), and the board simulation with a duplicate command and a `loop_stop()` that hangs 5 s (0 drops).
- Deployed. The first Wi-Fi deploy left the sketch unresponsive (Bridge `imu_status` timeouts); a second deploy reflashed it and it's fine (100 Hz, IMU found).

## Activity wearable: checking the taps' sync — 2026-11-02

- Checked Sam's kept walk (`SL_walk_normal_20261102-182117`): 59 taps vs 29–31 right-shin strides, alternating feet 100%, gaps 0.61–0.81 s. The right-foot taps sit -138 ms from the right heel strikes (|a| peaks over 2 g), IQR 57 ms. Good data.
- The discarded walk (`182248`) had an offset of -7 ms. So the laptop's board-clock estimate shifts by about 0.1 s between sessions.
- `train_steps.py` now shifts each session's taps so the right-foot taps sit on the right heel strikes (median, if at least 6 match within 250 ms). The left-foot taps move with them. The shift is reported as `tap_shift_ms`.
- `record.py`'s results screen now shows the same check: % of right taps matched, the offset, and the spread. It flags a spread over 120 ms or under 70% matched.
- The board survived a Wi-Fi drop mid-session with the fixes: 4000/4000 rows, 0 drops.

## Activity wearable: no more waiting at the end of a session — 2026-11-02

- `record.py` sometimes sat 10 s past a session's end (25 s after an x abort). The live samples kept arriving, but the single saved/aborted event was lost. The laptop walks too, so its Wi-Fi blips, and a QoS 1 message published while a clean-session subscriber is away is gone.
- Fix: the board repeats its last result (`last`) in every status message (twice a second), and `record.py` takes it from there. The unconfirmed wait is cut from 10 s to 6 s.
- Tested with the fake board: events lost, status has the result → done in 4.5 s (was 14 s). Deployed (board idle first).

## Activity wearable: step net trained on 6 people, training timelapse — 2026-11-03

- Data: BANJO (two sittings, sleeve refit in between) and DHRUV added, on top of SL, RUBYA and MAYA (TEOROM: zero-step sessions only). 70 sessions, 37 tapped, 2110 taps. RUBYA's `run_fast` is empty (a wire broke) and is skipped.
- `train_steps.py`, two corrections:
  - Compare on the same span: the net's output starts 1.1 s into a recording and stops 1.1 s before its end, so 110 of the 2110 taps were out of its reach. Taps, the old rule and F1 now use only the span it can count (`seen()`, `taps_seen`). Live, the stream has no edges.
  - Threshold from held-out output: tuned on each fold's own training people it came out 0.60 everywhere and missed steps on new people (DHRUV 308 vs 375). Now each fold's threshold is picked on the other folds' held-out output, and the board's net uses the best over all of them (0.50). Fold thresholds are in `steps_results.json`.
- Results, held out: net + phone median error 2.0% per session (shin only 2.9%, last week's rule 2.6%); air-biking 0.35 false steps/min vs the rule's 106. All tapped sessions: 2006 steps vs 2000 taps (rule 2010). Worst: DHRUV −8.5%, and BANJO's shuffling stop-start walk.
- Checked BANJO for wiring faults (Sam had re-fixed wires): 0 gaps, 0 drops, no zeroed or saturated rows, repeated-row rate like everyone else's. Not the wires; BANJO's stop-start steps are small and slow, unlike anyone in training.
- New `timelapse_steps.py` + `timelapse.html`: one fold (BANJO held out) re-trained identically and snapshotted 283 times; the page plays back the net's output on 4 recordings, both losses and the step counts. Last frame = BANJO's line in `train_steps.py`. `train()` takes a `snapshot` callback for it.
- Deployed the final net over USB (board on XFSsetup9084 at 10.0.0.32, which VS Code couldn't reach: macOS blocks its local-network access). The app runs, but the board reports `IMU: not found` (wiring, after collection was done).
- This file had been cut down to its last entry on 2026-11-02 (a write that replaced it instead of appending). Rebuilt from the last commit plus one uncommitted entry, recovered from the session transcript.

## Activity wearable: Notion write-up draft, loss-bowl explainer — 2026-11-03

- First draft of the week 2 Notion page, now in Sam's Obsidian vault (`notion draft.md`; deleted from the repo, never committed) (intro, links, demo shot list, the three-paragraph net explanation, uncertainty analysis, distance and its limits, training timelapse). Placeholders marked **TODO (Sam)** for the video, the live check, the distance test, the reflection answers and Sam's own wording.
- New in the uncertainty analysis, from `figures/steps_results.json`: 9 in 10 held-out sessions are within 13.5% for the net + phone (8.8% for last week's rule). The tail comes from DHRUV's runs and MAYA's stop-start/turning walks.
- Fixed the README's timelapse finding: BANJO's held-out loss is lowest at update 110, not 250.
- A loss-bowl explainer for Anna's gradient-descent page (3D bowl, top view, the two slices, stability limit), published as a claude.ai artifact.

## Activity wearable: how sure the step net is, on the dashboard — 2026-11-03

- `steps.py` `StepCounter` now also reports each new step's peak probability (`last_peaks`) and the peaks just under the threshold it didn't count (`last_near`). The steps themselves are unchanged: `check_live_matches_offline` still passes.
- `main.py` counts unsure steps (peak under threshold + 0.2) and near misses per bout, and publishes `step_peak_recent` and `step_threshold` in `.../live`. `dashboard.html` shows them under How far for walk/run: a clear/unsure/near-miss bar and "likely N–M steps", plus the held-out median and 90th-percentile error.
- `train_steps.py` saves the 90th-percentile error (`p90_abs_err_pct`, `count_err_p90_pct`); added to the existing `steps_results.json` and `steps_model.json` without retraining (13.5%).
- Needs a redeploy of the board app to show up live.

## Fitting the V in Anna's code (relu_lossregression rework) — 2026-11-08

- Assignment, as Sam received it: fit a model to the V data in Anna's code; include the gradient-descent math for a single neuron + ReLU, an Excel sheet with 5 iterations on m & b, and Python with a data + fit plot and a loss vs epoch plot.
- Read Anna's source (`chrisbuerginrogers/ME193-Robotics`, `Public stuff/AnnaCode`) to work out what's wanted:
  - V example (`network/training.py` `EXAMPLES["v"]`): 120 points, x uniform 20–100, `2·|x − 60|` + N(0, 2) noise.
  - The site's hint: hidden layer of ≥2 ReLU neurons, output activation None.
  - The Fitting tab is for setting weights by hand. Its Train buttons still work, and it hides the output layer's activation.
  - Training details: x standardized; y standardized unless the last layer has an activation; MSE with 2·err; averaged gradients clipped to ±5; default lr 0.05; Randomize gives uniform(−1,1)/√fan_in weights and zero bias.
- Interpretation: the hand fit and the trained fit happen on the site (2 ReLU neurons: (2, −120) and (−2, 120), output weights 1, 1, bias 0 gives exactly 2|x − 60|). The math and the Excel cover the single-neuron building block, y = ReLU(m·x̂ + b).
- `relu_lossregression/` reworked:
  - README is now the write-up: site steps, LaTeX math, the 5-iteration table, results.
  - `build_workbook.py` → `v_fit_5_iterations.xlsx`: Iterations tab (rows 0–5 plus charts) and a Per point tab (pre, ReLU, ReLU′, error, chain-rule terms per point per iteration).
  - `v_fit.py` (numpy, hand-written gradients): part 1 is one neuron (matches the Excel); part 2 is 2 ReLU neurons + linear output with random restarts. Saves `v_fit.png`.
  - Removed `one_neuron_relu.xlsx` / `one_neuron_fit.png`. `one_neuron.py` (PyTorch) is kept as a cross-check.
- Verified: the workbook was evaluated with the `formulas` package (in a scratch venv; LibreOffice isn't installed). 0 errors across 5,561 cells, and rows 0–5 equal `v_fit.py`.
- Findings:
  - A single ReLU neuron converges to the flat line (loss 567, on for all points) from every start tried.
  - 2 ReLU neurons reach loss 3.6 (noise floor ~4), but only 6/30 random starts get there. 3 neurons: 15/30, 4: 25/30, 6: 28/30. That's why the site says to randomize and retrain.
- Not committed or pushed yet.

## Notion write-up for the V fit — 2026-11-08

- `relu_lossregression/v_fit.py` now saves two images, `v_fit.png` (data + fits) and `v_loss.png` (loss vs epoch), to match the assignment's "a plot of the data and the fit and one of the loss". README updated.
- Drafted the Notion page for Sam. It lives in Sam's Obsidian vault, not this repo (a `notion_page.md` here was deleted at Sam's request). The draft leaves out the hand-set weights and anything learned only from reading Anna's source code.
- Rebuilt `v_fit_5_iterations.xlsx` to look like a classmate's: a small **Summary** tab (inputs, iterations 1–5 plus "after 5", points with ReLU off, 2 charts) and one tab per iteration (Iteration 1–5, 120 rows × 10 columns, averages on top). The old version was one 45-column "Per point" sheet plus a block of explanation text and a raw-units conversion. The numbers are unchanged, the `formulas` package found 0 errors, and the README, `v_fit.py` and `one_neuron.py` now use the 1–5 / "after 5" numbering.

## Infallible Safe (Midterm 2): the night-before build — 2026-11-08

- Brief (pasted by Sam): PyTorch net built from scratch that returns the number of fingers in the camera image, for a lock; Notion page (video, GitHub, intro, explanations); a stop-action movie with Sam's voice-over explaining the network (CNN, pooling); something fun not done in class; four sections: lock policy, 4+ limitations, how the net works (the movie), UNO Q vs computer. One day. Plan: Obsidian note `Midterm 2 Infallible Safe`, bottom section ("Vault Lock Plan - Claude"), followed and ticked there.
- Sam's decisions: the safe should only work for Sam's hand (so the network also answers "is it Sam's hand?", trained against a few friends' hands); fun features = intruder photo + duress code.
- New `FingerLock/` (README has the run order): `capture.py`, `train.py`, `laptop_lock.py`, `bench.py`, `set_codes.py`, `dashboard.html`, `movie/render.py` + `narration.md`, tests; board app `unoq/finger-lock/` (`main.py`, shared `fingernet.py`, `lock_policy.py`, `leds.py`, `photo.py`, `camera.py`; sketch copied from ArduinoDisplay). The camera check is built into the board app (it runs until `fingernet_model.npz` exists) instead of a separate app.
- Finding on synthetic hands: an owner head trained against 1 friend let the other (unseen) friend through 100% of the time (it learns "not like that friend"). Added the prototype check (closeness to the owner's per-count average description); `train.py` scores both on held-out friends and keeps the better one. Synthetic: head refused 0%, prototype 94% of unseen strangers' holds at 90% owner acceptance. Owner threshold rule: the highest that still lets the owner in on 90% of held-out holds.
- Privacy: `data/`, `intruders/`, `runs/`, `check/`, `codes.json`, movie frames/videos gitignored; status messages never include the digits, and the camera's readings only go out with `"demo": true`; the MQTT topic has a random suffix (in codes.json).
- Verified: 26 tests pass; train.py full run on synthetic data; numpy = PyTorch (max diff ~1e-5); board app dry run on the laptop (camera check report; real code opens; duress opens + alert + photo); MQTT through broker.emqx.io (status without readings, alert with a 12 KB PNG); dashboard rendered in headless Chrome with sample messages; movie rendered (53 frames, 76 s, 11 scene videos via Homebrew ffmpeg).
- Not verified: the board's camera API (board unreachable on 11/8: adb no device, no answer at any HOSTS address), anything on real hands, capture.py / laptop_lock.py with a real camera.
- Not committed (Sam's OK needed); the relu_lossregression and MuJoCoHPC changes stay uncommitted.

## Infallible Safe: camera rig, board camera check, box DXFs — 2026-11-09

- Hub wiring: power into the hub's USB-C PD port, the hub's own cable into whichever computer should see the webcam (the board for the safe; the Mac for `capture.py`). The PD port is power only.
- `capture.py --aim` (live view for building the rig, crop square + hand-size guide, `s` saves to `check/`); `--list` prints names from `system_profiler` (no AVFoundation in the root venv) and flags the iPhone (Continuity Camera took index 1 and looked like the webcam). The webcam is "icspring camera", 640x480 on the Mac.
- First board camera check (App Lab, `arduino_app_bricks==0.12.0`, cv2 4.13 in the container): `arduino.app_peripherals.camera.Camera` and `.usb_camera.USBCamera` exist; no camera at that moment because the webcam had moved to the Mac. On the board `/dev/video0`/`1` are the Qualcomm venus encoder/decoder; the webcam appears as `/dev/v4l/by-id/usb-icSpring_icspring_camera_...-video-index0` (camera.py's OpenCV fallback now tries that first). The app container binds all of `/dev`.
- Board app: looks for a camera every 10 s and drops it after 30 failed reads (hot-plug); check mode publishes status (the missing status made the MQTT watchdog reconnect every few seconds); the dashboard shows the whole frame with the crop square once a second.
- Box: `FingerLock/box/make_box.py` (ezdxf 1.4.5, added to requirements.txt): 150 x 100 x 75 mm, 3 mm, finger joints (~10 mm, odd counts), front/back own the bottom corners, door hole 70 x 45 + 80 x 55 overlay door, servo hole 23.5 x 12.5. Ownership is decided per 3 mm cell of the shell, then the DXFs are read back and rebuilt in 3D: every shell cell claimed exactly once. Layout 255 x 260 mm.
- Background (one frame): mid-grey ~122/255 with wood grain, a blue object and the cover's edge in the square; suggested black paper.
- Later: servo hole turned upright (12.5 wide x 23.5 tall) and moved to 1 mm beside the door, because upright the shaft is centred across the servo's width (SG90-type) instead of an uncertain ~6 mm from one end, and the ears point up/down instead of toward the door. Shaft ~7.25 mm from the door's edge: arms of 10/12/15 mm overlap the door by 2.75/4.75/7.75 mm (`front_closeup.png`). DXFs copied to `~/Downloads/infallible_safe_box/`.
- Servo latch: the Zephyr core 1.0.0 on the board has no Servo library (only LED matrix, CAN, RTC, SPI, Wire), so `sketch.ino` makes the pulses itself (D9, every 20 ms, 500-2400 us for 0-180°; keeps pulsing to hold; a negative angle lets go) behind Bridge "servo". `main.py` locks it at start, opens on "open" (duress included), relocks on "relock"; angles in `python/settings.json` (default locked 90, open 0). In camera-check mode only, it listens on `.../cmd` for `{"cmd": "servo", "angle": n}` and the dashboard has a slider for finding the angles. Verified on the board (sketch 90 KB; the board logged servo -> 45 and -> 90 from MQTT, no bridge errors); no servo wired yet.
- Sam's change: inset door (sits in the hole, flush; Sam handles the inward stop) with 1 mm clearance per side (68 x 43), door hole moved to 35 mm from the front's left edge for a hinge, servo hole kept 6 mm right of the door hole. `make_box.py` defaults now reproduce this (`--door-style inset --door-gap 1 --door-left 35 --servo-spacing 6`). Consequence: shaft ~13.25 mm from the door's edge, so 12 mm arm falls 1.2 mm short, 15 mm overlaps 1.8, 18 mm overlaps 4.8. Copied to `~/Downloads/infallible_safe_box/`.
- Data: JOAQ (first volunteer) captured on the Mac with the icspring webcam. First rounds had labels saved while the hand changed shape (39 frames moved: 26 set aside in `FingerLock/check/rejected/`, 13 relabelled; log in `check/rejected/JOAQ_s1_moves.txt`). `capture.py` now saves a 4 s burst at 10/s when a label key is pressed (0.3 s settle, stops by itself; SPACE = open-ended). After that: 1,776 photos (none 156, 0 298, 1 398, 2 295, 3 192, 4 201, 5 236); checked by brightness (hands in "none", empty finger frames), sharpness, and the start/middle/end of all 35 bursts; 4 blurred frames set aside.
- Sam's photos: SAM/lamp1, 1,539 (one session; Sam moved the rig while shooting, so lighting/height vary). 17 set aside (forming-the-pose and thumb-hidden frames, 1 blurred); "no hand" frames were false-flagged by the brightness check (a light patch at the bottom of the mat). Log in `check/rejected/SAM_lamp1_moves.txt`.
- First training (3,298 photos, 30 epochs, +-25 deg turns): 68% of Sam's held-out frames (last 20% per label) counted right; 2 -> "3" in 55/56, 3 -> "4" mostly. The labels were right: the held-out 2s/3s point left (hand from the right), a direction those labels hadn't been shot in. Full-rotation augmentation (corners filled with the border colour) + 60 epochs: 77.7%; a wider net (16/32/64) did worse (71.8%, overfits). Now the default in train.py.
- train.py's counting number now comes from an extra run that includes the friends (like the final network); the stranger runs exclude them, which with one friend means Sam-only training (67%, misleading).
- Current model (exported, not deployed): counting 77.7% held out (none 100, 0 92, 1 100, 2 38, 3 55, 4 86, 5 97%); sure (>= 0.8) on 51% of frames and 96.8% right when sure. Owner check: prototype, threshold fell to the 0.01 floor (no threshold let Sam in on 90% of held-out holds): Sam 85% let in, Joaq 54% refused. Next: lamp2 in the fixed final rig with more 2s/3s from all directions, more volunteers, retrain. Don't deploy the model before the servo is calibrated (the dashboard slider only works in camera-check mode, i.e. without a model).

## Infallible Safe: owner judged once per code, owner threshold setting — 2026-11-10

- Catch-up from late 11/9: Sam added about 400 photos of 2, 3 and 4 and the network was retrained (4,685 photos, 60 epochs, full rotation): 73.9% of Sam's held-out frames counted right (3 still 26%); owner check prototype at 0.09, letting Sam in on 90% of held-out holds and refusing 26% of Joaq's. An arm-to-the-bottom canonicalisation experiment reached 78.5% but wasn't adopted. Sam changed his real code with `set_codes.py`.
- Live laptop tests (11/9 evening, 11/10): the owner check kept refusing Sam (24+ stranger photos, 7 lockouts on 11/9; 3 refusals and a lockout on 11/10). Each refused digit counted as a whole wrong try, so 3 refusals inside one code locked it. The refusal photos from 11/10 score 0.000 on the owner check (the photos' thumbnail resolution barely changes scores: checked on Sam's training photos).
- Changed (Sam's call): `lock_policy.py` judges the owner once per code, on the average of the 4 digits' hold scores, so one code is at most one wrong try and 3 refused codes in a row lock it for 60 s. A stranger's code is reported as "stranger" (photo) at the end, with all digits entered, so nothing mid-code shows which digit failed.
- `settings.json` gets `"owner_threshold": 0.01` (overrides the trained 0.09; 0 turns the check off), read through the new `lock_policy.owner_threshold()` by the board app, `laptop_lock.py` and `movie/render.py`. `laptop_lock.py` logs each frame's owner score and the events with their owner averages, and its panel shows the code's running average.
- Verified: 33 tests pass (8 new policy tests: one wrong try per code, 3 strangers' codes lock out, whole-code average both ways, timeout forgets the scores, threshold source); board app dry run on photos logs "owner threshold 0.01 (settings.json, judged per code)"; the laptop panel rendered with sample values. Not yet run live by Sam; not deployed to the board (servo still to wire).

## Infallible Safe: servo on the board, start button, 3-digit codes — 2026-11-11

- Servo wired by Sam (male-to-male jumpers: signal to D9, red to 5V, brown to GND; the board's only male headers, JSPI and JCTL, weren't used). Deployed in calibration mode; Claude sent 90, 45, 90, 135, 90 over MQTT (`.../cmd`) and the board logged each move, no reset (board powered through the hub from the Mac). Angles still to find with the dashboard slider.
- Brief re-read (pasted by Sam): "you walk up to your safe, push a button, the LEDs light up, you place a pattern of three different numbers (1-5)", and the rubric grades "your 3 digit code". Built both:
  - Start button on D2 (COM to GND, NO to D2; NC also works because the sketch learns the resting level at start). The sketch debounces and counts presses; Bridge `button` (provide_safe, like the wearable's calls) returns the count since the last call. `lock_policy.py` rule 9: with `"button": true` the safe sleeps, LEDs dark, until a press, takes one code, then sleeps again (also after 10 s without a digit); a press while open locks at once; a press mid-code starts over; ignored during a lockout. `laptop_lock.py`: b or SPACE is the button. Calibration mode logs presses and the dashboard counts them, to test the wiring.
  - The UNO Q's own button can't start it: the datasheet (ABX00162/ABX00173, section 11.5) lists only a power button, JBTN1, whose 5 s press reboots Linux. The datasheet also says the headers are 3.3 V logic, so the button only switches the pin to GND.
  - Codes: the rules take any length; `set_codes.py` now asks for 3 different digits, 1-5. Sam's existing 4-digit code keeps working until he reruns it.
- `open_s` (settings.json, now 15 s): at 5 s the safe relocked with the door still open and the arm would block the door. `make_policy()` in `lock_policy.py` builds the rules from the model and settings for the board and the laptop.
- Verified: 45 tests pass (button flow, 3-digit codes, the new code format); board app dry run with simulated presses (wake on each press, LEDs dark while asleep); deployed to the board: the new sketch compiled, the servo still answers, and the button poll runs without errors. Not verified: a real press (button not wired yet), the latch angles, the full code-to-latch test on the board (needs the webcam on the board's hub).
- Later: Sam reran `set_codes.py` (3 digits) and wired the button (COM to GND, NO to D2; the button has only those two terminals). "Nothing happened" on pressing, but the board had logged all 15 presses (23:10:15-23:10:38 UTC, none after, so not noise): calibration mode only logged them. Calibration mode now also lights the LEDs for 1.5 s on a press, with the safe's awake screen.
- Servo twitching while holding still (seen before the button was wired). The board logged no stray servo commands, so the cause is the software-timed pulses being stretched by the board's other work. Fix: the sketch pulses only for 1 s after each move (`SERVO_MOVE_MS`), then stops; `servo` is now `provide_safe` like `button`, so it runs in loop()'s thread. Deployed with the new codes: the sketch compiled, "servo -> 90" answered, no button errors. Twitch fix not yet confirmed by Sam.
- Board moved to its own wall charger (hub and webcam stay on the Mac for photos). The power cut corrupted the container's log file ("docker logs error ... invalid character"), so `arduino-app-cli app logs` stops partway; the board's MQTT status (`servo_angle`, `button_presses`) is the reliable check. Latch: locked 90°, open 0° (Sam: the arm sits locked at 90, open is a quarter turn either way). Claude sent 90, 0, 90, 0, 90; Sam saw it open and close, solid, slight stutter at locked within the 1 s of pulses. `settings.json` set to `"calibrate": false`: the next deploy runs the safe.
- Gavin (second volunteer) captured: 2,003 photos; 13 set aside (fingers pressed into one shape, 2 glitched burst starts; `check/rejected/GAVIN_s1_moves.txt`), 1,990 kept. The 11/9 model already counted 88.5% of them right (its main miss: his 4s with the thumb folded across the palm, read as 5). Retraining started with Joaq and Gavin as held-out strangers; the 11/9 model and figures are backed up in the session scratchpad.
- Full setup on the board (hub's cable into the board, webcam on the hub, charger in the hub's PD port). Deployed the safe (`"calibrate": false`, 11/9 model): status says asleep ("idle"), 3-digit code, 15 frames/s, prepare 27 ms, network 9.4 ms per frame on the UNO Q (laptop: about 1.2 ms network, 3-5 ms prepare). Waiting on Sam's first button-to-latch test.
- Retrained with Gavin (6,675 photos: SAM 2,909, JOAQ 1,776, GAVIN 1,990; 60 epochs, ~13 min). Sam's held-out frames (last 20% per label): 82.4% counted right (was 73.9%); per label none 100, 0 95, 1 97, 2 88, 3 46 (was 26), 4 97, 5 97%; sure on 70% of frames and right on 89.6% of those. Unseen people (the rubric's "different people's hands"): GAVIN 91.3%, JOAQ 64.3% (11/9 model: JOAQ 42.1%). Owner check: prototype at 0.06, Sam's holds let in 90%, strangers' refused 40% (GAVIN 43%, JOAQ 36%; was 26%); settings.json still overrides with 0.01. numpy vs PyTorch max diff 7.6e-6. Deployed to the board while it was idle: "network from 2026-11-11 (6675 photos)", 15 frames/s, network 10.5 ms.
- The 11/9 model and its figures are kept in `FingerLock/check/model_2026-11-09/` (gitignored) for rolling back or comparing.
- Sam's first board tests: the button-to-code pipeline and the LED indicators work well, but codes kept failing and it locked out. The board's photos (pulled from `/home/arduino/ArduinoApps/finger-lock/intruders/`) show why: the first lockout was 3 stranger refusals, all with owner score 0.000, while the counts themselves were right (4 at 0.91, 1 at 0.89, 2 at 0.95); a later lockout was wrong codes. Board frames match the laptop's in exposure, framing and sharpness; at the safe the hand comes in from the bottom with the whole fist in view, while most training photos came from the top. Hand direction isn't the cause: Gavin's photos turned 180° still count 95-99% right. The 1 at 0.89 sits just over the 0.8 confidence bar, so small wobbles drop it to "unsure" and restart the hold.
- Changes: `lockout_s` setting (10 s, Sam's ask), owner check off (`owner_threshold` 0, given the 0.000 scores; set it back to show the extra), `make_policy` passes lockout_s; dashboard/README/narration/movie no longer say 60 s. New `FingerLock/board.py` (start / deploy / status / logs / stop via `tools/deploy.py`, status over MQTT): after a power cut the board boots into Board Status (systemd `board-status-autostart.service`), and `start` stops it and starts the safe in seconds. Tested start from Board Status and deploy; 46 tests pass. Making the safe start at boot instead would mean editing that systemd unit (sudo, Sam).
- Sam: the safe "works pretty solid" on the board (1s still shaky). Duress path reviewed: opens like the real code, saves a photo on the board and publishes `.../alert` (kind "duress", photo) to the public broker; only a dashboard open at that moment receives it (beeps 3x, vibrates on phones, browser notification). Not yet used on the board. The board reaches ntfy.sh (HTTP 200, 0.3 s), so phone push notifications are possible without accounts.
- Section 4 numbers (`figures/bench.json`): laptop network only: prepare 1.49 ms, numpy 0.44 ms, PyTorch 0.16 ms; laptop live (runs/*.csv): 30.2 frames/s, prepare 4.85 ms, numpy 1.5 ms; UNO Q live (40 s of its status): 15.0 frames/s, prepare 27.1 ms, numpy 9.5 ms.
- Brute force with codes of 3 different digits 1-5: 5 x 4 x 3 = 60 codes; at ~6 s a try, 3 tries then a 10 s lockout, every code can be tried in about 10 minutes (half that on average). The duress code is one of the 60, so a brute-forcer has even odds of tripping the silent alarm before finding the real code.
