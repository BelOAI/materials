"""Построить SVG-карты областей прогноза для учебных деревьев."""
from pathlib import Path

from sklearn.tree import DecisionTreeRegressor

def make_minutes(h, c, shape):
    area = 20 * h + 10 * h * (c >= 3) + 10 * shape
    return 8 + 0.1 * area + 3 * (c - 1)

train = [(h, c, shape)
         for h in range(2, 13)
         for c in range(1, 5)
         for shape in (-2, 0, 2)]
features = [(h, c) for h, c, _ in train]
answers = [make_minutes(h, c, shape) for h, c, shape in train]
large_models = {
    depth: DecisionTreeRegressor(max_depth=depth, random_state=0).fit(
        features, answers
    )
    for depth in (2, 4)
}

import matplotlib.pyplot as plt
import numpy as np

heights = np.linspace(2, 12, 401)
grid = np.array([(h, c) for c in range(1, 5) for h in heights])
fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)

for ax, depth in zip(axes, (2, 4)):
    forecasts = large_models[depth].predict(grid).reshape(4, -1)
    picture = ax.imshow(forecasts, origin="lower", aspect="auto",
                        extent=(2, 12, 0.5, 4.5), cmap="viridis",
                        vmin=12, vmax=52, interpolation="nearest")
    ax.scatter([h for h in range(2, 13) for c in range(1, 5)],
               [c for h in range(2, 13) for c in range(1, 5)],
               s=12, facecolors="none", edgecolors="white", linewidths=0.6)
    ax.set(title=f"Глубина {depth}", xlabel="Высота, см",
           yticks=(1, 2, 3, 4))
axes[0].set_ylabel("Число цветов")
fig.colorbar(picture, ax=axes, label="Прогноз, мин")
output = Path(__file__).parent / "media/decision-regions.svg"
fig.savefig(output, bbox_inches="tight")
output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
