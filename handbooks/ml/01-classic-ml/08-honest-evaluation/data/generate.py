"""Независимые синтетические заказы для итоговой проверки занятия 1.8."""

import csv
import random
from pathlib import Path


HERE = Path(__file__).resolve().parent
rng = random.Random(21)
orders = []
for number in range(1, 101):
    height = rng.randint(3, 12)
    colors = rng.randint(1, 4)
    plastic = 2 * height + height * (colors >= 3) + rng.randint(-4, 4)
    minutes = (8 + plastic + 3 * (colors - 1) + rng.randint(-3, 3)
               + (12 if rng.random() < 0.06 else 0))
    orders.append([f"final{number:04}", height, colors, plastic, minutes])

with (HERE / "final.csv").open("w", encoding="utf-8", newline="") as output:
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["order_id", "height_cm", "colors", "plastic_cm3", "minutes"])
    writer.writerows([row[:4] + ["?"] for row in orders])

with (HERE / "final_answers.csv").open("w", encoding="utf-8", newline="") as output:
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["order_id", "minutes"])
    writer.writerows([[row[0], row[4]] for row in orders])
