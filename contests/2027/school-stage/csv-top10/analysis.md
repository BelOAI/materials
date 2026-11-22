Чтобы запустить листинг, скачайте <a href="media/players.csv" download>учебный файл <code>players.csv</code></a> со страницы задачи и сохраните его как `data/players.csv` рядом со скриптом. В файле 12 вымышленных игроков, среди них есть игроки с равными очками.

**Идея задачи.**

1. посчитать `score = 3 × goals + assists`;
2. отсортировать по пяти ключам ровно в том порядке, который задан в условии;
3. записать десять строк в CSV точно в заданном формате и упаковать в `submission.zip`.

При этом почти все потери баллов происходят из-за пропущенного ключа сортировки или нарушенного формата CSV.

### Шаг 1. Читаем таблицу и считаем очки

Читаем CSV через `DictReader`, чтобы обращаться к столбцам по имени. Числа приходят строками, поэтому переводим их в `int`: иначе `"10" < "9"`.

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
```

### Шаг 2. Сортировка по пяти ключам

`sort` в Python сравнивает кортежи слева направо, поэтому кортеж ключей просто повторяет условие. Очки и голы нужны по убыванию, поэтому ставим минус, чтобы сортировалось наоборот. Минуты, имя и страну сортируем по возрастанию и оставляем как есть.

```python
players.sort(key=lambda row: (
    -row["score"], -row["goals"], row["minutes_played"],
    row["player"], row["country"],
))
```

На учебном файле получается такая десятка:

```text
rank  player  country  minutes  goals  assists  score
   1  Miro    Croatia      140      3        0      9
   2  Carlo   Italy        120      2        1      7
   3  Dario   Italy        160      2        0      6
   4  Noah    Canada       160      2        0      6
   5  Bruno   Spain        180      2        0      6
   6  Alex    France       300      1        3      6
   7  Leo     Spain        210      1        2      5
   8  Tomas   Chile         90      1        1      4
   9  Emil    Denmark      200      1        0      3
  10  Adam    Poland       100      0        2      2
```

У четырёх игроков по 6 очков. Алекс среди них последний: у него один гол. Бруно ниже Дарио и Ноя: голов столько же, но минут больше. Дарио и Ной совпадают по всем числам, их разводит только имя.

НО:

- если сортировать только по `score`, равные игроки остаются в порядке файла: на учебной таблице это 92 балла вместо 100;
- если забыть про минуты, Бруно остаётся выше Дарио и Ноя: 96 баллов;
- если сортировать минуты по убыванию (например, `ascending=False` для всех столбцов в pandas), результат тот же: 96 баллов;
- если остановиться на минутах, Дарио и Ной встанут в порядке файла, и Ной окажется выше: 98 баллов. При другой перестановке строк ответ изменится: без имени и страны сортировка неоднозначна.

### Шаг 3. Записываем CSV и архив

Добавляем ранги и записываем только нужные поля в заданном порядке. `newline=""` нужен модулю `csv`, а `lineterminator="\n"` фиксирует переносы строк. Файл кладём в корень архива.

```python
fields = ["rank", "player", "country", "minutes_played", "goals", "assists", "score"]
with open("top10.csv", "w", encoding="utf-8", newline="") as result:
    writer = csv.DictWriter(result, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for rank, row in enumerate(players[:10], start=1):
        writer.writerow({"rank": rank, **{field: row[field] for field in fields[1:]}})

with ZipFile("submission.zip", "w", compression=ZIP_DEFLATED) as archive:
    archive.write("top10.csv")
```

НО (здесь теряются уже не отдельные баллы, а вся посылка):

- `DataFrame.to_csv("top10.csv")` без `index=False` добавляет лишний первый столбец, и заголовок перестаёт совпадать;
- если заархивировать папку с файлом, `top10.csv` окажется не в корне архива.

Сортировка занимает $O(n\log n)$ времени и до $O(n)$ дополнительной памяти для $n$ строк.
