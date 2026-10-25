# Ближайшие соседи и масштаб признаков

Как предсказывать класс по похожим примерам и почему единицы измерения влияют на ответ.

[Текст](content.md) · [Ноутбук](notebook.ipynb) · [Расстояния](media/distances.svg) · [Соседи](media/neighbors.svg) · [Min–max](media/min-max.svg)

Нужны понятия признака, класса, обучающей и тестовой частей из занятия 1.1; основы Python, модуль числа и квадратный корень. Для кода нужен scikit-learn из [среды учебника](../../00-intro/01-environment/requirements.txt).

## Основа занятия

- [Программа, тема 1.2](../../CURRICULUM.md): расстояния, голосование и масштаб признаков. Пример с игровыми персонажами взят из задания программы; числа придуманы для этого занятия.
- [Занятие 1.1](../01-first-experiment/content.md): признаки и ответы, независимая проверка и доля верных ответов. Эти понятия используются без повторного подробного введения.
- Текст, схемы и реализация написаны для учебника. Таблицы содержат авторские учебные данные. Схемы показывают два расстояния на одних точках, порядок соседей при двух масштабах и min–max нормализацию здоровья.
- [MinMaxScaler](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.MinMaxScaler.html): границы на обучающей части через `fit_transform`, преобразование новых объектов через `transform`.
- [KNeighborsClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.neighbors.KNeighborsClassifier.html): модель с манхэттенским расстоянием, прогноз, индексы соседей и доля верных ответов.

## Иллюстрация персонажей

[Воин и маг](media/heroes.png) созданы встроенным инструментом `imagegen`. Иллюстрация знакомит с двумя классами героев; вычисления и подписи выполнены отдельно в SVG.

Финальная версия имеет прозрачный фон и небольшие полупрозрачные ауры: голубую у воина и фиолетовую у мага.

Промпт:

> Use case: illustration-story. Asset type: a wide, shallow editorial illustration for a Russian machine learning lesson for high school students, introducing game characters classified as warriors or mages. Primary request: a beautifully drawn friendly fantasy warrior and a mage, presented side by side like characters in a modern indie game handbook. Style: sophisticated clean digital illustration, crisp expressive silhouettes, subtle textured shading, polished flat color shapes, suitable for teenagers, not babyish. Warrior with blue silver armor and a shield; mage with a violet robe and a softly glowing cyan magic orb. Both standing relaxed, no combat, facing the reader. Composition: panoramic horizontal banner about 3:1, full characters visible and comfortably framed, very light warm paper background with faint blue and purple geometric halos behind the two figures, uncluttered, minimal empty margin above and below. No letters, labels, numbers, logos, borders, interface or watermark. The illustration should work attractively at a small size in a math textbook.

Финальный промпт редактирования:

> Edit target: the transparent cutout of the two existing fantasy characters. Preserve the characters exactly: warrior on the left with blue/silver armor and shield, mage on the right with purple robe and cyan orb; keep their faces, full bodies, poses, clothing, colors, relative size and position, and clean illustration style unchanged. Add ONLY a small tasteful translucent magical aura behind each character: a faint pale blue glow with a few subtle geometric sparkles close behind the warrior's silhouette, and a faint violet glow with a few subtle arc-shaped magical accents close behind the mage's silhouette. Keep each aura close to the figure, gently fading to full transparency, delicate and understated rather than big circles. Keep the cyan orb's local glow. There must be no solid backdrop, no cream paper, no castles, no landscape, no large enclosing discs, no rectangular backing and no painted checkerboard. Genuine RGBA transparency across the rest of the wide horizontal canvas, including between and outside the figures. Ensure clean antialiased edges without white fringes or stray colored pixels, looking beautiful on a dark #212529 webpage. No text or logos.
