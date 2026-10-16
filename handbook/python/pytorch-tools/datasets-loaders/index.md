## Чему научимся

Определять набор данных и проверять формы полных и неполных мини-пакетов.

## Данные примера

В autograd мы передавали вычислению всю таблицу сразу. Теперь научимся получать из неё пары «признаки, ответ» и объединять их в пакеты. Возьмём те же два объекта с ответами 5 и 4; создаём их заново для самостоятельного запуска ноутбука на CPU.

```python
import torch
X = torch.tensor([[2., 1.], [1., 3.]], dtype=torch.float64)
y = torch.tensor([5., 4.], dtype=torch.float64)
```

## Dataset, класс и методы

`Dataset` задаёт, как получить отдельный пример; `DataLoader` собирает примеры в мини-пакеты — небольшие группы для одного вычисления. Нужен минимальный синтаксис класса: класс описывает объект с данными и действиями; методы — функции внутри класса, `self` обозначает текущий объект. `__init__` вызывается при создании, `__len__` задаёт длину, `__getitem__` — получение по индексу. Запись `class Measurements(Dataset):` создаёт наш вид набора данных на основе `Dataset`; в нём определяем нужные методы. `self.features` хранит данные именно этого объекта. При вызове `Measurements(X, y)` Python сам передаст создаваемый объект в `self`, а `X` и `y` — в `features` и `targets`.

## Разобранный пример: два объекта, два мини-пакета

При `len(dataset)` Python вызывает `dataset.__len__()`, при `dataset[0]` — `dataset.__getitem__(0)`. В обоих случаях Python передаёт `self` автоматически. Мы переопределяем эти действия для своего набора данных. Запись `return self.features[index], self.targets[index]` возвращает кортеж из двух элементов без внешних скобок. Это пара «признаки, ответ»; цикл `for batch_X, batch_y in loader` распаковывает такие данные уже для пакета объектов. `torch.Generator().manual_seed(17)` создаёт генератор и задаёт ему начальное состояние.

`batch_size=1` задаёт один объект в пакете, `shuffle=True` перемешивает порядок при обходе, `generator` задаёт источник случайности. `num_workers=0` читает данные в текущем процессе, что удобно для небольшого ноутбука. Последний пакет может быть меньше `batch_size`; не зашивайте его размер в форму ответа.

```python
from torch.utils.data import Dataset, DataLoader

class Measurements(Dataset):
    def __init__(self, features, targets):
        if len(features) != len(targets):
            raise ValueError("Число объектов и ответов должно совпадать")
        self.features = features
        self.targets = targets

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, index):
        return self.features[index], self.targets[index]

dataset = Measurements(X, y)
generator = torch.Generator().manual_seed(17)
loader = DataLoader(dataset, batch_size=1, shuffle=True, generator=generator, num_workers=0)
seen = 0
for batch_X, batch_y in loader:
    assert batch_X.shape == (1, 2)
    assert batch_y.shape == (1,)
    seen += len(batch_y)
assert seen == 2
```

В данном наборе `dataset[0]` возвращает признаки `[2, 1]` и ответ 5. После объединения в пакет из одного объекта форма признаков `(1, 2)`, ответов — `(1,)`. Первая ось теперь обозначает объекты пакета.

## Полный и неполный пакет за один обход

Возьмём пять объектов, чтобы увидеть пакеты разного размера. Параметр `drop_last=False` оставляет последний неполный пакет; это значение используется по умолчанию.

```python
five_X = torch.tensor([[1., 2.], [2., 3.], [3., 4.], [4., 5.], [5., 6.]], dtype=torch.float64)
five_y = torch.tensor([3., 5., 7., 9., 11.], dtype=torch.float64)
five = Measurements(five_X, five_y)
sizes = []
for batch_X, batch_y in DataLoader(five, batch_size=2, shuffle=False, drop_last=False):
    assert batch_X.shape == (len(batch_y), 2)
    sizes.append(len(batch_y))
assert sizes == [2, 2, 1]
```

При `shuffle=False` объекты идут в исходном порядке, признаки и ответы остаются парами. Перемешивание меняет порядок пар целиком. Генератор случайности расходует своё состояние при обходе: второй обход может дать другую перестановку, хотя исходный seed был один.

## Задачи

### 1. Базовая

Какой метод Dataset задаёт длину?

<details>
<summary>Подсказка</summary>

Он вызывается функцией len.

</details>

<details>
<summary>Решение</summary>

Метод `__len__`: функция `len(dataset)` вызывает его и получает число объектов набора.

</details>

### 2. Базовая

Что задаёт batch_size?

<details>
<summary>Подсказка</summary>

Это размер одной группы примеров.

</details>

<details>
<summary>Решение</summary>

Число объектов в мини-пакете.

</details>

### 3. Прикладная

Проверьте первый объект dataset без загрузчика.

<details>
<summary>Подсказка</summary>

Индексирование вызывает __getitem__.

</details>

<details>
<summary>Решение</summary>

```python
features, target = dataset[0]
assert features.shape == (2,)
assert target.item() == 5
```

</details>

### 4. Прикладная

Создайте загрузчик из двух объектов с batch_size=3.

<details>
<summary>Подсказка</summary>

Последний пакет неполный.

</details>

<details>
<summary>Решение</summary>

```python
small_loader = DataLoader(dataset, batch_size=3, shuffle=False, num_workers=0)
packets = list(small_loader)
assert len(packets) == 1
assert packets[0][0].shape == (2, 2)
```

</details>

### 5. Олимпиадная

Почему нельзя всегда задавать форму ответа через batch_size?

<details>
<summary>Подсказка</summary>

Последний пакет может быть короче.

</details>

<details>
<summary>Решение</summary>

Нужно использовать фактическое число объектов текущего пакета, иначе возникнет ошибка формы или потеря данных.

</details>

### 6. Олимпиадная

Почему одинаковый seed не означает один и тот же порядок каждого обхода одного генератора?

<details>
<summary>Подсказка</summary>

Состояние генератора меняется.

</details>

<details>
<summary>Решение</summary>

Следующий обход использует продолжение последовательности. Для точного повторения опыт запускают с заново созданным генератором и тем же состоянием.

</details>

## Итоги

Вы умеете описывать доступ к объекту и собирать объекты в мини-пакеты.

## Самопроверка

Какой метод вызывается для `dataset[0]`? Какими будут размеры пакетов для пяти объектов при `batch_size=2`? Почему нельзя менять порядок признаков отдельно от ответов?

Для перехода дальше достаточно уверенно решать базовые и прикладные задачи. К олимпиадным можно вернуться позже.
