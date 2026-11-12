"""What the UNO Q's 13 x 8 LED matrix shows (brightness 0-7, as the sketch
draws it with setGrayscaleBits(3)). Pure numpy, so it's testable on the laptop
(python leds.py prints every screen as text).

Normal screen, left to right:
  cols 0-4   the count the camera sees (5 x 7 digit), "-" for no hand, "?" when
             unsure. Dim while the safe waits for the hand to leave the mat.
  row 7      under the digit: a bar that fills while you hold it (0.8 s)
  col 6      one dot per digit entered (4 slots, faint when empty)
  cols 8-12  a closed padlock
Full-screen moments: a tick when it opens (the duress code looks exactly the
same), a cross for a wrong code, a camera for a stranger's hand (photo taken),
and the padlock with the seconds left during a lockout.
"""
import numpy as np

ROWS, COLS = 8, 13
ON, DIM, FAINT = 7, 2, 1

FONT5x7 = {   # from ArduinoDisplay/python/main.py
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11111", "00010", "00100", "00010", "00001", "10001", "01110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
}
FONT3x5 = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
}
LOCK = [".###.", "#...#", "#...#", "#####", "##.##", "##.##", "#####"]

SCREENS = {
    "open": ["............#",
             "...........#.",
             "..........#..",
             ".#.......#...",
             "..#.....#....",
             "...#...#.....",
             "....#.#......",
             ".....#......."],
    "wrong": ["..#.......#..",
              "...#.....#...",
              "....#...#....",
              ".....#.#.....",
              ".....#.#.....",
              "....#...#....",
              "...#.....#...",
              "..#.......#.."],
    "stranger": ["....###......",
                 ".###########.",
                 ".#...###...#.",
                 ".#..#...#..#.",
                 ".#..#...#..#.",
                 ".#...###...#.",
                 ".###########.",
                 "............."],
    "check_ok": ["............#",
                 "...........#.",
                 "..........#..",
                 ".#.......#...",
                 "..#.....#....",
                 "...#...#.....",
                 "....#.#......",
                 ".....#......."],
    "no_camera": ["###...#...#..",
                  "#......#.#...",
                  "#.......#....",
                  "#......#.#...",
                  "###...#...#..",
                  ".............",
                  ".............",
                  "............."],
}


def blit(arr, rows, top, left, value=ON):
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch in "1#" and 0 <= top + r < ROWS and 0 <= left + c < COLS:
                arr[top + r, left + c] = value
    return arr


def screen(name):
    return blit(np.zeros((ROWS, COLS), np.uint8), SCREENS[name], 0, 0)


def normal(status):
    """The everyday screen, from LockPolicy.status()."""
    arr = np.zeros((ROWS, COLS), np.uint8)
    reading = status.get("reading")
    glyph = "-" if reading in ("none",) else ("?" if reading is None else reading)
    blit(arr, FONT5x7[glyph], 0, 0, DIM if status.get("need_clear") else ON)
    lit = int(round(status.get("hold", 0.0) * 5))
    arr[7, :lit] = ON
    for k in range(status.get("code_len", 4)):
        arr[2 * k, 6] = ON if k < status.get("entered", 0) else FAINT
    blit(arr, LOCK, 0, 8)
    return arr


def lockout(seconds_left):
    arr = blit(np.zeros((ROWS, COLS), np.uint8), LOCK, 0, 0)
    s = f"{min(99, int(np.ceil(seconds_left))):02d}"
    blit(arr, FONT3x5[s[0]], 1, 6)
    blit(arr, FONT3x5[s[1]], 1, 10)
    return arr


def render(status, flash=None):
    """The frame to show. flash: a full-screen moment ("open", "wrong",
    "stranger") that main.py shows for a second or two after an event."""
    if status.get("state") == "lockout":
        return lockout(status.get("left_s", 0.0))
    if status.get("state") == "open":
        return screen("open")
    if flash:
        return screen(flash)
    if status.get("state") == "idle":
        return np.zeros((ROWS, COLS), np.uint8)     # asleep: dark until the button is pressed
    return normal(status)


def as_text(arr):
    return "\n".join("".join(" .:-=+*#"[v] for v in row) for row in arr)


if __name__ == "__main__":
    demo = {"state": "locked", "reading": "3", "hold": 0.6, "entered": 2, "code_len": 4, "need_clear": False}
    for title, arr in [("normal, holding a 3", normal(demo)),
                       ("waiting for the hand to leave", normal(dict(demo, need_clear=True, hold=0))),
                       ("open (also the duress code)", render({"state": "open"})),
                       ("wrong code", render(demo, "wrong")),
                       ("stranger (photo taken)", render(demo, "stranger")),
                       ("lockout, 42 s left", render({"state": "lockout", "left_s": 41.2}))]:
        print(f"{title}:\n{as_text(arr)}\n")
