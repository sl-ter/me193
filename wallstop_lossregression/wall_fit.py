"""Gradient-descent line fit of motor speed vs. color-sensor reflection.

Same loop as the class handout's run(): raw x blows up, standardized x
converges, and np.polyfit gives the exact answer to compare against.
"""
from pathlib import Path
import csv
import numpy as np

HERE = Path(__file__).parent
rows = list(csv.reader(open(HERE / "annacode-data.csv", encoding="utf-8")))[1:]
# Keep only the stretch where the robot sees the wall and is still slowing:
# reflection 0 = sensor sees nothing yet, speed 0 = already stopped.
pts = sorted((float(r[1]), float(r[2])) for r in rows if float(r[1]) > 0 and float(r[2]) != 0)
x, Y = np.array(pts).T


def run(x, lr, steps=50, m=0.0, b=0.0):
    for _ in range(steps):
        err = Y - (m * x + b)
        m -= lr * np.mean(-err * x)
        b -= lr * np.mean(-err)
    return m, b, np.mean((Y - (m * x + b)) ** 2)


print(f"{len(x)} points, reflection {x.min():.0f}-{x.max():.0f}")
with np.errstate(over="ignore", invalid="ignore"):
    print("raw x, lr 0.0005 (blows up):  ", run(x, 0.0005, 1000))
print("raw x, lr 0.0004 (crawls):     ", run(x, 0.0004, 1000))

mu, sd = x.mean(), x.std()
m, b, loss = run((x - mu) / sd, 0.5, 50)
print(f"standardized x, lr 0.5: m={m:.4f} b={b:.4f} loss={loss:.3f}")
print(f"  back in reflection units: speed = {m / sd:.4f} * reflection + {b - m * mu / sd:.4f}")
print("np.polyfit (exact):", np.polyfit(x, Y, 1))
