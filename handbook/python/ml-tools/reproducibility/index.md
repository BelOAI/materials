## Чему научимся

Повторять эксперимент по сохранённым данным, настройкам, разбиению и окружению.

## Окружение и случайность

Окружение включает версию Python, версии библиотек, операционную систему и устройство вычислений. Введение объясняет виртуальную среду `venv`. Для фиксации установленных пакетов выполните в её терминале `python -m pip freeze > experiment-requirements.txt`; для повторения — `python -m pip install -r experiment-requirements.txt`. Знак `>` сохраняет вывод команды в файл, заменяя его прежнее содержимое. `pip freeze` перечисляет установленные пакеты и версии, а `pip install -r` устанавливает список из файла. Первая команда работает локально, вторая может обращаться к сети при установке пакетов.

Один seed не фиксирует всё: у Python, NumPy и библиотек моделей разные источники случайности. Кроме seed сохраняйте порядок данных и конкретное разбиение. Повторение в другом окружении может дать небольшие численные расхождения; одинаковый seed не гарантирует побитового совпадения на всех устройствах.

## Конфигурация, журнал и артефакты

Конфигурация — параметры опыта до запуска. Журнал — фактические результаты и условия запуска. Артефакты — сохранённые данные, предсказания и другие выходные файлы. Сохраняйте также версию программы: например, идентификатор коммита, если работаете в Git, или копию скрипта.

Не выбирайте лучший seed по проверочному качеству: это тоже подбор параметра. Несколько заранее выбранных seed помогают увидеть разброс, но должны использовать один понятный протокол сравнения.

## Разобранный пример: повторяемый запуск

Набор состоит из 20 вымышленных объектов с одним признаком. Ответ задаётся порогом 10. Мы создаём данные сами и отделяем итоговую проверку до обучения. Это проверка воспроизводимости кода, а не надёжности ML на реальных данных.

`np.arange` создаёт последовательность чисел, `.astype(int)` превращает логическую маску в 0 и 1. Размер `-1` в `reshape(-1, 1)` вычисляется по числу элементов. Разбиение сохраняем индексами: это позволяет проверить, какие именно строки использовались. Индексация `X[train]` выбирает строки по массиву индексов; `y[train]` выбирает ответы тех же объектов. Метод `.tolist()` превращает массив в список обычных чисел, чтобы сохранить его в JSON.

```python
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score

X = np.arange(20, dtype=np.float64).reshape(-1, 1)
y = (X[:, 0] >= 10).astype(int)
config = {"seed": 17, "test_fraction": 0.3, "neighbors": 3}

def run_experiment(config, X, y):
    indices = np.arange(len(y))
    train, test = train_test_split(
        indices, test_size=config["test_fraction"],
        stratify=y, random_state=config["seed"],
    )
    model = Pipeline([
        ("scale", StandardScaler()),
        ("knn", KNeighborsClassifier(n_neighbors=config["neighbors"])),
    ])
    model.fit(X[train], y[train])
    predicted = model.predict(X[test])
    return {
        "train_indices": train.tolist(),
        "test_indices": test.tolist(),
        "predicted": predicted.tolist(),
        "accuracy": float(accuracy_score(y[test], predicted)),
    }

first = run_experiment(config, X, y)
second = run_experiment(config, X, y)
assert first == second
assert len(first["test_indices"]) == 6
```

Сохраним вход и журнал. SHA-256 — контрольный отпечаток байтов файла: изменение содержимого почти наверняка изменит отпечаток. Он помогает обнаружить другую версию входа, но не объясняет её происхождение.

`Path.write_text(text, encoding="utf-8")` записывает текст в файл, `read_text` читает его обратно, `read_bytes` читает исходные байты без преобразования в текст. `hashlib.sha256(...).hexdigest()` вычисляет и записывает отпечаток строкой из шестнадцатеричных символов. Модуль `platform` сообщает версию Python и систему, функция `version` из `importlib.metadata` — версию установленного пакета. Эти сведения не меняют эксперимент, а объясняют условия его выполнения.

```python
with TemporaryDirectory() as folder:
    root = Path(folder)
    data_path = root / "input.json"
    data_path.write_text(json.dumps({"X": X.tolist(), "y": y.tolist()}), encoding="utf-8")
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    log = {
        "config": config,
        "result": first,
        "input_sha256": digest,
        "python": platform.python_version(),
        "system": platform.platform(),
        "packages": {name: version(name) for name in ["numpy", "scikit-learn"]},
    }
    log_path = root / "run.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    saved = json.loads(log_path.read_text(encoding="utf-8"))
    data = json.loads(data_path.read_text(encoding="utf-8"))
    replay = run_experiment(saved["config"], np.array(data["X"]), np.array(data["y"]))
    assert replay == saved["result"]
    assert hashlib.sha256(data_path.read_bytes()).hexdigest() == saved["input_sha256"]
print(first)
```

