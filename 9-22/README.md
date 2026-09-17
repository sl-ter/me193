# 9/22 — AprilTag centering

The car drives back and forth on a track parallel to the laptop screen, with
an AprilTag taped to a tower on it. This watches the webcam, finds the tag,
draws a red outline + centroid on the live feed, and drives the car so it
always comes to rest in the horizontal middle of the frame.

- `generate_tag.py` — generates a printable AprilTag (36h11 family, id 0 by
  default) as a PNG with a white quiet-zone border. `tag_0.png` in this
  folder is the one actually printed and taped to the tower.
- `track_and_drive.py` — the live loop: detects the tag with OpenCV's
  `cv2.aruco` AprilTag detector, draws the red outline and centroid
  coordinates, and drives a Double Motor to center it.
- `lelib.py` — shared LEGO Education wrapper (same file as `9-17/`, copied
  in per this repo's per-folder convention).

New dependency: `opencv-contrib-python` (added to the root
`requirements.txt`) — plain `opencv-python` doesn't include the `aruco`
module's AprilTag dictionaries, `-contrib` does.

## Before running

`CARD_COLOR`/`CARD_SERIAL` at the top of `track_and_drive.py` are set to
this kit's Connection Card (orange, `0994`), same as `9-10/` and `9-17/`.

Print `tag_0.png` flat, as large as the tower will hold without wobbling,
and tape it to face the camera as the car drives past.

## Run it

```bash
python 9-22/generate_tag.py      # only needed once, to (re)print the tag
python 9-22/track_and_drive.py
```

Press `q` in the video window to quit (this also stops the motor).

## How it works / questions

**Describe the controller (policy) — how is it determining the motor speed?**

Every camera frame:

```
error  = frame_center_x - tag_centroid_x      (pixels)
speed  = Kp * error - Kd * d(error)/dt
```

`speed` (clamped to ±100%, in percent) is the only thing commanded — there's
no separate "drive to position" call, and no explicit "measure distance,
then pick a speed" step. This already gives the "faster when far, slower
when close" behavior asked for as a stretch goal for free: `error` is
literally how far off-center (in pixels) the tag is, so a proportional
controller's speed naturally scales down as the tag approaches the middle
of the frame and hits zero right at center. The sign of `error` also picks
the direction — tag left of center drives one way, tag right of center
drives the other.

**What does your code do if no tag is detected?**

`dm.stop()` — motor speed goes to zero immediately, no coasting toward a
guess. It also resets the derivative state (`prev_error = None`) so that
when the tag is reacquired, the code doesn't compute a derivative spike
from the gap in time where there was no reading (a real jump in `error`
across a dropped-frame gap isn't the car's actual rate of motion, so
treating it as one would produce a bogus kick in the speed command). A "NO
TAG DETECTED" banner is drawn on the video feed at the same time.

**Can you make it overshoot the center spot and come back (spring loaded)?**

Yes — that's what the `Kd` term is for. Physically, `Kp` acts like a spring
constant pulling the car toward center, and `Kd` acts like a damper
resisting how fast it's approaching. With `SPRING_LOADED = True` (the
default here), `Kd = 0`: nothing opposes the car's own momentum, so it
overshoots center and swings back, oscillating a bit before friction
settles it — an underdamped spring. Setting `SPRING_LOADED = False` raises
`Kd`, which damps that motion out so the car eases into center without
overshoot instead (overdamped/critically damped).

## Caveats

Tested end-to-end for tag detection, outline drawing, and centroid math
against a synthetic frame (a `tag_0.png` pasted at a known offset into a
blank frame) — confirmed the detector finds it and the computed centroid
matches the known placement to sub-pixel accuracy. The motor-driving half
(`dm.connect()`/`dm.run()`/`dm.stop()`) wasn't tested against real
hardware this session — same caveat as `9-17/`. `KP`/`DEAD_ZONE_PX`/
`DRIVE_SIGN` are starting guesses and will likely need tuning once run
against the actual car, track distance, and camera. In particular, if the
car drives *away* from center instead of toward it, flip `DRIVE_SIGN` to
`-1`.
