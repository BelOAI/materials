В таблице нужно вывести первые десять игроков после сортировки по нескольким ключам. В Python `sort` умеет сравнивать кортежи слева направо. Для убывающего порядка числовых показателей используем отрицательные значения; для минут и текста оставляем обычный порядок.

Сначала читаем CSV через `DictReader`, чтобы обращаться к столбцам по имени. Поле `score` вычисляем из голов и передач. Кортеж ключей в точности повторяет правила условия: очки и голы по убыванию, минуты по возрастанию, затем имя и страна.

После сортировки добавляем ранги и записываем только нужные поля в заданном порядке. `newline=""` нужен модулю `csv`, а `lineterminator="\n"` фиксирует переносы строк. В конце упаковываем один файл в корень `submission.zip`.

Проверка решения — это не только десять имён: каждое поле строки должно совпадать, а правильная десятка должна идти в том же порядке, что и эталон. Поэтому порядок ключей сортировки и заголовок CSV нельзя менять. Сортировка занимает $O(n\log n)$ времени и до $O(n)$ дополнительной памяти для $n$ строк.

```python
import csv
from zipfile import ZIP_DEFLATED, ZipFile

with open("data/players.csv", encoding="utf-8-sig", newline="") as source:
    players = list(csv.DictReader(source))

for row in players:
    row["minutes_played"] = int(row["minutes_played"])
    row["goals"] = int(row["goals"])
    row["assists"] = int(row["assists"])
    row["score"] = 3 * row["goals"] + row["assists"]

players.sort(key=lambda row: (
    -row["score"], -row["goals"], row["minutes_played"],
    row["player"], row["country"],
))

fields = ["rank", "player", "country", "minutes_played", "goals", "assists", "score"]
with open("top10.csv", "w", encoding="utf-8", newline="") as result:
    writer = csv.DictWriter(result, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for rank, row in enumerate(players[:10], start=1):
        writer.writerow({"rank": rank, **{field: row[field] for field in fields[1:]}})

with ZipFile("submission.zip", "w", compression=ZIP_DEFLATED) as archive:
    archive.write("top10.csv")
```
