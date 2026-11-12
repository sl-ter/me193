#!/usr/bin/env python3
"""Laser-cut DXFs for the Infallible Safe's box: 3 mm birch, finger joints, an
open top. Five faces (bottom, back, left, right, front) plus the door.

    python FingerLock/box/make_box.py                       # the defaults below
    python FingerLock/box/make_box.py --width 160 --height 120

All sizes are millimetres. The box is --width wide (left to right), --depth
deep (front to back) and --height tall, measured outside. The front has the
door hole, --door-left from its left edge (room for a hinge), and --servo-spacing
to the hole's right, the servo hole: upright by default (long side vertical, so
the mounting ears point up and down), centred on the door's height.

The door (--door-style): "inset" (default) sits inside the hole, flush with the
front, --door-gap smaller than the hole on every side, hinged along its left
edge; something inside has to stop it swinging in. "overlay" is --door-overlap
bigger than the hole on every side and sits on the outside of the front.

The lock: the servo arm sweeps over the door's right edge. On SG90-type micro
servos the output shaft is centred across the servo's width, so upright it
lands half the servo hole's width from the hole's edge. The arm has to reach
from there past the door's edge; the summary and front_closeup.png show how
far that is and how much 10, 12 and 15 mm arms overlap.

How the joints are made so they can't clash: each wall is a slab 3 mm thick.
Wherever two slabs overlap (every edge of the box) the overlap is cut into
fingers of about --finger mm that alternate between the two panels. Where
three overlap (the four bottom corners) the front or back panel takes the
cube. So every bit of the box's shell belongs to exactly one panel. After
writing the DXFs, this reads them back, rebuilds the box in 3D from them and
checks that: no two parts overlap anywhere and there are no gaps.

Writes, in FingerLock/box/dxf/: one DXF per part (closed polylines on layer
CUT, red, units mm), all_parts.dxf (everything laid out with 5 mm gaps),
preview.png (the parts, labelled) and assembled.png (the box in 3D). No kerf
compensation: the joints come out a little loose (by the laser's cut width),
which wood glue fills.
"""
import argparse
import sys
from bisect import bisect_right
from pathlib import Path

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

HERE = Path(__file__).resolve().parent
PANELS = ["bottom", "front", "back", "left", "right"]
COLOURS = {"bottom": "#2a78d6", "front": "#eb6834", "back": "#1baf7a", "left": "#9b59b6", "right": "#d4a017"}
GAP = 5.0                           # between parts in all_parts.dxf
EAR = 5.0                           # a micro servo's mounting ears stick out about this far past each end
SHAFT_FROM_END = 6.0                # micro servo shaft: about this far from one end (varies by model)


def finger_bounds(lo, hi, target):
    """Boundaries of an odd number of equal fingers between lo and hi, each about target long."""
    n = max(1, int(round((hi - lo) / target)))
    if n % 2 == 0:
        n = n + 1 if (hi - lo) / (n + 1) >= 0.75 * target else n - 1
    n = max(1, n)
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


