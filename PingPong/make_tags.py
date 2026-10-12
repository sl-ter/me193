#!/usr/bin/env python3
"""
Make the game's AprilTag cards: tags/tags.pdf, one US Letter page per tag,
each labeled with what it does, plus a PNG of each.

  0 = pause/resume   1 = easy   2 = medium   3 = hard

Same 36h11 family as AprilTagCentering/generate_apriltag.py and vision.py.
Print at 100% / "Actual size" (not "Fit to page") and keep them flat: a
curled tag is much harder to detect.

  venv/bin/python make_tags.py [--size-cm 14]
"""

import argparse
import os

import cv2
import numpy as np
from PIL import Image

DPI = 300
PAGE_W, PAGE_H = int(8.5 * DPI), int(11 * DPI)      # US Letter
LABELS = {0: "PAUSE / RESUME", 1: "EASY", 2: "MEDIUM", 3: "HARD"}
HERE = os.path.dirname(os.path.abspath(__file__))


def tag_page(tag_id, size_cm):
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    size_px = int(size_cm / 2.54 * DPI)
    tag = cv2.aruco.generateImageMarker(dictionary, tag_id, size_px)
    page = np.full((PAGE_H, PAGE_W), 255, np.uint8)
    x0 = (PAGE_W - size_px) // 2
    y0 = int(1.5 * DPI)
    page[y0:y0 + size_px, x0:x0 + size_px] = tag

    def centered(text, y, scale, thick):
        (w, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        cv2.putText(page, text, ((PAGE_W - w) // 2, y), cv2.FONT_HERSHEY_SIMPLEX,
                    scale, 0, thick, cv2.LINE_AA)

    below = y0 + size_px + int(0.9 * DPI)
    centered(f"{tag_id}  {LABELS[tag_id]}", below, 5.0, 12)
    centered(f"Ping-pong card - AprilTag 36h11 ID {tag_id} - {size_cm:g} cm", below + int(0.6 * DPI), 1.6, 3)
    centered("Hold up for about a second. Keep flat.", below + int(1.0 * DPI), 1.6, 3)
    return page, tag


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--size-cm", type=float, default=14.0, help="black square side length")
    args = p.parse_args()

    out = os.path.join(HERE, "tags")
    os.makedirs(out, exist_ok=True)
    pages = []
    for tag_id in LABELS:
        page, tag = tag_page(tag_id, args.size_cm)
        bordered = cv2.copyMakeBorder(tag, 60, 60, 60, 60, cv2.BORDER_CONSTANT, value=255)
        cv2.imwrite(os.path.join(out, f"tag{tag_id}.png"), bordered)
        pages.append(Image.fromarray(page).convert("L"))
    pdf = os.path.join(out, "tags.pdf")
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=DPI)
    print(f"Saved {pdf} ({len(pages)} pages) and tag0-3.png in {out}")
    print("Print at 100% / Actual size, not 'Fit to page'.")


if __name__ == "__main__":
    main()
