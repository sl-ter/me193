# Infallible Safe — 11/8

ME193 Midterm 2: a safe that opens when its camera sees the right code shown with fingers. A convolutional neural network, built from scratch in PyTorch, counts the fingers (no hand, 0-5) and checks that the hand is the owner's. The same trained weights run on the laptop (PyTorch or numpy) and on the UNO Q (numpy). The plan lives in the Obsidian note `Midterm 2 Infallible Safe` (bottom section).

The assignment: PyTorch, net built from scratch, returns the number of fingers in the camera image; a Notion page with video, GitHub, intro and good explanations; a stop-action movie with Sam's voice-over explaining the network (CNN and pooling); something fun not done in class; and four sections: the lock policy, 4+ limitations, how the net works (the movie), and the UNO Q setup vs the computer.

Status, 11/11: **working on the UNO Q**: start button, LEDs, 3-digit code, servo latch, dashboard alerts. The network is trained on 6,675 photos of three people's hands (Sam, Joaq, Gavin): 82% of Sam's held-out frames counted right (3 is the weak one, at 46%), and 91% and 64% of Gavin's and Joaq's when it had never seen them. Still to do: more photos of 1s and 3s taken at the safe, the duress code tested on the board, the movie from the final network, the demo video and the write-up.

## How it works

