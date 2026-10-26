# Занятия по неделям

Каждая папка `NN-topic/` объединяет лекцию, практики и задания недели. Неделя `00` содержит подготовительные задания; остальные начинаются с лекции, которую можно листать на сайте.

`course.yml` задаёт порядок недель. В каждой неделе `week.yml` задаёт название, описание, номер, постоянный slug страницы и порядок подпапок материалов. Каждый материал содержит `material.yml`: `kind: lecture`, `practice` или `assignment`, явный `number`, название, дату, авторов и `build: true`. Для заданий обязателен `assignment_type: math` или `coding`.

Чтобы добавить неделю, создайте папку, заполните `week.yml` по существующему примеру и внесите её в `course.yml`. Скопируйте внутрь нужные шаблоны из `_templates/`: `lecture`, `practice`, `assignment-math` или `assignment-coding`. Перечислите подпапки в `materials` недели. Каждой неделе после нулевой нужна ровно одна лекция с PDF.

Лекции используют `academicbeamer`, практики — его опцию `practice`. Задания используют класс `article` и пакет `academicworksheet` или `academicstatement`. Пакеты подключаются через `\usepackage`; порядок фрагментов в `main.tex` задают команды `\input`. Готовый PDF можно указать в поле `pdf` вместо сборки TeX.

```bash
make -f build/Makefile session DIR=course/01-intro-ml/lecture
make -f build/Makefile site
```

Поля метаданных, зависимости и публикация: [руководство по сборке](../utils/scripts/README.md). Общие стили: [LaTeX](../utils/latex/README.md).

Учебные материалы — [CC BY 4.0](../LICENSE-CC-BY-4.0). Авторы указаны в метаданных каждого материала.
