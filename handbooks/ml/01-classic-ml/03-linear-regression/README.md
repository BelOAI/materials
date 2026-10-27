# Линейная регрессия, Ridge и Lasso

<!-- handbook-authors -->

Подбираем прямую по учебным точкам, смотрим на остатки и MSE, затем добавляем штрафы $L_2$ (Ridge) и $L_1$ (Lasso) и выбираем их силу по проверочной части.

[Текст](content.md) · [Ноутбук](notebook.ipynb) · [Код рисунков](figures.py) · [Остатки](media/fit-residuals.svg) · [Цикл обучения](media/training-loop.svg) · [Шпаргалка](media/cheatsheet.svg) · [Выбросы и коллинеарность](media/pitfalls.svg) · [Сжатие весов](media/shrinkage.svg) · [Пути весов](media/paths.svg) · [Сравнение](media/compare.svg)

Нужны понятия признака, числового ответа и средней ошибки из [занятия 1.1](../01-first-experiment/README.md), а также деление на обучающую и проверочную части. Все данные синтетические и придуманы для учебника; графики воспроизводит `python3 figures.py`, схемы `training-loop.svg` и `cheatsheet.svg` нарисованы вручную (нужны numpy, matplotlib и scikit-learn).
