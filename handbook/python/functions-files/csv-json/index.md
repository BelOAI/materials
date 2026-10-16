## Чему научимся

Читать структурированные данные и обнаруживать нарушения схемы до вычислений.

## Подготовка примеров

Используем знакомые `Path` и `TemporaryDirectory`: все файлы создаются во временной папке, поэтому существующие данные не перезаписываются.

```python
from pathlib import Path
from tempfile import TemporaryDirectory
```

## CSV: строки таблицы

CSV хранит таблицу с разделителями и правилами кавычек. Например, файл с двумя полями может выглядеть так:

```text
id,span_cm
a,12
b,22
```

Первая строка — заголовок. Не разбивайте строки вручную по запятой: запятая может быть частью поля в кавычках. `csv.DictReader` читает заголовок и выдаёт строки как словари. Значения пока остаются строками: `"22"` нужно превратить в число.

**Схема данных** — договорённость об именах полей, их типах и допустимых значениях. В нашем файле нужны поля `id` и `span_cm` в этом порядке, непустой уникальный идентификатор и положительный конечный размах.

## Разобранный пример: проверяем измерения

Сначала опишем чтение отдельной функцией. Свойство (атрибут) объекта — значение, доступное через точку; в отличие от вызова метода, для чтения свойства круглые скобки не нужны. У `DictReader` свойство `fieldnames` хранит названия столбцов. Если полей в строке слишком много, лишние попадут под ключ `None`; если слишком мало — у недостающего поля значение будет `None`. `row.values()` позволяет проверить значения словаря. Проверку числа полей выполняем **до** обращения к конкретному полю.

`enumerate(..., start=2)` нумерует записи после заголовка, начиная с 2. В нашем простом CSV каждая запись занимает одну строку. `float` принимает и специальные строки `"nan"` и `"inf"`: неопределённое числовое значение и бесконечность. `math.isfinite` возвращает `True` только для конечного числа, исключая оба случая. Пустое поле не равно нулю: отсутствие измерения нельзя автоматически заменять нулевой массой или размахом.

```python
import csv
import math

def read_measurements(path):
    rows = []
    seen = set()
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["id", "span_cm"]:
            raise ValueError("Ожидались поля id, span_cm в этом порядке")
        for line_number, row in enumerate(reader, start=2):
            if None in row or None in row.values():
                raise ValueError(f"Запись {line_number}: неверное число полей")
            identifier = row["id"].strip()
            try:
                span = float(row["span_cm"])
            except ValueError:
                raise ValueError(f"Запись {line_number}: размах не число")
            if not identifier or identifier in seen:
                raise ValueError(f"Запись {line_number}: пустой или повторный id")
            if not math.isfinite(span) or span <= 0:
                raise ValueError(f"Запись {line_number}: нужен конечный размах > 0")
            seen.add(identifier)
            rows.append({"id": identifier, "span_cm": span})
    return rows
```

Проследите одну запись: `"12"` превращается в `12.0`, проходит проверку знака, затем попадает в результат. Строка с `"nan"` преобразуется без ошибки, но будет отклонена проверкой `isfinite`. При нарушении схемы функция останавливается с объяснением; строки не исчезают молча.

Теперь создадим файл и применим функцию. Это два вымышленных измерения для обучения работе с форматом, а не реальные полёты. `csv.DictWriter` записывает словари по заданным `fieldnames`; `writeheader` пишет заголовок, `writerows` — строки. `newline=""` оставляет обработку переводов строк модулю CSV и используется и при записи, и при чтении.

```python
with TemporaryDirectory() as folder:
    path = Path(folder) / "measurements.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["id", "span_cm"])
        writer.writeheader()
        writer.writerows([
            {"id": "a", "span_cm": 12},
            {"id": "b", "span_cm": 22},
        ])
    rows = read_measurements(path)
assert rows == [{"id": "a", "span_cm": 12.0}, {"id": "b", "span_cm": 22.0}]
print(rows)
```

## JSON: вложенные данные

