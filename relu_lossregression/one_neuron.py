"""One neuron + ReLU, trained by gradient descent in PyTorch.

    y = ReLU(m * x_hat + b),   x_hat = (x - mean) / std

Full-batch SGD on mean squared error, starting from m = b = 1, so every
epoch here matches one row of v_fit_5_iterations.xlsx (epochs 0-4 = iterations 1-5, epoch 5 = "after 5").
"""
from pathlib import Path
import numpy as np
import torch
from torch import nn

HERE = Path(__file__).parent
LEARNING_RATE = 0.1
EPOCHS = 50
M0, B0 = 1.0, 1.0   # not 0: ReLU'(0) = 0, so a neuron starting at 0 never moves

data = np.loadtxt(HERE / "annacode-v.tsv", skiprows=1, delimiter="\t")
x_raw, y_raw = data[:, 1], data[:, 2]
mu, sd = x_raw.mean(), x_raw.std()          # population std, same as Excel STDEVP
X = torch.tensor((x_raw - mu) / sd).reshape(-1, 1)
Y = torch.tensor(y_raw).reshape(-1, 1)

# 1 input -> 1 neuron (weight m, bias b) -> ReLU activation
model = nn.Sequential(nn.Linear(1, 1), nn.ReLU()).double()
with torch.no_grad():
    model[0].weight.fill_(M0)
    model[0].bias.fill_(B0)
loss_fn = nn.MSELoss()                      # mean((pred - Y)^2)
opt = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE)

history = []
for epoch in range(EPOCHS + 1):
    pred = model(X)                         # forward pass
    loss = loss_fn(pred, Y)
    opt.zero_grad()
    loss.backward()                         # chain rule: dLoss/dm, dLoss/db
    m, b = model[0].weight.item(), model[0].bias.item()
    dm, db = model[0].weight.grad.item(), model[0].bias.grad.item()
    history.append((epoch, m, b, dm, db, loss.item()))
    if epoch < EPOCHS:
        opt.step()                          # m -= lr*dm, b -= lr*db

print(f"{'epoch':>5} {'m':>10} {'b':>10} {'dm':>10} {'db':>10} {'loss':>10}")
for row in history[:3] + history[-1:]:
    print(f"{row[0]:5d} " + " ".join(f"{v:10.4f}" for v in row[1:]))

m, b = history[-1][1:3]
m_raw, b_raw = m / sd, b - m * mu / sd
active = (m * X + b > 0).sum().item()
print(f"\ny = ReLU({m_raw:.4f} * x + {b_raw:.4f})   loss {history[-1][5]:.2f}")
print(f"ReLU is 'on' for {active} of {len(X)} points")

try:
    import matplotlib.pyplot as plt
except ImportError:
    raise SystemExit
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
a1.plot([h[0] for h in history], [h[5] for h in history])
a1.set(title="Loss vs epoch", xlabel="epoch", ylabel="MSE")
xs = np.linspace(x_raw.min(), x_raw.max(), 200)
a2.scatter(x_raw, y_raw, s=12, label="data")
a2.plot(xs, np.maximum(0, m_raw * xs + b_raw), "r", label="ReLU(m·x + b)")
a2.set(title="Data and one-neuron fit", xlabel="x", ylabel="output 1")
a2.legend()
fig.tight_layout()
fig.savefig(HERE / "one_neuron_fit.png", dpi=120)
print("saved one_neuron_fit.png")
