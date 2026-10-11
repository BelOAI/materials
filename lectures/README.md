# Лекции

Каждая лекция находится в `lectures/NN-topic/`: `main.tex` подключает фрагменты из `slides/`, `meta.yaml` описывает материал на сайте, `assets/` содержит изображения, `materials/` — дополнительные файлы.

## Добавить лекцию

```bash
cp -R lectures/_template lectures/02-topic
```

Заполните `meta.yaml` и установите `build: true`. В `main.tex` обновите название и подпись; замените примеры в `slides/`. Оставьте только нужные команды `\input` в порядке показа слайдов.

```latex
\documentclass[aspectratio=169,11pt,t]{beamer}
\usepackage[russian]{academicbeamer}
\setshorttitle{BelOAI \textbar\ Лекция 2}
```

Лекции используют синюю тему. Соберите и проверьте:

```bash
make session DIR=lectures/02-topic
make site
```

Можно публиковать лекцию только с ноутбуком или ссылками, без `main.tex`. Поля метаданных, сборка и публикация: [общее руководство](../scripts/README.md). Оформление: [LaTeX](../latex/README.md).

## Опубликовать готовый PDF

Создайте папку лекции с `meta.yaml` и своим PDF, без обязательного `main.tex`. Укажите `pdf: materials/lecture.pdf` и `build: true`; заполните название, описание и дату. Если TeX тоже есть, указанный PDF имеет приоритет. `make tex DIR=…` собирает только локальную TeX-версию. Подробнее: [готовые PDF](../scripts/README.md#готовый-pdf-вместо-tex).

Материалы этого раздела — [CC BY 4.0](../LICENSE-CC-BY-4.0). Авторы BelOAI.