Ожидаем одинаковые индексы, предсказания и метрику в обоих запусках. Временные артефакты удалятся после примера; для настоящего проекта выберите отдельную постоянную папку результата. Сохранённый вход также должен сопровождаться описанием происхождения и допустимого использования.

## Ноутбук и скрипт

Ноутбук удобен для исследования, но хранит скрытое состояние ядра: удалённая ячейка могла оставить переменную. Перед передачей перезапустите ядро и выполните всё сверху вниз. Затем скачайте ноутбук с проверенным результатом.

Скрипт `.py` запускается сверху вниз командой `python experiment.py`. Повторяемые вычисления выносите в функции, а параметры — в один блок настроек. Если время запуска или качество изменились, сначала сравните вход, разбиение, версии и параметры; только затем объясняйте разницу алгоритмом.

## Задачи

### 1. Базовая

Что кроме seed нужно сохранить, чтобы восстановить проверочную часть?

<details>
<summary>Подсказка</summary>

Порядок строк тоже влияет на разбиение.

</details>

<details>
<summary>Решение</summary>

Сам набор данных в прежнем порядке и индексы либо идентификаторы строк разбиения.

</details>

### 2. Базовая

Чем конфигурация отличается от журнала?

<details>
<summary>Подсказка</summary>

Одна описывает намерение, другой — выполненный опыт.

</details>

<details>
<summary>Решение</summary>

Конфигурация задаёт параметры до запуска; журнал фиксирует фактические результаты и условия.

</details>

### 3. Прикладная

Проверьте, что списки `first["train_indices"]` и `first["test_indices"]` не пересекаются и вместе содержат индексы всех 20 объектов.

<details>
<summary>Подсказка</summary>

Используйте множества индексов.

</details>

<details>
<summary>Решение</summary>

```python
train_set = set(first["train_indices"])
test_set = set(first["test_indices"])
assert not train_set & test_set
assert train_set | test_set == set(range(20))
```

</details>

### 4. Прикладная

Подготовьте конфигурацию опыта с одним соседом, не изменяя исходный словарь. Проверьте, что seed и доля теста сохранены. Обучать альтернативу и просматривать тест для этой задачи не нужно.

<details>
<summary>Подсказка</summary>

Создайте копию словаря.

</details>

<details>
<summary>Решение</summary>

```python
alternative = config.copy()
alternative["neighbors"] = 1
assert alternative["neighbors"] == 1
assert config["neighbors"] == 3
assert alternative["seed"] == config["seed"]
assert alternative["test_fraction"] == config["test_fraction"]
```

Копия словаря позволяет изменить один параметр, сохранив остальные условия. Чтобы затем сравнить варианты, используйте внутреннюю перекрёстную проверку из прошлого урока, сохраняя итоговый тест закрытым.

</details>

### 5. Олимпиадная

Два участника сохранили seed, но один перед разбиением отсортировал таблицу. Почему части различаются?

<details>
<summary>Подсказка</summary>

Генератор выбирает позиции, а не смысл объектов.

</details>

<details>
<summary>Решение</summary>

Одинаковым позициям теперь соответствуют другие объекты. Поэтому нужны сохранённый порядок входа и явные индексы или id.

</details>

### 6. Олимпиадная

На сотне seed выбрали результат с наибольшей тестовой точностью. Почему это не честная итоговая оценка?

<details>
<summary>Подсказка</summary>

Тест участвовал в выборе опыта.

</details>

<details>
<summary>Решение</summary>

Произошёл подбор по тесту; случайно удачные разбиения получили преимущество. Нужна независимая итоговая проверка и заранее заданный протокол, а разброс результатов нужно указать.

</details>

## Итоги

Вы умеете сохранять условия опыта и проверять повторение по данным и журналу.

## Самопроверка

Почему seed без порядка строк не восстанавливает разбиение? Что покажет другой отпечаток файла? Как проверить, что ноутбук не зависит от ранее выполненных ячеек?

Для перехода дальше достаточно уверенно решать базовые и прикладные задачи. К олимпиадным можно вернуться позже.