class Box:
    def __init__(self, W, D, H, t, finger):
        self.W, self.D, self.H, self.t = W, D, H, t
        self.fx = finger_bounds(t, W - t, finger)       # bottom-front / bottom-back joints, along x
        self.fy = finger_bounds(t, D - t, finger)       # bottom-left / bottom-right joints, along y
        self.fz = finger_bounds(t, H, finger)           # the four vertical joints, along z
        self.xb = sorted(set([0.0, t, W - t, W] + self.fx))
        self.yb = sorted(set([0.0, t, D - t, D] + self.fy))
        self.zb = sorted(set([0.0, t, H] + self.fz))

    def slabs(self, x, y, z):
        t = self.t
        return [p for p, inside in [("bottom", z < t), ("front", y < t), ("back", y > self.D - t),
                                    ("left", x < t), ("right", x > self.W - t)] if inside]

    @staticmethod
    def index(bounds, c):
        return bisect_right(bounds, c) - 1

    def owner(self, x, y, z):
        """Which panel the bit of the shell at (x, y, z) belongs to (None = inside or outside the box)."""
        ps = self.slabs(x, y, z)
        if not ps:
            return None
        if len(ps) == 1:
            return ps[0]
        if len(ps) == 3:                                     # a bottom corner
            return "front" if "front" in ps else "back"
        a, b = ps
        if "bottom" in ps:
            other = b if a == "bottom" else a
            k = self.index(self.fx if other in ("front", "back") else self.fy, x if other in ("front", "back") else y)
            return "bottom" if k % 2 == 0 else other
        fb = a if a in ("front", "back") else b              # a vertical edge: front/back with left/right
        lr = b if fb == a else a
        return fb if self.index(self.fz, z) % 2 == 0 else lr

    def panel_grid(self, panel):
        """The panel's face as a grid: u and v cell boundaries, and which cells it owns."""
        mid = lambda bs: [(bs[i] + bs[i + 1]) / 2 for i in range(len(bs) - 1)]      # noqa: E731
        t = self.t
        if panel in ("front", "back"):
            ub, vb = self.xb, self.zb
            y = t / 2 if panel == "front" else self.D - t / 2
            mask = np.array([[self.owner(u, y, v) == panel for v in mid(vb)] for u in mid(ub)])
        elif panel in ("left", "right"):
            ub, vb = self.yb, self.zb
            x = t / 2 if panel == "left" else self.W - t / 2
            mask = np.array([[self.owner(x, u, v) == panel for v in mid(vb)] for u in mid(ub)])
        else:
            ub, vb = self.xb, self.yb
            mask = np.array([[self.owner(u, v, t / 2) == panel for v in mid(vb)] for u in mid(ub)])
        return ub, vb, mask


def outline(ub, vb, mask):
    """The boundary of the owned cells as closed loops of (u, v) corners, counter-clockwise,
    with straight runs merged."""
    nu, nv = mask.shape
    inside = lambda i, j: 0 <= i < nu and 0 <= j < nv and mask[i, j]      # noqa: E731
    edges = {}
    for i in range(nu):
        for j in range(nv):
            if not mask[i, j]:
                continue
            u0, u1, v0, v1 = ub[i], ub[i + 1], vb[j], vb[j + 1]
            if not inside(i, j - 1):
                edges.setdefault((u0, v0), []).append((u1, v0))
            if not inside(i + 1, j):
                edges.setdefault((u1, v0), []).append((u1, v1))
            if not inside(i, j + 1):
                edges.setdefault((u1, v1), []).append((u0, v1))
            if not inside(i - 1, j):
                edges.setdefault((u0, v1), []).append((u0, v0))
    if any(len(v) > 1 for v in edges.values()):
        raise ValueError("a panel's parts only touch at a corner: can't make a single outline")
    loops = []
    while edges:
        start = next(iter(edges))
        loop, p = [start], start
        while True:
            q = edges.pop(p)[0]
            if q == start:
                break
            loop.append(q)
            p = q
        loops.append(simplify(loop))
    return loops


def simplify(loop):
    out = []
    n = len(loop)
    for k in range(n):
        a, b, c = loop[k - 1], loop[k], loop[(k + 1) % n]
        if not ((a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1])):
            out.append(b)
    return out


def overlap_text(overlap):
    return f"overlaps the door by {overlap:.1f} mm" if overlap > 0 else f"falls {-overlap:.1f} mm short of the door"


def rect(u0, v0, w, h):
    return [(u0, v0), (u0 + w, v0), (u0 + w, v0 + h), (u0, v0 + h)]


def area(loop):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(loop, loop[1:] + loop[:1]))


