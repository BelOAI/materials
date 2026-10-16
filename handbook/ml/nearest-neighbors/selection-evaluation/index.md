## Чему научимся

Проводить выбор подготовки и параметров на validation и однократную финальную оценку.

## Протокол эксперимента

Нужно сравнить не только k, но и подготовку признаков. Сначала отделим train, validation и test. На train определим минимумы и диапазоны. По validation выберем сочетание масштаба и k, затем один раз оценим зафиксированное решение на test.

Скачайте [gliders.csv](../../../data/gliders.csv) в рабочую папку. Сначала повторим чтение и функцию точности, чтобы весь опыт можно было выполнить в отдельном ноутбуке.

```python
import csv
with open("gliders.csv", encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))
for row in rows:
    row["span_cm"] = float(row["span_cm"])
    row["mass_g"] = float(row["mass_g"])
train = [row for row in rows if row["split"] == "train"]
validation = [row for row in rows if row["split"] == "validation"]
test = [row for row in rows if row["split"] == "test"]
assert (len(train), len(validation), len(test)) == (12, 6, 6)
ids = [row["id"] for row in rows]
assert len(set(ids)) == len(ids)  # Каждый id относится к одной строке.

def accuracy(expected, predicted):
    if len(expected) == 0 or len(expected) != len(predicted):
        raise ValueError("Нужны непустые списки одинаковой длины")
    correct = 0
    for left, right in zip(expected, predicted):
        if left == right:
            correct += 1
    return correct / len(expected)
```

## Подготовка и модель

Функция `prepare` отделяет признаки от ответа, `fit_scale` получает обучающие минимум и диапазон по двум координатам, `transform` применяет сохранённые значения. Условное выражение `width if width != 0 else 1` выбирает width при ненулевом диапазоне, иначе 1. Это короткая запись знакомого if/else. Эти функции рассчитаны ровно на два признака: пустой train и другой размер объекта отклоняем до вычислений. В `predict` также проверяем целочисленное k, как в предыдущем уроке.

```python
def fit_scale(examples):
    if len(examples) == 0:
        raise ValueError("Для масштаба нужны обучающие объекты")
    for row in examples:
        if len(row["x"]) != 2:
            raise ValueError("Ожидались два признака: размах и масса")
    minimum = []
    ranges = []
    for j in range(2):
        values = [row["x"][j] for row in examples]
        left = min(values)
        width = max(values) - left
        minimum.append(left)
        ranges.append(width if width != 0 else 1)
    return minimum, ranges

def transform(point, scale):
    if len(point) != 2:
        raise ValueError("Ожидались два признака: размах и масса")
    minimum, ranges = scale
    return [(point[j] - minimum[j]) / ranges[j] for j in range(2)]

def prepare(rows):
    return [{"id": row["id"], "x": [row["span_cm"], row["mass_g"]], "y": row["flight"]} for row in rows]

def predict(query, examples, k):
    if type(k) != int or not 1 <= k <= len(examples):
        raise ValueError("k должен быть целым от 1 до числа обучающих объектов")
    if len(query) == 0:
        raise ValueError("Нужен хотя бы один признак")
    for row in examples:
        if len(row["x"]) != len(query):
            raise ValueError("Число признаков должно совпадать")
    ranked = []
    for row in examples:
        squared_distance = 0
        for j in range(len(query)):
            squared_distance += (query[j] - row["x"][j]) ** 2
        ranked.append((squared_distance, row["id"], row["y"]))
    ranked.sort()
    votes = {}
    for distance, identifier, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    winner = None
    for label in sorted(votes):
        if winner is None or votes[label] > votes[winner]:
            winner = label
    return winner

raw_train = prepare(train)
raw_validation = prepare(validation)
raw_test = prepare(test)
scale = fit_scale(raw_train)
```

## Разобранный пример: выбираем вариант

Перебираем масштабированные данные первыми, k — по возрастанию. При равных оценках оставляем первого победителя: заранее предпочитаем масштабирование и меньшее k. Внутренний цикл не обращается к тестовым ответам.

```python
best = None
for scaled in [True, False]:
    fitted = []
    for row in raw_train:
        point = transform(row["x"], scale) if scaled else row["x"]
        fitted.append({"id": row["id"], "x": point, "y": row["y"]})
    for k in [1, 3, 5]:
        predicted = []
        for row in raw_validation:
            point = transform(row["x"], scale) if scaled else row["x"]
            predicted.append(predict(point, fitted, k))
        score = accuracy([row["y"] for row in raw_validation], predicted)
        if best is None or score > best["score"]:
            best = {"scaled": scaled, "k": k, "score": score, "examples": fitted}
assert best["scaled"] and best["k"] == 1 and best["score"] == 1
```

