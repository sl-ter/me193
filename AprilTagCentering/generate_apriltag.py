"""
generate_apriltag.py

Generates a printable AprilTag (36h11 family, the most common/robust one)
and saves it as a PNG with a white border so a detector can find the quiet
zone around the tag.

Usage:
    python generate_apriltag.py               # tag ID 0, ~10cm print size
    python generate_apriltag.py --id 3
    python generate_apriltag.py --size-cm 15  # bigger tag, easier to see
                                               # from farther away
"""

import argparse

import cv2
import numpy as np

# Must match TAG_DICT in apriltag_center.py / apriltag_chase.py -- the
# detector only recognizes tags generated from the same dictionary.
TAG_DICT = cv2.aruco.DICT_APRILTAG_36h11

DPI = 300  # standard printer resolution; the saved PNG is sized so that
           # printing it at "actual size" (100%, no "fit to page") gives
           # you a tag of exactly --size-cm on each side.


def generate(tag_id, size_cm, out_path):
    dictionary = cv2.aruco.getPredefinedDictionary(TAG_DICT)

    size_px = int(size_cm / 2.54 * DPI)
    tag_img = np.zeros((size_px, size_px), dtype=np.uint8)
    cv2.aruco.generateImageMarker(dictionary, tag_id, size_px, tag_img)

    # White quiet-zone border -- detectors need blank space around the tag
    # to lock onto its edges. ~15% of the tag size on each side is plenty.
    border = int(size_px * 0.15)
    bordered = cv2.copyMakeBorder(
        tag_img, border, border, border, border,
        cv2.BORDER_CONSTANT, value=255,
    )

    cv2.imwrite(out_path, bordered)
    total_cm = size_cm + 2 * border / DPI * 2.54
    print(f"Saved {out_path}")
    print(f"Tag ID {tag_id}, dictionary DICT_APRILTAG_36h11")
    print(f"Print at 100% scale (NOT 'fit to page') on paper at least "
          f"{total_cm:.1f}cm x {total_cm:.1f}cm.")
    print("Tape it flat -- a curled or wrinkled tag is much harder to detect.")


def parse_args():
    p = argparse.ArgumentParser(description="Generate a printable AprilTag")
    p.add_argument("--id", type=int, default=0, help="Tag ID (default: 0)")
    p.add_argument("--size-cm", type=float, default=10.0,
                    help="Side length of the black tag square in cm (default: 10)")
    p.add_argument("--out", default="apriltag.png", help="Output file path")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generate(args.id, args.size_cm, args.out)
