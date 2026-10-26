"""Воспроизводимые синтетические заказы для занятия 1.7."""

import csv
import random
from pathlib import Path


HERE = Path(__file__).resolve().parent


def orders(seed, prefix, count):
    rng = random.Random(seed)
    for number in range(1, count + 1):
        height = rng.randint(3, 12)
        colors = rng.randint(1, 4)
        plastic = 2 * height + height * (colors >= 3) + rng.randint(-4, 4)
        minutes = (8 + plastic + 3 * (colors - 1) + rng.randint(-3, 3)
                   + (12 if rng.random() < 0.06 else 0))
        yield [f"{prefix}{number:04}", height, colors, plastic, minutes]


def write_csv(filename, header, rows):
    with (HERE / filename).open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


train = list(orders(19, "tr", 300))
new = list(orders(20, "new", 100))
write_csv("train.csv", ["order_id", "height_cm", "colors", "plastic_cm3", "minutes"], train)
write_csv("new.csv", ["order_id", "height_cm", "colors", "plastic_cm3", "minutes"],
          [row[:4] + ["?"] for row in new])
write_csv("new_answers.csv", ["order_id", "minutes"], [[row[0], row[4]] for row in new])
