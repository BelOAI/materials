Сначала оставим только строки, в которых есть X: это покупатели 1, 2, 3, 4, 5, 7, 8 и 10. Затем посчитаем закрашенные клетки в каждом из остальных столбцов в этих строках.

Товар A купили покупатели 1, 2, 4, 7 и 10 — всего пять человек. Товар B купили четыре человека, C — три, D — один. Чаще всего с X встречается **товар A**.

<details><summary>Код Python</summary>

```python
purchases = [
    "XAB", "XA", "XBC", "XAC", "XB",
    "C", "XAD", "XC", "BD", "XAB",
]

counts = {}
for basket in purchases:
    if "X" in basket:
        for product in basket:
            if product != "X":
                counts[product] = counts.get(product, 0) + 1

print(max(counts, key=counts.get))
```

</details>
