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
