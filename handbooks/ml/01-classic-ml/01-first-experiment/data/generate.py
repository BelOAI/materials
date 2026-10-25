"""Воспроизводимые синтетические заказы для практики занятия 1.1.

Запуск из корня репозитория: py -3 handbooks/ml/01-classic-ml/01-first-experiment/data/generate.py
"""

import csv
import json
import random
from pathlib import Path


HERE = Path(__file__).resolve().parent
RNG = random.Random(20261025)


def orders(prefix, count):
    for number in range(1, count + 1):
        height = RNG.randint(3, 12)
        colors = RNG.randint(1, 4)
        # Скрытые площади сечений и переключения дают разные ответы
        # даже для фигурок с одинаковыми доступными признаками.
        area_sum = 10 * (2 * height + RNG.randint(-5, 5))
        switches = colors - 1 + RNG.randint(0, 1) if colors > 1 else 0
        minutes = 8 + area_sum // 10 + 3 * switches
        yield [f"{prefix}{number:04}", height, colors, minutes]


def save(name, header, rows):
    with (HERE / name).open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


train = list(orders("tr", 1000))
test = list(orders("te", 1000))
save("train.csv", ["order_id", "height_cm", "colors", "minutes"], train)
save("test.csv", ["order_id", "height_cm", "colors", "minutes"],
     [row[:3] + ["?"] for row in test])
save("test_answers.csv", ["order_id", "minutes"], [[row[0], row[3]] for row in test])


def cell(kind, source, number):
    result = {"cell_type": kind, "id": f"cell-{number:03}", "metadata": {},
              "source": source.splitlines(keepends=True)}
    if kind == "code":
        result.update(execution_count=None, outputs=[])
    return result


cells = [
    cell("markdown", "# Практика: первый эксперимент\n\nАвтор: Алексей Толстиков. CC BY 4.0.\n\n"
         "Положите ноутбук рядом с папкой `data`. У каждого CSV-файла 1000 строк с заказами. "
         "В `test.csv` ответы скрыты знаком `?`. Сначала зафиксируйте прогноз по обучению; "
         "затем открывайте `test_answers.csv` для проверки.\n", 0),
    cell("markdown", "## 1. Постоянный прогноз\n\nЗагрузите данные через pandas. "
         "Найдите медиану `minutes` только в `train.csv`, сделайте постоянный прогноз "
         "и посчитайте обучающую MAE.\n", 1),
    cell("code", "import pandas as pd\n\ntrain = pd.read_csv('data/train.csv')\n"
         "test = pd.read_csv('data/test.csv')\n"
         "print(len(train), len(test))\n", 2),
    cell("code", "# Ваш код: медиана, прогноз и MAE на обучении.\n", 3),
    cell("markdown", "## 2. Зафиксируйте оба правила\n\nПримените числовой прогноз "
         "к тесту. Только по обучающим временам найдите самый частый ответ на вопрос "
         "«успеет ли заказ за 30 минут?» и дайте его всем тестовым заказам. "
         "Пока не открывайте `test_answers.csv`.\n", 4),
    cell("code", "# Ваш код: постоянный прогноз времени и самый частый класс.\n", 5),
    cell("markdown", "## 3. Проверьте оба прогноза\n\nТеперь загрузите "
         "`data/test_answers.csv`, сопоставьте строки по `order_id` и вычислите "
         "тестовую MAE и accuracy. Числа для самопроверки приведены в статье.\n", 6),
    cell("code", "# Ваш код: соединение по order_id, тестовая MAE и accuracy.\n", 7),
]
notebook = {"cells": cells, "metadata": {"authors": [{"name": "Алексей Толстиков"}],
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.14"}},
            "nbformat": 4, "nbformat_minor": 5}
(HERE.parent / "notebook.ipynb").write_bytes(
    (json.dumps(notebook, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