def write_dxf(path, shapes):
    """shapes: [(loop, (du, dv))] -> closed polylines on layer CUT, in mm."""
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.MM
    doc.header["$MEASUREMENT"] = 1
    doc.layers.add("CUT", color=1)
    msp = doc.modelspace()
    for loop, (du, dv) in shapes:
        msp.add_lwpolyline([(round(u + du, 4), round(v + dv, 4)) for u, v in loop], close=True,
                           dxfattribs={"layer": "CUT"})
    doc.saveas(path)


def read_loops(path):
    doc = ezdxf.readfile(path)
    return [[(p[0], p[1]) for p in e.get_points("xy")] for e in doc.modelspace().query("LWPOLYLINE")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=float, default=150.0, help="left to right: the front's width")
    ap.add_argument("--depth", type=float, default=100.0, help="front to back")
    ap.add_argument("--height", type=float, default=75.0)
    ap.add_argument("--thickness", type=float, default=3.0)
    ap.add_argument("--finger", type=float, default=10.0, help="target finger length")
    ap.add_argument("--door-hole", default="70x45", help="width x height of the hole in the front")
    ap.add_argument("--door-left", type=float, default=35.0,
                    help="from the front's left edge to the door hole (room for the hinge)")
    ap.add_argument("--door-style", choices=["inset", "overlay"], default="inset",
                    help="inset: the door sits in the hole, flush; overlay: it covers the hole from outside")
    ap.add_argument("--door-gap", type=float, default=1.0, help="inset door: clearance on every side")
    ap.add_argument("--door-overlap", type=float, default=5.0, help="overlay door: how much bigger than the hole, each side")
    ap.add_argument("--servo-hole", default="23.5x12.5", help="the servo body's long x short side")
    ap.add_argument("--servo-horizontal", action="store_true",
                    help="long side horizontal (default: upright, which lets the shaft sit closer to the door)")
    ap.add_argument("--servo-spacing", type=float, default=6.0,
                    help="wood between the door hole and the servo hole")
    ap.add_argument("--arm", type=float, default=18.0,
                    help="servo arm length, shaft centre to tip, for the close-up drawing")
    ap.add_argument("--sheet-width", type=float, default=300.0, help="max width of the all_parts layout")
    ap.add_argument("--out", type=Path, default=HERE / "dxf")
    args = ap.parse_args()

    W, D, H, t = args.width, args.depth, args.height, args.thickness
    hw, hh = (float(s) for s in args.door_hole.lower().split("x"))
    long_side, short_side = sorted((float(s) for s in args.servo_hole.lower().split("x")), reverse=True)
    upright = not args.servo_horizontal
    sw, sh = (short_side, long_side) if upright else (long_side, short_side)
    ov = args.door_overlap
    box = Box(W, D, H, t, args.finger)

    # The front's holes, in its own coordinates: u = x (right as you face the front), v = z (up).
    hx, hz = args.door_left, (H - hh) / 2
    inset = args.door_style == "inset"
    g = args.door_gap
    door = (hx + g, hz + g, hw - 2 * g, hh - 2 * g) if inset else (hx - ov, hz - ov, hw + 2 * ov, hh + 2 * ov)
    door_right = door[0] + door[2]
    sx, sz = hx + hw + args.servo_spacing, hz + hh / 2 - sh / 2
    door_hole, servo_hole = rect(hx, hz, hw, hh), rect(sx, sz, sw, sh)
    # The shaft is centred across the servo's width (exact for micro servos like the SG90); along
    # its length it's near one end, about SHAFT_FROM_END mm in, which varies by model.
    shaft_x = sx + sw / 2 if upright else sx + SHAFT_FROM_END
    shafts = ([(shaft_x, sz + sh - SHAFT_FROM_END), (shaft_x, sz + SHAFT_FROM_END)] if upright
              else [(shaft_x, sz + sh / 2)])     # upright: shaft end up or down, either works
    reach = shaft_x - door_right                  # the arm must be longer than this to lock
    problems = []
    if min(door[0], hx) < t + 3:
        problems.append("the door or its hole reaches the left wall: increase --door-left")
    if min(door[1], hz) < t + 3 or max(door[1] + door[3], hz + hh) > H - 3:
        problems.append("the door is too tall for the front")
    if inset and (g < 0.3 or door[2] <= 0 or door[3] <= 0):
        problems.append("--door-gap must be at least 0.3 mm (and smaller than half the hole)")
    if not inset and sx < door_right + 0.5:
        problems.append("the servo body would rub the overlay door: increase --servo-spacing")
    if args.servo_spacing < 4:
        problems.append("less than 4 mm of wood between the door hole and the servo hole")
    if upright and (sz - EAR < t + 1 or sz + sh + EAR > H - 1):
        problems.append(f"the servo's mounting ears (about {EAR:g} mm past each end) would hit the bottom joint "
                        "or stick out of the top: make the box taller or the servo hole shorter")
    if not upright and (sx - (hx + hw) < EAR + 1 or sx + sw + EAR > W - t - 1):
        problems.append("no room for the servo's mounting ears beside the holes")
    if sx + sw > W - t - 3:
        problems.append("the servo hole is too close to the right wall")
    if problems:
        sys.exit("\n".join(problems))

    parts = {}
    for p in PANELS:
        ub, vb, mask = box.panel_grid(p)
        loops = outline(ub, vb, mask)
        if len(loops) != 1:
            sys.exit(f"{p}: expected one outline, got {len(loops)}")
        loop = loops[0] if area(loops[0]) > 0 else loops[0][::-1]
        holes = [door_hole, servo_hole] if p == "front" else []
        parts[p] = {"loops": [loop] + holes, "size": (ub[-1], vb[-1]), "grid": (ub, vb, mask)}
    parts["door"] = {"loops": [rect(0, 0, door[2], door[3])], "size": (door[2], door[3])}

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    for name, part in parts.items():
        write_dxf(out / f"{name}.dxf", [(lp, (0, 0)) for lp in part["loops"]])

    # Lay everything out in rows no wider than --sheet-width: tallest parts first, each into the
    # first row with room for it (so short parts fill the gaps next to long ones).
    order = sorted(parts, key=lambda n: (-parts[n]["size"][1], -parts[n]["size"][0]))
    rows, placed = [], {}                    # rows: [x of the next free spot, y, height]
    for name in order:
        w, h = parts[name]["size"]
        row = next((r for r in rows if r[0] + w <= args.sheet_width), None)
        if row is None:
            row = [0.0, rows[-1][1] + rows[-1][2] + GAP if rows else 0.0, h]
            rows.append(row)
        placed[name] = (row[0], row[1])
        row[0] += w + GAP
    sheet = (max(placed[n][0] + parts[n]["size"][0] for n in parts), rows[-1][1] + rows[-1][2])
    write_dxf(out / "all_parts.dxf", [(lp, placed[n]) for n in parts for lp in parts[n]["loops"]])

    # ---- Checks, from the DXF files as written --------------------------------------------------
    report = []
    for p in PANELS:
        ub, vb, mask = parts[p]["grid"]
        loops = read_loops(out / f"{p}.dxf")
        outer = max(loops, key=lambda lp: abs(area(lp)))
        path = MPath(outer)
        centres = [((ub[i] + ub[i + 1]) / 2, (vb[j] + vb[j + 1]) / 2) for i in range(len(ub) - 1) for j in range(len(vb) - 1)]
        got = np.array(path.contains_points(centres)).reshape(mask.shape)
        if not (got == mask).all():
            sys.exit(f"CHECK FAILED: {p}.dxf doesn't match its joint plan")
        parts[p]["dxf_mask"] = got
    mid = lambda bs: [(bs[i] + bs[i + 1]) / 2 for i in range(len(bs) - 1)]      # noqa: E731
    xs, ys, zs = mid(box.xb), mid(box.yb), mid(box.zb)
    claims = np.zeros((len(xs), len(ys), len(zs)), int)
    owner3d = np.full(claims.shape, "", dtype=object)

    def lookup(p, u, v):
        ub, vb, _ = parts[p]["grid"]
        return parts[p]["dxf_mask"][Box.index(ub, u), Box.index(vb, v)]

    for i, xc in enumerate(xs):
        for j, yc in enumerate(ys):
            for k, zc in enumerate(zs):
                for p in box.slabs(xc, yc, zc):
                    u, v = {"front": (xc, zc), "back": (xc, zc), "left": (yc, zc), "right": (yc, zc),
                            "bottom": (xc, yc)}[p]
                    if lookup(p, u, v):
                        claims[i, j, k] += 1
                        owner3d[i, j, k] = p
                in_shell = bool(box.slabs(xc, yc, zc))
                if in_shell and claims[i, j, k] != 1:
                    sys.exit(f"CHECK FAILED: the shell at ({xc:.1f}, {yc:.1f}, {zc:.1f}) is claimed by "
                             f"{claims[i, j, k]} parts")
                if not in_shell and claims[i, j, k]:
                    sys.exit("CHECK FAILED: a part sticks into the inside of the box")
    report.append("3D check: every bit of the shell belongs to exactly one part (no gaps, no overlaps)")
    front_outer = MPath(max(read_loops(out / "front.dxf"), key=lambda lp: abs(area(lp))))
    for name, hole in [("door hole", door_hole), ("servo hole", servo_hole)]:
        if not all(front_outer.contains_points(hole)):
            sys.exit(f"CHECK FAILED: the {name} isn't inside the front")
    report.append(f"holes inside the front, at least {min(hx, hz - 0, W - sx - sw, H - hz - hh):.1f} mm from its edges")

    # ---- Pictures ------------------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 9 * sheet[1] / sheet[0] + 0.6))
    for name, part in parts.items():
        du, dv = placed[name]
        for k, lp in enumerate(part["loops"]):
            xy = np.array(lp + lp[:1]) + (du, dv)
            ax.plot(xy[:, 0], xy[:, 1], color=COLOURS.get(name, "#333333") if k == 0 else "#d33b3b", lw=1)
        w, h = part["size"]
        ax.text(du + w / 2, dv + h / 2, f"{name}\n{w:g} x {h:g}", ha="center", va="center", fontsize=9)
    ax.set_aspect("equal")
    ax.set_title(f"all_parts.dxf: {sheet[0]:.0f} x {sheet[1]:.0f} mm, {t:g} mm birch", loc="left")
    ax.set_xlabel("mm")
    fig.tight_layout()
    fig.savefig(out / "preview.png", dpi=150)
    plt.close(fig)

    X, Y, Z = np.meshgrid(box.xb, box.yb, box.zb, indexing="ij")
    filled = owner3d != ""
    colours = np.empty(filled.shape, dtype=object)
    for p in PANELS:
        colours[owner3d == p] = COLOURS[p]
    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(projection="3d")
    ax.voxels(X, Y, Z, filled, facecolors=colours, edgecolor="#00000030", linewidth=0.2)
    for name, (u0, v0, w, h) in [("door hole", (hx, hz, hw, hh)), ("servo", (sx, sz, sw, sh))]:
        xx = [u0, u0 + w, u0 + w, u0, u0]
        zz = [v0, v0, v0 + h, v0 + h, v0]
        ax.plot(xx, [-0.5] * 5, zz, color="#d33b3b", lw=1.5)
    ax.set_box_aspect((W, D, H))
    ax.view_init(elev=24, azim=-58)
    ax.set_title("assembled (front faces you; open top)\n" +
                 "  ".join(f"{p}: {COLOURS[p]}" for p in PANELS), fontsize=9, loc="left")
    fig.tight_layout()
    fig.savefig(out / "assembled.png", dpi=150)
    plt.close(fig)

    # The front, close up: can the servo arm reach over the door?
    fig, ax = plt.subplots(figsize=(8, 6.2))
    front = parts["front"]["loops"]
    for k, lp in enumerate(front):
        xy = np.array(lp + lp[:1])
        ax.plot(xy[:, 0], xy[:, 1], color=COLOURS["front"] if k == 0 else "#d33b3b", lw=1.5)
    dxy = np.array(rect(*door) + rect(*door)[:1])
    ax.plot(dxy[:, 0], dxy[:, 1], "--", color=COLOURS["bottom"], lw=1.5,
            label=f"door ({'in the hole' if inset else 'on the outside'})")
    theta = np.linspace(0, 2 * np.pi, 200)
    for n, (x0, z0) in enumerate(shafts):
        ax.plot(x0, z0, "k+", ms=12, mew=2, label="servo shaft" if n == 0 else None)
        for arm, style in [(12, ":"), (15, "--"), (args.arm, "-")]:
            ax.plot(x0 + arm * np.cos(theta), z0 + arm * np.sin(theta), style, color="#555555", lw=0.8)
        ax.plot([x0, x0 - args.arm], [z0, z0], color="#1baf7a", lw=4, solid_capstyle="round",
                label=f"{args.arm:g} mm arm, locked" if n == 0 else None)
    ax.axvline(door_right, color=COLOURS["bottom"], lw=0.8)
    ax.annotate(f"shaft to door edge: {reach:.2f} mm", (door_right, shafts[0][1] + 13), fontsize=10)
    ax.set_xlim(door_right - 30, sx + sw + 25)
    ax.set_ylim(max(0, sz - 18), min(H, sz + sh + 18))
    ax.set_aspect("equal")
    ax.set_title(f"Front, close up. Circles: arms of 12, 15 and {args.arm:g} mm.\n"
                 f"A {args.arm:g} mm arm {overlap_text(args.arm - reach)} when locked.", loc="left", fontsize=10)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_xlabel("mm from the front's left edge")
    ax.set_ylabel("mm up")
    fig.tight_layout()
    fig.savefig(out / "front_closeup.png", dpi=150)
    plt.close(fig)

    # ---- Summary -------------------------------------------------------------------------------
    print(f"Box {W:g} x {D:g} x {H:g} mm outside, {t:g} mm walls, open top")
    print(f"Fingers: {len(box.fx) - 1} along the width ({box.fx[1] - box.fx[0]:.2f} mm), "
          f"{len(box.fy) - 1} along the depth ({box.fy[1] - box.fy[0]:.2f} mm), "
          f"{len(box.fz) - 1} up each corner ({box.fz[1] - box.fz[0]:.2f} mm)")
    print(f"Door hole {hw:g} x {hh:g} at {hx:g} mm from the front's left edge ({hx - t:g} mm from the inside "
          f"of the left wall, for the hinge) and {hz:g} mm up")
    print(f"Door {door[2]:g} x {door[3]:g}: " + (f"inset, {g:g} mm clear of the hole on every side" if inset
                                               else f"overlay, {ov:g} mm bigger than the hole on every side"))
    print(f"Servo hole {sw:g} wide x {sh:g} tall ({'upright' if upright else 'long side horizontal'}), "
          f"{args.servo_spacing:g} mm right of the door hole: left edge {sx:g} mm from the front's left edge, "
          f"{sz:g} mm up; {W - sx - sw:g} mm from the front's right edge")
    print(f"Servo shaft about {reach:.2f} mm right of the door's edge"
          + (" (if, as on SG90-type servos, the shaft is centred across the servo's width)" if upright
             else f" (assuming the shaft is {SHAFT_FROM_END:g} mm from the servo's end: check yours)"))
    print("Servo arm, locked: " + "; ".join(f"{a:g} mm arm {overlap_text(a - reach)}" for a in (12, 15, 18)))
    print(f"All parts laid out: {sheet[0]:.0f} x {sheet[1]:.0f} mm")
    for line in report:
        print(line)
    print(f"Files in {out}: " + ", ".join(sorted(f.name for f in out.iterdir())))


if __name__ == "__main__":
    main()
