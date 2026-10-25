# Практики

Каждая практика находится в `course/practices/NN-topic/`. Структура такая же, как у [лекций](../lectures/README.md): `main.tex`, `meta.yaml`, `slides/`, при необходимости `assets/` и `materials/`. Нумерация практик независима от лекций.

## Добавить практику

```bash
cp -R practices/_template practices/02-topic
```

Заполните `meta.yaml`, установите `build: true`, обновите `main.tex` и содержимое `slides/`. Порядок слайдов задайте командами `\input`.

```latex
\documentclass[aspectratio=169,11pt,t]{beamer}
\usepackage[practice,russian]{academicbeamer}
\setshorttitle{BelOAI \textbar\ Практика 2}
```

Опция `practice` включает зелёную тему.

```bash
make -f build/Makefile session DIR=course/practices/02-topic
make -f build/Makefile site
```

Для практики только с контестом достаточно `meta.yaml` с внешней ссылкой, без `main.tex`. Ноутбуки и файлы перечислите в `materials`. Подробнее: [метаданные и публикация](../../utils/scripts/README.md), [оформление LaTeX](../../utils/latex/README.md).

## Опубликовать готовый PDF

Создайте папку практики с `meta.yaml` и своим PDF, без обязательного `main.tex`. Укажите `pdf: materials/practice.pdf` и `build: true`; заполните название, описание и дату. Если TeX тоже есть, указанный PDF имеет приоритет. `make -f build/Makefile tex DIR=…` собирает только локальную TeX-версию. Подробнее: [готовые PDF](../../utils/scripts/README.md#готовый-pdf-вместо-tex).

Материалы этого раздела — [CC BY 4.0](../../LICENSE-CC-BY-4.0). Авторы указаны в метаданных каждого материала.
