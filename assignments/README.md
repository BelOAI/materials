# Домашние задания

Задания находятся в `assignments/NN-topic/`. Это печатные документы класса `article`: `main.tex` подключает фрагменты из `sections/`, `meta.yaml` описывает задание на сайте, `materials/` содержит дополнительные файлы. Нумерация заданий независима от лекций и практик.

## Выбрать шаблон

| Вид задания | Шаблон | `assignment_type` | Пакет |
| --- | --- | --- | --- |
| Математика | `_template-math` | `math` | `academicworksheet` |
| Программирование | `_template-coding` | `coding` | `academicstatement` |

```bash
cp -R assignments/_template-math assignments/04-topic
```

Для программирования вместо `_template-math` используйте `_template-coding`. Заполните `meta.yaml`: `build: true`, `assignment_type`, название, описание и дату выдачи. Без корректного `assignment_type` запись не попадёт в каталог.

Обновите `main.tex`, номер задания и фрагменты в `sections/`:

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicworksheet} % или academicstatement
\setassignmentno{4}
```

```bash
make session DIR=assignments/04-topic
make site
```

На сайте задания отмечаются янтарным цветом, видом задания и датой «Выдано». Время необязательно и задаётся через `time`.

Доступные команды пакетов: [LaTeX](../latex/README.md). Дополнительные файлы, ссылки и публикация: [общее руководство](../scripts/README.md).

## Опубликовать готовый PDF

Создайте папку задания с `meta.yaml` и своим PDF, без обязательного `main.tex`. Укажите `pdf: materials/assignment.pdf` и `build: true`; заполните название, описание и дату. Для задания обязателен `assignment_type`. Если TeX тоже есть, указанный PDF имеет приоритет. `make tex DIR=…` собирает только локальную TeX-версию. Подробнее: [готовые PDF](../scripts/README.md#готовый-pdf-вместо-tex).

Материалы этого раздела — [CC BY 4.0](../LICENSE-CC-BY-4.0). Авторы: Pavel Kasila и BelOAI Material Authors.
