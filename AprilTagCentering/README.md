# AprilTag centering — 9/22

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
- `lelib.py` — shared LEGO Education wrapper (same file as
  `PDPositionTracker/`, copied in per this repo's per-folder convention).

Dependencies: same as `PDPositionTracker/` (`legoeducation`,
`opencv-contrib-python`, `numpy`) — already in the root `requirements.txt`,
nothing new needed here.

## Before running

Print `apriltag.png` at **100% scale** (not "fit to page"), tape it flat to
a tower on the car so it faces the camera. `apriltag_center.py` connects to
the first advertising Double Motor it finds — no Connection Card needed
(unlike `MotorSpinDemo/`/`PDPositionTracker/`).

## Run it

```bash
python AprilTagCentering/apriltag_center.py                # drive the real Double Motor
python AprilTagCentering/apriltag_center.py --simulate      # no hardware needed,
                                                             # just prints the
                                                             # commands it would send
python AprilTagCentering/apriltag_center.py --camera 1      # pick a different webcam
```

Press `q` or Esc in the video window to quit (also stops the motors).

If it drives the *wrong* direction (chases the error instead of correcting
it), flip `DIRECTION_SIGN` at the top of the file. If one wheel spins
backward relative to the other (car spins in place instead of translating),
flip `INVERT_LEFT_MOTOR`/`INVERT_RIGHT_MOTOR`.
