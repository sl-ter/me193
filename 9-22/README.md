# 9/22 — AprilTag centering

The car drives back and forth on a track parallel to the laptop screen, with
an AprilTag taped to a tower on it. `apriltag_center.py` watches the webcam,
finds the tag, draws a red outline + centroid coordinates on the live feed,
and drives a Double Motor so the car always comes to rest in the horizontal
middle of the frame.

## Files

- `generate_apriltag.py` — generates a printable AprilTag (36h11 family) as
  a PNG with a white quiet-zone border. `apriltag.png` in this folder (id
  0, 10cm) is the one to print and tape to the tower.
- `apriltag_center.py` — the main task: stationary webcam watches the car,
  centers it.
- `apriltag_center_mobile.py` — bonus variant for later: same centering
  logic, but for when the camera rides on the car facing sideways (a phone
  streamed over WiFi via an IP-camera app, e.g. iVCam/EpocCam) instead of a
  stationary webcam watching the car. **Not yet run** — iVCam isn't set up
  on this machine yet; once it is, point `--stream` at the phone's stream
  URL.
- `lelib.py` — shared LEGO Education wrapper (same file as `9-17/`, copied
  in per this repo's per-folder convention).

Dependencies: same as `9-17/` (`legoeducation`, `opencv-contrib-python`,
`numpy`) — already in the root `requirements.txt`, nothing new needed here.

## Before running

Print `apriltag.png` at **100% scale** (not "fit to page"), tape it flat to
a tower on the car so it faces the camera. `apriltag_center.py` connects to
the first advertising Double Motor it finds — no Connection Card needed
(unlike `9-10/`/`9-17/`).

## Run it

```bash
python 9-22/apriltag_center.py                # drive the real Double Motor
python 9-22/apriltag_center.py --simulate      # no hardware needed, just
                                                # prints the commands it
                                                # would send
python 9-22/apriltag_center.py --camera 1      # pick a different webcam
```

Press `q` or Esc in the video window to quit (also stops the motors).

If it drives the *wrong* direction (chases the error instead of correcting
it), flip `DIRECTION_SIGN` at the top of the file. If one wheel spins
backward relative to the other (car spins in place instead of translating),
flip `INVERT_LEFT_MOTOR`/`INVERT_RIGHT_MOTOR`.

## How it works / questions

### 1. Describe the controller (policy) — how is it determining motor speed?

A **P/PD (proportional/proportional-derivative) feedback controller**, the
same structure as `9-17/pd_tracker.py`'s position tracker, just swapping in
a vision-based error signal instead of a motor-position error:

```
error = tag_centroid_x - frame_center_x
speed = KP * error + KD * d(error)/dt
```

- **P term (`KP * error`)** — the further the tag is from center, the
  faster the car drives toward center. This gives the assignment's "drive
  faster if far, slower if close" bonus for free: speed scales directly
  with how off-center the tag is, and eases toward zero as it approaches
  the middle.
- **D term (`KD * d(error)/dt`)** — reacts to how fast the error is
  already shrinking or growing, damping the response so it doesn't fly
  past center and oscillate forever.
- A small **deadzone** (`DEADZONE_PX`) treats "close enough to center" as
  fully stopped, so the car doesn't jitter back and forth by a pixel or
  two forever trying to hit exactly zero error.

### 2. What does your code do if no tag is detected?

Short dropouts (a single missed frame) are ignored — the car keeps doing
whatever it was last commanded, since flickery misses are normal. But if
the tag hasn't been seen for longer than `NO_TAG_TIMEOUT` (default 0.5s),
the car **fails safe and stops both motors**, and the on-screen overlay
switches to a red "No tag detected" banner. The derivative term's memory
(`prev_error`) is also cleared while the tag is missing, so if it
reappears the D term doesn't spike from comparing against a stale,
long-ago error.

### 3. Can you make it overshoot the center spot and come back (spring-loaded)?

Yes — set `KD = 0` (or small relative to `KP`) in `apriltag_center.py`.
With no damping term, the car drives at full commanded speed toward center
right up until the error crosses zero. By the time the camera sees the new
frame, detection runs, and the command reaches the motor, the car has
already coasted slightly past center — so it corrects back the other way,
overshoots again by a smaller amount, and settles into a decaying
oscillation. That lag chain (camera frame time + detection time + BLE
round-trip + the motor's own spin-up/down time) is exactly what a real
spring-mass-damper system's inertia does, which is why an undamped P
controller "rings" like a spring here. Raising `KD` adds damping and calms
the bounce back down.

## Caveats

Tag detection and centroid math were verified against a synthetic frame
(the generated `apriltag.png` pasted into a blank frame at a known pixel
offset, run through the real detection code path) — confirmed sub-pixel
accurate. Unlike `9-17/`'s untested motor half, **the motor-driving side
of `apriltag_center.py` has already been run against the real Double Motor
and car** — video/photo evidence from that run exists locally (not pushed
to this repo, kept off GitHub to avoid bloating it with ~60MB of media)
showing the car driving back and forth and settling in frame center.
`apriltag_center_mobile.py`'s sideways-camera/iVCam path hasn't been tried
yet since iVCam isn't set up on this machine.
