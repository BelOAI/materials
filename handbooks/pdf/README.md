# PDF-стиль учебника

Основа оформления взята из `bsu-special-data-structures-en/materials/build-lecture.ps1`, `materials/build-quiz.ps1` и `materials/pdf-header.tex`: A4, Pandoc + XeLaTeX, засечковый основной шрифт, аккуратные переносы и цельные короткие листинги. Взяты параметры опросника 10 pt и поля 18 мм, чтобы занятие вместе с десятью вопросами укладывалось в предел восьми страниц. Для русского текста используется Times New Roman; код набирается Consolas. Исходный Markdown остаётся пригодным для сайта.

Собрать занятие из корня репозитория:

```powershell
py -3 utils/scripts/build-handbook-pdf.py handbooks/ml/01-classic-ml/01-first-experiment
```

Сборка сохраняет PDF в `output/pdf/`. Подсказки и разборы из раскрывающихся блоков выводятся в печатном варианте целиком. Схемы SVG преобразуются во временные векторные PDF для XeLaTeX; исходники не меняются. Перед передачей просмотрите каждую страницу и проверьте предел объёма из `handbooks/guidelines/content.md`.