- **Setup:** a USB webcam looks down at a plain mat under a lamp. As the brief asks, you walk up, push the start button, the LEDs light up, and you show a 3-digit code (3 different digits, 1-5) one digit at a time, taking your hand off the mat, for about a second, between digits. (Codes set before 11/11 were 4 digits, 0-5; the rules take any length, `set_codes.py` now asks for the brief's format.)
- **Wiring** (UNO Q headers): latch servo signal (orange) to D9, red to 5V, brown to GND; start button COM to GND and NO to D2 (NC works too: the sketch learns the resting level at start).
- **Network** (`unoq/finger-lock/python/fingernet.py`, trained by `train.py`): 64 x 64 grey picture, then 3 rounds of 3 x 3 convolution, ReLU and 2 x 2 max pooling (8, 16, 32 filters), then a fully connected layer of 64 (the hand's "description"), then two answers: the count (softmax over 7) and the owner check.
- **Owner check, two ways** (`train.py` keeps whichever refuses more strangers it never trained on):
  - *head*: an output trained on the owner's hand vs friends' hands.
  - *prototype*: the owner's average description per count; a hand scores high when it's close to it. On the synthetic data the head let every unseen stranger through (it learned "not like the friends I saw"), while the prototype check refused 94% of their holds and let the owner in on 90%. The real numbers come from real photos.
- **Rules** (`lock_policy.py`, tested in `test_lock_policy.py`): the safe sleeps, LEDs dark, until the button wakes it for one code (`"button": true` in `settings.json`; b on the laptop); a digit counts once the same reading holds 0.8 s at 80%+; the hand must leave the mat between digits; after the last digit the owner is judged once, on the code's average owner score (threshold in `settings.json`), and the right code from the owner's hand opens it for `open_s` seconds (15, in `settings.json`; shut the door before the latch swings back); 3 refused codes in a row (wrong, or a stranger's) lock it for `lockout_s` seconds (10, in `settings.json`); after a code, or 10 s without a digit, it goes back to sleep; pressing the button while it's open locks it at once.
- **Fun features:** an *intruder photo* (a stranger's hand or a lockout sends a photo to the dashboard/phone) and a *duress code* (opens exactly like the real code, LED included, but silently sends an alert with a photo).
- **Board** (`unoq/finger-lock/`, App Lab app): camera, network, rules, LED matrix (`leds.py`), MQTT status/alerts. Until a trained network is copied in, it runs a **camera check** instead and streams the mat's view to the dashboard for aiming the camera.
- **Dashboard** (`dashboard.html#<topic>`): state, speed, alerts with photos, the camera check. On a phone (GitHub Pages) it's the alarm: it can beep and vibrate.

## Run it

```bash
cd ~/Code/Projects/me193 && source venv/bin/activate      # every new terminal

python FingerLock/set_codes.py               # set or change the real + duress code (typed hidden): codes.json (gitignored), prints the topic

# Photos
python FingerLock/capture.py --list          # camera numbers and names (an iPhone nearby takes one too)
python FingerLock/capture.py --aim --camera N    # live view for aiming the camera; s saves a snapshot to check/
python FingerLock/capture.py --person SAM --session lamp2 --camera N    # 0-5 / n: a 4 s burst at 10/s; SPACE: no limit; q quits
python FingerLock/capture.py --person NAME --session s1 --camera N      # a friend

# Network
python FingerLock/train.py                   # held-out tests, figures/, exports fingernet_model.npz (--quick: 3 epochs)

# The safe
python FingerLock/laptop_lock.py --camera N  # on the laptop, with the debug window (b = the start button, q quits); --mqtt also feeds the dashboard
open "FingerLock/dashboard.html#<topic>"     # status, alerts with photos, camera check, servo slider
python FingerLock/board.py start              # after the board restarts (its IP scrolls): start the safe
python FingerLock/board.py deploy             # after any change: copy the app (codes, model, settings.json), start it
python FingerLock/board.py status             # what the safe says right now; also: logs, stop

# Write-up
python FingerLock/bench.py; python FingerLock/bench.py --runs; python FingerLock/bench.py --board 60   # speed table
python FingerLock/movie/render.py            # the movie's frames and videos (movie/*.mp4)
python -m pytest FingerLock -q               # tests
```

- **What a deploy runs** depends on `settings.json`: `"calibrate": true` runs the camera check and listens to the dashboard's servo slider; `false` runs the safe. The laptop safe and the board both read its `owner_threshold`, which overrides the threshold `train.py` picks: delete that line to use the trained one.
- **Demo mode:** set `"demo": true` in `settings.json` (and redeploy) to send what the camera reads to the dashboard, for the video. Leave it off otherwise: anyone on the public broker who knew the topic could watch the code go in.
- **Deploying:** while the camera hub is in the board's only USB-C port, deploy over Wi-Fi (USB deploys use that port). `deploy.py` copies `codes.json` and the trained `fingernet_model.npz` with the app.
- **Dry run on the laptop** (no board): `FINGERLOCK_FAKE_FRAMES=<folder of photos> FINGERLOCK_NO_MQTT=1 FINGERLOCK_APP_DIR=<scratch folder> python FingerLock/unoq/finger-lock/python/main.py`, plus `FINGERLOCK_MODEL=<npz>` and `FINGERLOCK_MAX_FRAMES=<n>` as needed.

## Files

| File | What |
|---|---|
| `capture.py` | labelled photos: keys 0-5 / n for no hand save a 4 s burst at 10 a second (pose first, then press), SPACE saves with no time limit, to `data/<PERSON>/<session>/<label>/` (gitignored) |
| `train.py` | trains and tests the network (PyTorch), picks the owner check and its threshold on held-out people, exports `unoq/finger-lock/python/fingernet_model.npz`, writes `figures/` |
| `laptop_lock.py` | the safe on the laptop, with a window showing what the network sees; timing logs in `runs/` |
| `bench.py` | speed table for section 4: laptop network only, laptop live, UNO Q live |
| `board.py` | the safe on the board in one command: start (after a reboot), deploy (after a change), status, logs, stop; goes through `tools/deploy.py` |
| `set_codes.py` | writes `codes.json` (real code, duress code, random MQTT topic) |
| `dashboard.html` | live state, speed, alerts with photos, camera check |
| `movie/render.py`, `movie/narration.md` | stop-action frames and per-scene videos from the real network; voice-over draft |
| `unoq/finger-lock/python/` | the board app: `main.py`, and the shared `fingernet.py`, `lock_policy.py`, `leds.py`, `photo.py`, `camera.py` |
| `test_lock_policy.py`, `test_fingernet.py` | rules on made-up streams; numpy = PyTorch, preprocessing, PNG, LED frames |
| `common.py` | paths, owner name, camera opener, codes loader |
| `unoq/finger-lock/python/settings.json` | the latch servo's locked and open angles (find them with the dashboard's servo slider while the board is in camera-check mode); `calibrate`; `demo`; `owner_threshold` (overrides the trained one, read by the board and `laptop_lock.py`; 0 turns the owner check off); `open_s` (how long the safe stays open); `button` (wait for the start button) |
| `box/make_box.py`, `box/dxf/` | laser-cut box: 3 mm birch, finger joints, open top, 150 x 100 x 75 mm, door hole + door + servo hole; one DXF per part, `all_parts.dxf`, previews. Checks the parts in 3D before writing |

## How the code was developed

- **Patterns reused from this repo** (read 11/8): the wearable's split between a numpy forward pass shared with the board and PyTorch training with a numpy-vs-PyTorch check (`ActivityWearable/unoq/activity-wearable/python/steps.py`, `ActivityWearable/train_steps.py`); its board app's MQTT setup and echo watchdog (`ActivityWearable/unoq/activity-wearable/python/main.py`, broker `broker.emqx.io`); the LED matrix sketch and `Frame` drawing (`ArduinoDisplay/`); the macOS camera opener (`CustomRobotCentering/common.py`); the deploy kit (`tools/deploy.py`, which copies every non-hidden file in the app folder).
- **The board's camera:** `camera.py` tries App Lab's camera class first, then OpenCV. The App Lab usage (`Camera("usb:0", resolution=(640, 480), fps=15)`, `start()`, `capture()`) comes from search-result summaries of community posts, not Arduino's docs, and wasn't checked on the board (it was unreachable on 11/8): [element14 post](https://community.element14.com/challenges-projects/design-challenges/ez-ev-challenge/f/forum/57183/hall-w-ev---post-4---giving-it-eyes), [Arduino forum thread](https://forum.arduino.cc/t/unable-to-connect-arduino-uno-q-to-webcam/1449124). The same sources say the hub must supply 5 V/3 A. The camera check logs every attempt, so the first deploy settles it.
- **General practice, not from a source read for this:** the PyTorch layers and losses (`Conv2d`, `max_pool2d`, `cross_entropy` with class weights, `binary_cross_entropy_with_logits` with `pos_weight`, Adam), the area-averaging resize, the PNG file layout (verified by a round trip through Pillow in the tests), and the prototype owner check (compare a description with the owner's per-class mean, scaled by its spread; the idea behind nearest-class-mean and face-verification checks).
- **Tested:** the rules on made-up answer streams (20 tests, at 4, 10 and 30 frames a second); the numpy network against PyTorch (max difference about 1e-5); the whole pipeline on synthetic hands (training, held-out tests, export, the board app opening for the real code and raising the duress alert, MQTT messages through the real broker, the dashboard rendered in headless Chrome with sample messages).
- **Tested since, with real hands (11/9-11/11):** held-out photos and people (numbers above, `figures/results.json`); the laptop and board safes live; the board's speed (`figures/bench.json`: 15 frames/s, 9.5 ms per network pass on the UNO Q vs 0.44 ms on the laptop); the button, latch and LEDs on the board.
- **Not proven yet:** the owner check on new people and new setups (it follows the camera setup more than the hand, so it's off for now: `owner_threshold` 0 in `settings.json`); tricks such as a printed photo of a hand.
