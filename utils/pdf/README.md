# PDF учебников

Общий профиль: Pandoc + XeLaTeX, A4, 10 pt, поля 18 мм, Liberation Serif и DejaVu Sans Mono. Chromium преобразует SVG в векторные PDF с печатной светлой темой, CSS-переменными и узорами; подсказки и решения печатаются полностью. Короткие листинги сохраняются на одной странице. Исходные Markdown и структура учебников не меняются. SVG должны содержать необходимые стили и изображения внутри файла: внешние загрузки и скрипты при преобразовании отключены.

## Зависимости

Нужны Python 3.14, Pandoc, XeLaTeX, Poppler (`pdfinfo`, `pdftoppm`), Fontconfig (`fc-match`), указанные шрифты и пакеты из `requirements.txt` этой папки. TeX должен включать поддержку русского языка, `fontspec`, `babel`, `float`, `needspace`, `framed`, `fancyvrb` и математические пакеты.

```bash
python3 -m pip install -r utils/pdf/requirements.txt
python3 -m playwright install chromium --no-shell
# Debian / Ubuntu
sudo apt-get install pandoc texlive-xetex texlive-latex-extra texlive-lang-cyrillic \
  poppler-utils fontconfig fonts-liberation fonts-dejavu-core
# macOS: дополнительно установите MacTeX или соответствующий набор TeX Live
brew install pandoc poppler fontconfig
brew install --cask font-liberation font-dejavu
```

На Linux системные зависимости Chromium можно установить командой `python3 -m playwright install-deps chromium`. После обновления Playwright повторите установку Chromium.

PDF-инструменты устанавливаются отдельно от окружения сайта. Обычные команды `site`, `handbooks` и CI публикации PDF учебников не собирают.

## Команды

Из корня репозитория:

```bash
make -f build/Makefile handbook-pdf                              # все учебники
make -f build/Makefile handbook-pdf DIR=handbooks/ml JOBS=2       # книга и её разделы
make -f build/Makefile handbook-pdf DIR=handbooks/ml/01-classic-ml
python3 utils/scripts/build-handbook-pdf.py handbooks/ml/01-classic-ml/01-first-experiment
python3 utils/scripts/build-handbook-pdf.py --all --output-dir output/pdf --jobs 2
```

Путь к главе собирает главу и её параграфы; путь к книге — все три уровня. Результаты:

- `output/pdf/<book>/handbook.pdf`;
- `output/pdf/<book>/<chapter>/chapter.pdf`;
- `output/pdf/<book>/<chapter>/<paragraph>/paragraph.pdf`.

Имена берутся из `slug`, порядок — из `chapters` в `handbooks/handbooks.json` и `paragraphs` в YAML глав. Для будущего учебника применяется та же структура каталогов и метаданных; ограничение сайта на ML не распространяется на PDF.

`--output <файл.pdf>` задаёт путь при выборе ровно одного документа. `--output-dir` задаёт корень результатов поддерева; эти параметры несовместимы. Для ссылок на dev-версию задайте `--site-url https://beloai.github.io/materials/dev/`.

В состав главы входят её собственный `content.md`, если он есть, и доступные параграфы. В книгу дополнительно входит её вводный `content.md`. README, программа, данные и ноутбуки не вставляются в текст. Папки с `_`, `build: false` и `planned` пропускаются; `draft` с `build: true` включается. Пустые документы не создаются. Удалённые и исключённые материалы очищаются только внутри выбранного поддерева результатов.

Главы и книги — цельные документы с оглавлением, закладками и сквозной нумерацией страниц. Авторы указаны у соответствующих разделов. Ссылки на включённые разделы ведут внутрь PDF, остальные — на сайт. Изображения разрешаются относительно исходного текста и должны находиться внутри `handbooks/`, в том числе общие изображения и цели символических ссылок.

## Кэш и проверка

Общий проверяемый кэш `.cache/build/` хранит подготовленные деревья Pandoc, преобразованные SVG и готовые PDF раздельно. Неизменённый запуск восстанавливает результаты без Pandoc и XeLaTeX. Изменение параграфа пересобирает его PDF, родительскую главу и книгу. Одинаковые SVG преобразуются один раз независимо от пути; подготовка текста переиспользуется на всех уровнях. XeLaTeX выполняется максимум в двух параллельных задачах по умолчанию.

Ключи учитывают содержимое, используемые ресурсы, порядок, профиль, код преобразования, бинарники инструментов, шрифты, формат TeX, реестр TeX Live при наличии и версию Chromium. Обновление движка SVG пересобирает рисунки и использующие их PDF. `BUILD_ENV_ID` позволяет явно обозначить смену окружения. `BUILD_CACHE_DIR` меняет расположение кэша; `BUILD_CACHE_DISABLE=1` отключает чтение и запись. Повреждённые записи пересобираются, неудачные результаты не кэшируются. Проверенные PDF заменяются атомарно; при ошибке прежний файл остаётся, а команда завершается с ненулевым кодом.

Команда выводит попадания в кэш, число компиляций, преобразований SVG и время. Для сравнения холодной и тёплой сборки выполните одну команду дважды. Удаление `output/pdf/` не требует повторной компиляции при сохранном кэше.

Синтетическая проверка настоящего SVG-рендеринга (CSS-переменные, печатная палитра, сетка, текст и векторный выход): `PDF_RENDER_TESTS=1 python3 -m unittest discover -s utils/scripts/tests -p test_handbook_svg.py`. Обычные тесты не требуют установки браузера и пропускают эти две проверки.

Перед передачей отрендерите PDF через `pdftoppm -png <файл.pdf> <префикс>` и просмотрите каждую страницу: формулы, глифы, рисунки, код и разрывы. Ориентир объёма отдельного занятия — в `handbooks/guidelines/content.md`; лимит не применяется к целой главе или книге. Результаты и кэш не коммитятся.

Профиль основан на `bsu-special-data-structures-en/materials/build-lecture.ps1`, `materials/build-quiz.ps1` и `materials/pdf-header.tex`; общее оформление хранится в этой папке.
