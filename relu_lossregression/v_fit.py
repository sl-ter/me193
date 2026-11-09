"""Fit the V example from Anna's code by gradient descent, with the gradients written out by hand.

Part 1 is a single neuron with ReLU, y = ReLU(m*x_hat + b). It uses the same start, learning rate
and loss as v_fit_5_iterations.xlsx, so epochs 0-4 printed here are the spreadsheet's
iterations 1-5, and epoch 5 is its "after 5" row.

Part 2 is what Anna's site recommends for a V: a hidden layer of 2 ReLU neurons feeding one output
neuron with no activation. Like pressing "Randomize weights" then "Train" again on the site, it
retries from new random weights until one run reaches the V.

Saves v_fit.png (the data with both fits) and v_loss.png (loss vs epoch for both).
"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
data = np.loadtxt(HERE / "annacode-v.tsv", skiprows=1, delimiter="\t")
x, Y = data[:, 1], data[:, 2]
mu, sd = x.mean(), x.std()      # population std, same as Excel STDEVP and Anna's code
x_hat = (x - mu) / sd


# ---- Part 1: one neuron + ReLU ----
def one_neuron(m=1.0, b=1.0, lr=0.1, epochs=50):
    history = []
    for epoch in range(epochs + 1):
        pre = m * x_hat + b                   # neuron
        post = np.maximum(0, pre)             # ReLU
        relu_slope = (pre > 0) * 1.0          # ReLU'(pre)
        err = Y - post
        dm = np.mean(-2 * err * relu_slope * x_hat)   # chain rule
        db = np.mean(-2 * err * relu_slope)
        history.append((epoch, m, b, dm, db, np.mean(err ** 2)))
        m -= lr * dm
        b -= lr * db
    return history


h1 = one_neuron(epochs=3000)            # same length as part 2 so the loss curves line up
print("Part 1: one neuron + ReLU (epochs 0-4 = spreadsheet iterations 1-5, epoch 5 = 'after 5')")
print(f"{'epoch':>5} {'m':>9} {'b':>9} {'dm':>9} {'db':>9} {'loss':>9}")
for row in h1[:6] + h1[-1:]:
    print(f"{row[0]:5d} " + " ".join(f"{v:9.3f}" for v in row[1:]))
m1, b1 = h1[-1][1:3]
print(f"y = ReLU({m1 / sd:.4f}*x + {b1 - m1 * mu / sd:.3f}), on for {(m1 * x_hat + b1 > 0).sum()} of {len(x)} points\n")


# ---- Part 2: hidden layer of 2 ReLU neurons -> output neuron (no activation) ----
# Trained like Anna's code: x and y both standardized (the output has no activation).
my, sy = Y.mean(), Y.std()
y_hat_t = (Y - my) / sy


def two_neurons(seed, lr=0.1, epochs=3000):
    rng = np.random.default_rng(seed)
    w = rng.uniform(-1, 1, 2)                 # hidden weights (Anna: uniform(-1,1)/sqrt(fan_in), fan_in = 1)
    c = np.zeros(2)                           # hidden biases
    v = rng.uniform(-1, 1, 2) / np.sqrt(2)    # output weights (fan_in = 2)
    d = 0.0                                   # output bias
    losses = []
    for _ in range(epochs):
        pre = np.outer(x_hat, w) + c          # each column is one hidden neuron
        h = np.maximum(0, pre)
        out = h @ v + d
        err = y_hat_t - out
        losses.append(np.mean(err ** 2) * sy ** 2)    # report MSE in raw y units
        g = -2 * err / len(x)                 # dLoss/dout per point (summed below = averaged)
        dv, dd = h.T @ g, g.sum()
        g_pre = np.outer(g, v) * (pre > 0)    # error sent back through v, then through ReLU'
        dw, dc = (g_pre * x_hat[:, None]).sum(0), g_pre.sum(0)
        v -= lr * dv; d -= lr * dd; w -= lr * dw; c -= lr * dc
    return w, c, v, d, losses


for seed in range(20):
    w, c, v, d, h2 = two_neurons(seed)
    if h2[-1] < 6:                            # noise level: the site adds noise with std 2, so MSE ~4
        break
    print(f"Part 2: random start {seed} got stuck at loss {h2[-1]:.0f}, randomizing again")
print(f"Part 2: start {seed} reached the V, loss {h2[-1]:.2f}")
# Fold back into raw units: what you would type into Anna's site
w_raw, c_raw = w / sd, c - w * mu / sd
v_raw, d_raw = v * sy, my + d * sy
for j in range(2):
    print(f"  hidden neuron {j + 1}: ReLU({w_raw[j]:.4f}*x + {c_raw[j]:.3f}), output weight {v_raw[j]:.4f}")
print(f"  output bias {d_raw:.3f}")
print(f"  ramps: slope {w_raw[0] * v_raw[0]:.3f} starting at x = {-c_raw[0] / w_raw[0]:.1f}, "
      f"slope {w_raw[1] * v_raw[1]:.3f} starting at x = {-c_raw[1] / w_raw[1]:.1f}")


def predict_two(xs):
    return np.maximum(0, np.outer(xs, w_raw) + c_raw) @ v_raw + d_raw


# ---- Plots ----
xs = np.linspace(x.min(), x.max(), 300)
fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.scatter(x, Y, s=12, color="0.55", label="V data (Anna's code)")
ax.plot(xs, np.maximum(0, m1 / sd * xs + (b1 - m1 * mu / sd)), color="tab:red", label="1 neuron + ReLU")
ax.plot(xs, predict_two(xs), color="tab:blue", label="2 ReLU neurons + output")
ax.set(title="Data and fit", xlabel="x", ylabel="output 1")
ax.legend()
fig.tight_layout()
fig.savefig(HERE / "v_fit.png", dpi=120)

fig, ax = plt.subplots(figsize=(6.5, 4.5))
ax.plot([r[5] for r in h1], color="tab:red", label="1 neuron + ReLU")
ax.plot(h2, color="tab:blue", label="2 ReLU neurons + output")
ax.set(title="Loss vs epoch", xlabel="epoch", ylabel="MSE (output units²)", yscale="log")
ax.legend()
fig.tight_layout()
fig.savefig(HERE / "v_loss.png", dpi=120)
print("\nsaved v_fit.png and v_loss.png")
