# Оформление LaTeX

Общие пакеты находятся в `utils/latex/tex/latex/`. Скрипты сборки устанавливают `TEXINPUTS`, поэтому документы подключают пакеты через `\usepackage`, без относительных путей к стилям.

## Презентации

```latex
\usepackage[russian]{academicbeamer}          % лекция, синяя тема
\usepackage[practice,russian]{academicbeamer} % практика, зелёная тема
\setshorttitle{BelOAI \textbar\ Лекция 2}
```

В документе используйте только один вариант подключения. Опции `russian` и `lecture` действуют по умолчанию; `english` включает английский язык, `practice` — тему практик.

Команды темы:

- `\lead{текст}` — выделенное начало мысли;
- `\tbd{текст}` — отметка черновика;
- `\orient` — отметка «ориентир»;
- `\photoframe{ширина}{высота}{подпись}` — место для изображения;
- `\orientnote[дополнение]` — примечание к ориентировочным значениям.

Примеры компоновки находятся в [шаблоне слайдов](../../course/lectures/_template/slides/README.md).

## Задания

Для математических листов:

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicworksheet}
\setassignmentno{2}
```

Используйте окружение `exercise`, команды `\answerlines{число}` и `\answerbox[высота]` для места под ответ.

Для условий задач по программированию подключите `academicstatement` вместо `academicworksheet`. Доступны окружения `problem`, `io`, `example`, `constraints` и команда `\sampleio{ввод}{вывод}`. Оба пакета поддерживают `russian` (по умолчанию) и `english`.

## Где менять оформление

| Изменение | Файл внутри `utils/latex/tex/latex/` |
| --- | --- |
| Цвета лекций и практик | `beamer/beamercolorthemeAcademic.sty`, `beamer/beamercolorthemeAcademicPractice.sty` |
| Заголовки, колонтитулы и поля | `beamer/beamerouterthemeAcademic.sty` |
| Блоки, списки и команды темы | `beamer/beamerinnerthemeAcademic.sty` |
| Зависимости темы | `beamer/beamerthemeAcademic.sty` |
| Язык и шрифты презентаций | `academicbeamer/academicbeamer.sty` |
| Математические листы | `academicworksheet/academicworksheet.sty` |
| Условия задач | `academicstatement/academicstatement.sty` |

Содержимое занятий храните в папках занятий, а не в стилях. После изменения общих пакетов выполните `make -f build/Makefile site`, чтобы пересобрать все материалы. Сборка и зависимости описаны в [общем руководстве](../scripts/README.md).

Пакеты оформления распространяются по [MIT](../../LICENSE-MIT). Авторы BelOAI.
