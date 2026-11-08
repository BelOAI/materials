# Первое обучение нейросети

Обучаем небольшую сеть распознавать рукописные цифры 8 на 8: от картинки к вектору из 64 чисел, `MLPClassifier` и `fit`, ошибка и шаг против производной, эпохи и кривая ошибки, десять классов и softmax, честная оценка на отложенных данных.

[Текст](content.md) · [Ноутбук](notebook.ipynb) · [Код рисунков](figures.py) · [От картинки к сети](media/digit-to-net.svg) · [Цикл обучения](media/fit-loop.svg) · [Шаг против производной](media/step.svg) · [Ошибка по эпохам](media/loss-curve.svg) · [Десять вероятностей](media/probabilities.svg) · [Ошибки сети](media/mistakes.svg)

Нужны прямой проход и активации из [занятия 2.1](../01-from-linear-model-to-neural-network/README.md), логарифмическая ошибка и градиентный спуск из [занятия 1.6](../../01-classic-ml/06-logistic-regression/README.md), разделение данных и переобучение из занятий [1.7](../../01-classic-ml/07-features-regularization/README.md) и [1.8](../../01-classic-ml/08-honest-evaluation/README.md). PyTorch не требуется: обучение выполняет `MLPClassifier` из scikit-learn. Обратное распространение ошибки только названо; его разбор остаётся за занятием 5.5.

## Данные

Набор рукописных цифр входит в scikit-learn и загружается `load_digits()`: 1797 картинок 8 на 8, яркости от 0 до 16. Отдельных файлов данных параграф не содержит. Для занятия отобраны тройки и восьмёрки, яркости разделены на 16, разбиение — `train_test_split(test_size=0.3, random_state=0, stratify=y)`.

Рисунки — SVG с прозрачным фоном и цветами для светлой, тёмной и печатной темы; их собирает `python3 figures.py` (нужны numpy и scikit-learn). Картинки цифр, кривая ошибки, вероятности и примеры ошибок на рисунках взяты из тех же моделей, что в тексте, с теми же `random_state`. Ноутбук синхронизируется с текстом: `python3 utils/scripts/handbook_notebooks.py --write`.

## Источники

- E. Alpaydin, C. Kaynak. Optical Recognition of Handwritten Digits. UCI Machine Learning Repository, 1998, [archive.ics.uci.edu](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits) — исходный набор цифр 8 на 8, который scikit-learn публикует как `load_digits`.
- scikit-learn — [Neural network models (supervised)](https://scikit-learn.org/stable/modules/neural_networks_supervised.html) — параметры `MLPClassifier`, скорость обучения и `loss_curve_`.

Числа в тексте проверены запуском листингов (Python 3.14, scikit-learn 1.9.1, numpy 2.5.4).