JSON хранит объекты, массивы, строки, числа, логические значения и `null`. В Python объект JSON читается как словарь, массив как список, `null` как `None`. `json.dump` записывает в файл, `json.load` читает; варианты `dumps` и `loads` работают со строкой.

`ensure_ascii=False` сохраняет кириллицу читаемой; `allow_nan=False` запрещает запись нечисловых значений и бесконечностей как нестандартного JSON.

```python
import json

config = {"seed": 17, "features": ["span_cm"], "comment": "учебный опыт"}
encoded = json.dumps(config, ensure_ascii=False, allow_nan=False)
restored = json.loads(encoded)
assert restored == config
```

Успешное чтение JSON ещё не проверяет смысл: отдельно проверяйте обязательные ключи, типы и диапазоны. Повреждённый JSON вызывает `json.JSONDecodeError`.

## Проверяем не только правильный файл

Функция должна отклонять повторный идентификатор ещё до вычисления среднего. Создадим неправильный CSV специально и проверим исключение знакомым способом. Запись `except ValueError as error` даёт пойманному исключению имя `error`, чтобы напечатать его сообщение.

```python
with TemporaryDirectory() as folder:
    path = Path(folder) / "repeated.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write("id,span_cm\na,12\na,22\n")
    try:
        read_measurements(path)
    except ValueError as error:
        print(error)  # Запись 3: пустой или повторный id
    else:
        raise AssertionError("Повторный id не обнаружен")
```

Первая строка данных допустима, вторая содержит уже встреченный `id`. Проверка числа полей, преобразование числа и проверка уникальности отвечают за разные нарушения.

## Задачи

### 1. Базовая

Чем JSON null отличается от нуля?

<details>
<summary>Подсказка</summary>

После чтения у них разные значения и типы.

</details>

<details>
<summary>Решение</summary>

null превращается в None, ноль — в число 0.

</details>

### 2. Базовая

Почему числа CSV сначала являются строками?

<details>
<summary>Подсказка</summary>

CSV не задаёт числовые типы полей.

</details>

<details>
<summary>Решение</summary>

Нужны преобразования по схеме, например float для размаха.

</details>

### 3. Прикладная

Проверьте размахи «12.5», пустую строку, «nan», «-2».

<details>
<summary>Подсказка</summary>

Преобразование и проверка конечности — разные шаги.

</details>

<details>
<summary>Решение</summary>

```python
def valid_span(text):
    try:
        value = float(text)
    except ValueError:
        return False
    return math.isfinite(value) and value > 0
assert [valid_span(s) for s in ["12.5", "", "nan", "-2"]] == [True, False, False, False]
```

</details>

### 4. Прикладная
Проверьте восстановление словаря `{"name": "крыло", "count": 2}` через JSON-строку. Сравните именно значения словарей, а не написание JSON-текста.

<details>
<summary>Подсказка</summary>

Используйте dumps и loads.

</details>

<details>
<summary>Решение</summary>

```python
original = {"name": "крыло", "count": 2}
assert json.loads(json.dumps(original, ensure_ascii=False)) == original
```

</details>

### 5. Олимпиадная

Почему ручной split неверно разбирает поле с запятой в кавычках?

<details>
<summary>Подсказка</summary>

Разделитель внутри кавычек — часть значения.

</details>

<details>
<summary>Решение</summary>

Он не учитывает правила CSV и создаёт лишнее поле. Используйте csv.DictReader.

</details>

### 6. Олимпиадная

Две строки имеют один id и разные массы. Достаточно ли проверки числовых типов?

<details>
<summary>Подсказка</summary>

Типы не проверяют согласованность объектов.

</details>

<details>
<summary>Решение</summary>

Нет. Нужно выяснить смысл повтора и проверить уникальность id либо хранить повторные измерения явно.

</details>

## Итоги

Вы умеете читать CSV и JSON, преобразовывать значения и проверять схему данных.

## Самопроверка

Перечислите разные причины отклонения строки CSV. Почему успешный `float("nan")` ещё не означает допустимое измерение? Какие типы Python получаются из объекта, массива и `null` в JSON?

Для перехода дальше достаточно уверенно решать базовые и прикладные задачи. К олимпиадным можно вернуться позже.