## Финальная оценка

```python
predicted = []
for row in raw_test:
    point = transform(row["x"], scale) if best["scaled"] else row["x"]
    predicted.append(predict(point, best["examples"], best["k"]))
assert accuracy([row["y"] for row in raw_test], predicted) == 1
```

На этой простой вымышленной таблице KNN дал 6 верных ответов из 6, постоянный baseline — 3. Одна ошибка меняет долю на 1/6. Такой опыт проверяет ход вычислений, но не доказывает качество на настоящих планерах. После просмотра test параметры не меняем; новый выбор потребует новой независимой проверки.

## Разобранный пример: фиксируем весь победивший вариант

Проследим первый тестовый объект g19: размах 15 см, масса 10 г. Минимумы train равны (12,8), диапазоны — (15,30). Его новые координаты — ((15−12)/15,(10−8)/30)=(0.2,1/15). Далее `predict` сравнивает их с уже масштабированными обучающими точками и при k=1 берёт метку ближайшей. Ответ g19 не участвовал ни в расчёте масштаба, ни в выборе k.

В сохранённом best находятся готовые обучающие описания, score validation и выбранное k. Итоговый тест получает ровно эту процедуру, включая обучающий минимум и диапазон. Если после просмотра теста заново выбрать масштаб или seed, нужно признать новый подбор, а не переносить прежнюю оценку на изменённое решение.

## Типичные ошибки

Не переучивайте масштаб на test и не меняйте вариант после его просмотра. Оценка относится ко всей зафиксированной процедуре, а не только числу k.

## Задачи

### 1. Базовая

По какой части выбирают k?

<details>
<summary>Подсказка</summary>

Тест используется в конце.

</details>

<details>
<summary>Решение</summary>

По validation. Train задаёт примеры, а test остаётся для однократной итоговой оценки.

</details>

### 2. Базовая

Какая часть задаёт масштаб?

<details>
<summary>Подсказка</summary>

Её статистики доступны модели при обучении.

</details>

<details>
<summary>Решение</summary>

Train: минимумы и диапазоны сохраняются после обучения и применяются к остальным частям.

</details>

### 3. Прикладная

Преобразуйте 15 и 40 при обучающем минимуме 10 и диапазоне 20.

<details>
<summary>Подсказка</summary>

Вычтите минимум и разделите.

</details>

<details>
<summary>Решение</summary>

(15−10)/20=0.25 и (40−10)/20=1.5. Второе значение допустимо и находится выше обучающего диапазона.

</details>

### 4. Прикладная

Сколько ошибок допустимо для accuracy 5/6 на шести объектах?

<details>
<summary>Подсказка</summary>

Верны пять.

</details>

<details>
<summary>Решение</summary>

Из шести верны пять, значит неверен один. Это ровно одна ошибка, а не 5/6 ошибки.

</details>

### 5. Олимпиадная
Массу всех обучающих объектов и запроса перевели из граммов в килограммы, после чего заново вычислили min-max по train. Докажите, что нормированные массы сохранятся, если обучающий диапазон массы ненулевой. Что нужно отдельно оговорить для постоянного признака?

<details>
<summary>Подсказка</summary>

Подставьте общий положительный множитель в числитель и знаменатель.

</details>

<details>
<summary>Решение</summary>

Пусть c=0.001. Тогда (cx−c·min)/(c·max−c·min)=(x−min)/(max−min): множитель c сокращается. Ненулевой диапазон нужен, чтобы знаменатель был определён. Если max=min, эта формула неприменима: требуется отдельное соглашение о постоянном признаке. Например, замена нулевого диапазона на 1 не даёт такого же доказательства неизменности нормированных координат запроса.

</details>

### 6. Олимпиадная

Можно ли после просмотра теста выбрать другой k и сообщить прежнюю тестовую оценку как итоговую?

<details>
<summary>Подсказка</summary>

Оценка относится к конкретному зафиксированному решению.

</details>

<details>
<summary>Решение</summary>

Нет. Решение изменилось, а тест уже участвовал в разработке. Нужна честная новая проверка.

</details>

## Итоги

По validation выбрана вся процедура: масштаб по train и k=1. На шести тестовых объектах она дала шесть верных ответов; это результат одного зафиксированного учебного опыта, а не доказательство качества на настоящих полётах.

## Самопроверка

Проследите один объект от сырых полей через сохранённый масштаб к голосам. Какие данные участвовали в выборе, а какие только в финальной оценке?

Для перехода дальше достаточно базовых и прикладных задач; олимпиадные можно отложить.
