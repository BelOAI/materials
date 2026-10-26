"""Строит схему ошибок по данным занятия 1.7."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.tree import DecisionTreeRegressor


ROOT = Path(__file__).resolve().parent
train = pd.read_csv(ROOT / "data/train.csv")
new = pd.read_csv(ROOT / "data/new.csv")
answers = pd.read_csv(ROOT / "data/new_answers.csv")
checked = new.merge(answers, on="order_id", validate="one_to_one", suffixes=("_hidden", ""))

variants = [
    ("2 признака\nглубина 4", ["height_cm", "colors"], 4, 1),
    ("3 признака\nглубина 4", ["height_cm", "colors", "plastic_cm3"], 4, 1),
    ("3 признака\nбез ограничения", ["height_cm", "colors", "plastic_cm3"], None, 1),
    ("3 признака\n≥5 в листе", ["height_cm", "colors", "plastic_cm3"], None, 5),
]
train_errors = []
new_errors = []
for _, features, depth, leaf in variants:
    model = DecisionTreeRegressor(max_depth=depth, min_samples_leaf=leaf, random_state=0)
    model.fit(train[features], train["minutes"])
    train_errors.append(mean_absolute_error(train["minutes"], model.predict(train[features])))
    new_errors.append(mean_absolute_error(checked["minutes"], model.predict(checked[features])))

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none"})
fig, ax = plt.subplots(figsize=(9, 3.8))
positions = np.arange(len(variants))
width = 0.35
bars_train = ax.bar(positions - width / 2, train_errors, width, label="Обучение", color="#2563eb")
bars_new = ax.bar(positions + width / 2, new_errors, width, label="Новые заказы", color="#ea580c")
ax.bar_label(bars_train, labels=[f"{value:.2f}" for value in train_errors], padding=3)
ax.bar_label(bars_new, labels=[f"{value:.2f}" for value in new_errors], padding=3)
ax.set_xticks(positions, [name for name, *_ in variants])
ax.set_ylabel("MAE, минуты")
ax.set_ylim(0, 4.7)
ax.grid(axis="y", color="#cbd5e1", linewidth=0.7)
ax.set_axisbelow(True)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(ncol=2, loc="upper right", frameon=False)
fig.tight_layout()
output = ROOT / "media/model-errors.svg"
output.parent.mkdir(exist_ok=True)
fig.savefig(output, format="svg")
plt.close(fig)
output.write_bytes(output.read_bytes().replace(b"\r\n", b"\n"))
