"""
Generate a printable AprilTag (36h11 family) as a PNG, with a white quiet
zone around it so the detector has contrast to lock onto the tag's edge.

Usage:
    python generate_tag.py [tag_id] [size_px]

Defaults to tag id 0 (matches TAG_ID in track_and_drive.py) at 800x800 px.
Print it flat and as large as your tower/mount allows -- a bigger tag stays
detectable from farther away.
"""

import sys

import cv2

TAG_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 0
SIZE_PX = int(sys.argv[2]) if len(sys.argv) > 2 else 800
QUIET_ZONE_PX = SIZE_PX // 8


def main():
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    tag = cv2.aruco.generateImageMarker(dictionary, TAG_ID, SIZE_PX)
    bordered = cv2.copyMakeBorder(
        tag, QUIET_ZONE_PX, QUIET_ZONE_PX, QUIET_ZONE_PX, QUIET_ZONE_PX,
        cv2.BORDER_CONSTANT, value=255,
    )

    out_path = f"tag_{TAG_ID}.png"
    cv2.imwrite(out_path, bordered)
    print(f"Saved {out_path} ({bordered.shape[1]}x{bordered.shape[0]} px, AprilTag 36h11 id {TAG_ID}).")


if __name__ == "__main__":
    main()
