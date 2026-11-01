"""Настоящий TeX на синтетических книгах; включается вместе с SVG-тестами."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_pdf import build, prepare_logo, format_objects
from repo_paths import REPO_ROOT


@unittest.skipUnless(os.environ.get('PDF_RENDER_TESTS') == '1', 'Нужно PDF_RENDER_TESTS=1 и окружение utils/pdf')
class HandbookPdfRenderingTests(unittest.TestCase):
    def test_recto_chapters_blank_pages_and_opening_page_style(self):
        import pymupdf
        import subprocess
        source = r'''\documentclass[12pt,twoside]{article}
\usepackage[T2A]{fontenc}
\usepackage[russian]{babel}
\usepackage{handbookfonts,belarustextbook}
\begin{document}
\handbookopenchapter\section*{Первый}
Начало первой главы.
\handbookopenchapter\section*{Второй}
Начало второй главы.
\end{document}'''
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'recto.tex').write_text(source)
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//'
                       + os.pathsep + os.environ.get('TEXINPUTS', ''))
            result = subprocess.run(['pdflatex', '-halt-on-error', '-interaction=nonstopmode', 'recto.tex'],
                                    cwd=folder, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            with pymupdf.open(folder / 'recto.pdf') as document:
                self.assertEqual(len(document), 3)
                self.assertIn('Первый', document[0].get_text())
                self.assertFalse(document[1].get_text().strip())
                self.assertFalse(document[1].get_drawings())
                self.assertIn('Второй', document[2].get_text())
                for i in (0, 2):
                    page = document[i]
                    self.assertFalse(page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, 45)).strip())
                    self.assertIn(str(i + 1), page.get_text(clip=pymupdf.Rect(0, page.rect.height - 45, page.rect.width, page.rect.height)))

    def test_editorial_pandoc_paragraph_and_list_indents(self):
        import pymupdf
        import subprocess

        prose = 'текст для проверки переноса строки ' * 9
        source = ('# Заголовок\n\nНачальный абзац.\n\nОбычный абзац.\n\n'
                  '9. Нумерованный ' + prose + '\n\n'
                  '   ```python\n   print(1)\n   ```\n\n'
                  '   Дополнительный абзац того же пункта.\n\n'
                  '10. Повторный пункт.\n\n'
                  '- Маркированный ' + prose + '\n\n'
                  '  - Вложенный ' + prose + '\n\n'
                  'Возвратный абзац после списка.\n\n'
                  '```python\nprint(2)\n```\n\n'
                  'Кодовый абзац после отдельного листинга.\n')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'header.tex').write_text(
                '\\usepackage{fvextra}\n\\usepackage{belarustextbook}\n')
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//'
                       + os.pathsep + os.environ.get('TEXINPUTS', ''))
            result = subprocess.run(
                ['pandoc', '-f', 'markdown', '--pdf-engine=pdflatex',
                 '--include-in-header', 'header.tex', '-V', 'fontenc:T2A', '-V', 'lang:ru-RU',
                 '-V', 'fontfamily:handbookfonts', '-V', 'fontsize:12pt',
                 '-V', 'classoption:twoside', '-V', 'indent:true', '-o', 'lists.pdf'],
                input=source, cwd=folder, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            with pymupdf.open(folder / 'lists.pdf') as document:
                self.assertEqual(len(document), 1)
                page = document[0]
                mm = 72 / 25.4
                for word, offset in [('Начальный', 30), ('Обычный', 30), ('Возвратный', 30), ('Кодовый', 30),
                                     ('Нумерованный', 38), ('Дополнительный', 25), ('Повторный', 38),
                                     ('Маркированный', 38), ('Вложенный', 38)]:
                    self.assertAlmostEqual(page.search_for(word)[0].x0, offset * mm, delta=.2, msg=word)
                for label in ('9.', '10.'):
                    self.assertAlmostEqual(page.search_for(label)[0].x0,
                                           page.search_for('Обычный')[0].x0, delta=.2, msg=label)
                # Only the opening line is indented. Continuations use the
                # full page text area, including nested and multi-paragraph items.
                continuations = 0
                for block in page.get_text('dict')['blocks']:
                    if block['type'] != 0:
                        continue
                    for line in block['lines']:
                        text = ''.join(span['text'] for span in line['spans'])
                        if text.startswith('текст') or text.startswith('проверки') or text.startswith('строки'):
                            continuations += 1
                            self.assertAlmostEqual(line['bbox'][0], 25 * mm, delta=.2, msg=text)
                self.assertGreater(continuations, 3)

    def test_editorial_type_metrics_paragraphs_and_binding_offset(self):
        import pymupdf
        import re
        import subprocess

        source = r'''
\documentclass[12pt,twoside]{article}
\usepackage[T2A]{fontenc}
\usepackage[russian]{babel}
\usepackage{handbookfonts}
\usepackage{fvextra,longtable}
\DefineVerbatimEnvironment{Highlighting}{Verbatim}{}
\usepackage{belarustextbook}
\begin{document}
\makeatletter
\small Small\par\normalsize
\typeout{BODY-SIZE=\f@size}
\typeout{BODY-BASELINE=\the\baselineskip}
\typeout{BODY-INDENT=\the\parindent}
\typeout{BODY-PARSKIP=\the\parskip}
\typeout{BODY-WIDTH=\the\textwidth}
\setbox0\hbox{Н}\typeout{BODY-CAP=\the\ht0}
\makeatother
\section*{Глава}
Первый абзац после заголовка. Продолжение первой строки, затем
продолжение текста второй строки для проверки набора.

Обычный абзац с отступом первой строки и продолжением текста,
которого достаточно для переноса на следующую строку.
\subsection*{Параграф}
Текст после параграфа. Ещё несколько слов для продолжения строки.
\subsubsection*{Подраздел}
Текст после подраздела. Ещё несколько слов для продолжения строки.
\paragraph*{Глубокий}
Текст после глубокого заголовка. Продолжение первой строки.
\begin{figure}[H]
\centering\rule{20mm}{5mm}
\caption*{Рисунок 7. Подпись}
\end{figure}
\begin{Highlighting}
print("Листинг")
\end{Highlighting}
\clearpage
\noindent Чётная страница\par
\begin{longtable}{ll}
\caption*{Таблица 3. Подпись}\\
Ячейка & Значение\\
\end{longtable}
\clearpage
\noindent Нечётная страница\par
\end{document}
'''
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'metrics.tex').write_text(source)
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//'
                       + os.pathsep + os.environ.get('TEXINPUTS', ''))
            result = subprocess.run(['pdflatex', '-halt-on-error', '-interaction=nonstopmode', 'metrics.tex'],
                                    cwd=folder, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
            metrics = dict(re.findall(r'BODY-([A-Z]+)=([0-9.]+)', result.stdout))
            tex_pt_per_mm = 72.27 / 25.4
            for name, expected in [('SIZE', 13), ('BASELINE', 16), ('INDENT', 5 * tex_pt_per_mm),
                                   ('PARSKIP', 0), ('WIDTH', 130 * tex_pt_per_mm)]:
                self.assertAlmostEqual(float(metrics[name]), expected, delta=.01, msg=name)
            self.assertGreaterEqual(float(metrics['CAP']) / tex_pt_per_mm, 3)
            self.assertNotIn('Overfull', result.stdout)
            self.assertNotIn('headheight is too small', result.stdout)
            with pymupdf.open(folder / 'metrics.pdf') as document:
                self.assertEqual(len(document), 3)
                mm = 72 / 25.4
                for page, word, margin in [(document[0], 'Первый', 30),
                                           (document[1], 'Чётная', 15), (document[2], 'Нечётная', 25)]:
                    self.assertAlmostEqual(page.search_for(word)[0].x0, margin * mm, delta=.1)
                self.assertAlmostEqual(document[0].search_for('Обычный')[0].x0, 30 * mm, delta=.1)
                seen = set()
                for page in document:
                    for block in page.get_text('dict')['blocks']:
                        if block['type'] != 0:
                            continue
                        for line in block['lines']:
                            for span in line['spans']:
                                for word, size in [('Глава', 22), ('Параграф', 16), ('Подраздел', 14),
                                                   ('Глубокий', 13), ('Листинг', 13), ('Ячейка', 13),
                                                   ('Подпись', 11)]:
                                    if word in span['text']:
                                        seen.add(word)
                                        self.assertAlmostEqual(span['size'], size * 72 / 72.27, delta=.02)
                                        if word == 'Подпись':
                                            self.assertFalse(span['flags'] & 2, 'Captions must be upright')
                self.assertEqual(seen, {'Глава', 'Параграф', 'Подраздел', 'Глубокий',
                                        'Листинг', 'Ячейка', 'Подпись'})

    def test_editorial_book_layout_metadata_and_shared_content(self):
        import pymupdf
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ('utils/pdf', 'utils/latex/tex/latex', 'utils/site/fonts'):
                shutil.copytree(REPO_ROOT / directory, root / directory)
            book = root / 'handbooks/example'
            chapter = book / '01-section'
            paragraph = chapter / '01-paragraph'
            paragraph.mkdir(parents=True)
            title = 'Синтетическая книга: 50% & {пример}'
            (root / 'handbooks/handbooks.yml').write_text(yaml.safe_dump(dict(
                title='Каталог', description='Описание', handbooks=[dict(
                    slug='example', title=title, description='Описание')]), allow_unicode=True))
            (book / 'meta.yml').write_text(yaml.safe_dump(dict(chapters=['01-section'],
                contributors=[dict(name='Участник проекта')]), allow_unicode=True))
            for folder, metadata in [(chapter, dict(slug='section', paragraphs=['01-paragraph'])),
                                     (paragraph, dict(slug='paragraph'))]:
                metadata.update(title='Раздел книги', description='Описание', authors=['Автор раздела'], status='draft', build=True)
                (folder / 'meta.yaml').write_text(yaml.safe_dump(metadata, allow_unicode=True))
                (folder / 'README.md').write_text('# Описание')
            (book / 'content.md').write_text('Предисловие.\n\n<!-- handbook-contributors -->')
            annotation = r'Аннотация: 50% & #1 {текст} \input{secret}.'
            publication = dict(kind='Учебные материалы', status='Издательский макет', audience='Для читателей 15–18 лет.',
                annotation=annotation, edition='Первая редакция',
                classification={key: dict(value=value, status='preliminary', rationale='Тематический подбор',
                    sources=['https://example.org/catalog']) for key, value in
                    [('udk', '004.8'), ('bbk', '32.8'), ('author_mark', 'Т12')]},
                publisher=dict(value='Синтетический издатель', source='Подтверждение'),
                place=dict(value='Проверенный город', source='Подтверждение'),
                year=dict(value='2025', source='Редактор'),
                reviewers=dict(value='Рецензент & коллеги', source='Подтверждение'),
                approval=dict(value='Подтверждённые сведения об утверждении', source='Подтверждение'),
                isbn=dict(value='978-0-306-40615-7', source='Письмо агентства'))
            (book / 'publication.yml').write_text(yaml.safe_dump(publication, allow_unicode=True))
            (paragraph / 'figure.svg').write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40">'
                '<rect width="80" height="40" fill="white"/>'
                '<text x="4" y="25">Vector</text></svg>')
            content = '''## Кириллица и формулы {#target}

Русский текст, Latin, λ и $\\frac{1}{2} + x_i^2 \\leq \\sqrt{3}$.
[Внутренняя ссылка](#target), [внешняя ссылка](https://example.org/).
[example.org/downloads/platform/install](https://example.org/downloads/platform/install).

![Вектор](figure.svg)

*Рис. 7. Подпись рисунка.*

<details><summary>Подсказка</summary>

Подсказка полностью видна.

</details>

*Таблица 1 — Длинная таблица*

| Значение | Описание |
| --- | --- |
'''
            content += '\n'.join(f'| {i} | Строка таблицы |' for i in range(80))
            content += '\n\n' + r'$$a=\frac{123+456}{789},\qquad b=\frac{456+789}{123},\qquad c=\frac{789+123}{456}.$$' + '\n\n'
            content += '\n\n' + r'$$Q=\frac{(0{,}123-1)\cdot7+(0{,}456-0)\cdot3}{5}=\frac{-0{,}789+0{,}123}{5}\approx-0{,}133.$$' + '\n\n'
            content += 'Длинный идентификатор в строке: `SyntheticLongIdentifierWithoutSeparators`.\n\n'
            content += '''

*Таблица 2 — Измерения*

| Последовательность | Измерение первое | Измерение второе | Измерение третье | Среднее значение |
| --- | --- | --- | --- | --- |
| Базовая | 123,456 | 234,567 | 345,678 | 234,567 |

*Таблица 3 — Метки*

| acceleration | verification | classification | measurement | comparison | probability | prediction | explanation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
'''
            content += '\n\n```python\n' + '\n'.join(f'print({i})' for i in range(55)) + '\n```\n'
            content += '\n```python\n# Очень длинная строка\nprint("' + 'abcdefgh ' * 30 + '")\n```\n'
            (paragraph / 'content.md').write_text(content)
            with patch.dict(os.environ, BUILD_CACHE_DIR=str(root / 'cache'), BUILD_CACHE_DISABLE='0'), \
                    patch('handbook_pdf.source_revision', return_value=('revision-test', '2026-01-02')):
                with redirect_stdout(io.StringIO()):
                    build(root, selected=book, book_only=True, profile='belarus-textbook', jobs=1)
            pdf = root / 'output/pdf/belarus-textbook/example/handbook.pdf'
            with pymupdf.open(pdf) as document:
                self.assertGreater(len(document), 5)
                self.assertTrue(document.get_toc())
                self.assertEqual(document.metadata['title'], title)
                text = '\n'.join(page.get_text() for page in document)
                cover = ' '.join(document[0].get_text().split())
                self.assertEqual(cover.count(title), 1)
                self.assertEqual(cover.count(publication['kind']), 1)
                self.assertIn('Проверенный город', cover)
                self.assertIn('Синтетический издатель', cover)
                self.assertIn('2025', cover)
                self.assertIn('Рецензент & коллеги', document[1].get_text())
                self.assertIn(publication['approval']['value'],
                              ' '.join(document[1].get_text().replace('-\n', '').split()))
                self.assertIn('Аннотация: 50% & #1', text)
                self.assertIn(r'\input{secret}', text, 'Metadata must be escaped, never executed')
                self.assertIn('ISBN: 978-0-306-40615-7', text)
                self.assertIn('предварительные', document[1].get_text())
                self.assertIn('Участник проекта', text)
                self.assertIn('Автор раздела', text)
                self.assertIn('Подсказка полностью видна.', text)
                self.assertIn('Дата исходников: 2026-01-02', text)
                self.assertIn('Год издания: 2025', text)
                self.assertNotIn('revision-test', document[0].get_text())
                for page in document[:2]:
                    self.assertFalse(page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, 45)).strip())
                    self.assertFalse(page.get_text(clip=pymupdf.Rect(0, page.rect.height - 35,
                                                                    page.rect.width, page.rect.height)).strip())
                # Classification and annotations have no prose paragraph indent.
                self.assertAlmostEqual(document[1].search_for('УДК')[0].x0,
                                       document[1].search_for('Аннотация')[0].x0, delta=.2)
                self.assertIn(title, ' '.join(document[-1].get_text().split()))
                self.assertFalse(document[-1].get_text(clip=pymupdf.Rect(0, 0, document[-1].rect.width, 45)).strip())
                self.assertIn(str(len(document)), document[-1].get_text(clip=pymupdf.Rect(
                    0, document[-1].rect.height - 40, document[-1].rect.width, document[-1].rect.height)))
                for number, page in enumerate(document, 1):
                    if number <= 2 or number == len(document) or number % 2:
                        continue
                    header = page.get_text(clip=pymupdf.Rect(0, 0, page.rect.width, 45))
                    self.assertIn(title, ' '.join(header.split()))
                    self.assertNotIn('BelOAI', header)
                    page_number = next(word for word in page.get_text('words')
                                       if word[4] == str(number) and word[1] < 45)
                    title_words = [word for word in page.get_text('words') if word[1] < 45 and word != page_number]
                    self.assertLess(page_number[2] + 5, min(word[0] for word in title_words))
                self.assertNotIn('??', text)
                self.assertNotIn('Последовательность', text,
                                 'The long first word must wrap inside its narrow table cell')
                self.assertNotIn('classification', text,
                                 'Latin labels must wrap even with Russian hyphenation selected')
                links = [link for page in document for link in page.get_links()]
                self.assertTrue(any(link.get('page', -1) >= 0 for link in links),
                                'Internal links must resolve to a page, including named destinations')
                self.assertTrue(any(link.get('uri') == 'https://example.org/' for link in links))
                for page in document:
                    self.assertAlmostEqual(page.rect.width * 25.4 / 72, 170, delta=.1)
                    self.assertAlmostEqual(page.rect.height * 25.4 / 72, 240, delta=.1)
                    for block in page.get_text('blocks'):
                        self.assertGreaterEqual(block[0], -1)
                        self.assertLessEqual(block[2], page.rect.width + 1)
                        self.assertGreaterEqual(block[1], 0)
                        self.assertLessEqual(block[3], page.rect.height)
                self.assertTrue(any('Значение' in page.get_text() for page in document[4:]))
            fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True)
            self.assertNotIn('Type 3', fonts)
            for line in fonts.splitlines()[2:]:
                self.assertEqual(line.split()[-5], 'yes', 'Every font must be embedded')

    def test_unicode_lambda_in_prose_math_and_code(self):
        import pymupdf
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with pymupdf.open() as logo:
                logo.new_page(width=80, height=20)
                logo.save(folder / 'logo.pdf')
            (folder / 'header.tex').write_text(
                '\\usepackage{academichandbook}\n\\renewcommand{\\handbooklogo}{logo.pdf}\n'
                '\\title{Проверка Unicode}\n')
            source = '''Параметр λ задаёт штраф.

Формула: $λ = 2$.

```python
print("λ =", 2)
```
'''
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//' + os.pathsep + os.environ.get('TEXINPUTS', ''))
            result = subprocess.run(
                ['pandoc', '-f', 'markdown', '--pdf-engine=pdflatex',
                 '--include-in-header', 'header.tex', '-V', 'fontenc:T2A',
                 '-V', 'fontfamily:handbookfonts', '-o', 'unicode.pdf'],
                input=source, cwd=folder, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            with pymupdf.open(folder / 'unicode.pdf') as document:
                self.assertEqual(len(document), 1)
                self.assertEqual(document[0].get_text().count('λ'), 3)

    def test_centered_objects_and_explicit_caption_positions(self):
        import pymupdf
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with pymupdf.open() as graphic:
                page = graphic.new_page(width=80, height=40)
                page.draw_rect(page.rect, color=None, fill=(.1, .8, .2))
                graphic.save(folder / 'small.pdf')
            source = '''![Альтернативное описание](small.pdf)

*Рис. 7. Короткая подпись.*

*Таблица 3 — Короткая подпись*

| Объект | Число |
| :--- | ---: |
| А | 2 |
'''
            ast = json.loads(subprocess.check_output(
                ['pandoc', '-f', 'markdown-implicit_figures', '-t', 'json'], input=source, text=True))
            (folder / 'source.json').write_text(json.dumps(format_objects(ast)))
            (folder / 'header.tex').write_text(
                '\\usepackage{academichandbook}\n\\renewcommand{\\handbooklogo}{small.pdf}\n'
                '\\title{Проверка оформления}\n')
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//' + os.pathsep + os.environ.get('TEXINPUTS', ''))
            result = subprocess.run(
                ['pandoc', 'source.json', '-f', 'json', '--pdf-engine=pdflatex',
                 '--lua-filter', str(REPO_ROOT / 'utils/pdf/keep-short-code.lua'),
                 '--include-in-header', 'header.tex', '-V', 'fontenc:T2A',
                 '-V', 'fontfamily:handbookfonts', '-o', 'objects.pdf'],
                cwd=folder, env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr[-3000:])
            with pymupdf.open(folder / 'objects.pdf') as document:
                self.assertEqual(len(document), 1)
                page = document[0]
                text = page.get_text()
                self.assertEqual(text.count('Рисунок 7'), 1)
                self.assertEqual(text.count('Таблица 3'), 1)
                self.assertNotIn('Альтернативное описание', text)
                # The first green rectangle is the header logo; the second is
                # the actual small figure, which must not be stretched.
                shapes = sorted((path['rect'] for path in page.get_drawings()
                                 if path['fill'] and abs(path['fill'][1] - .8) < .01), key=lambda rect: rect.y0)
                self.assertEqual(len(shapes), 2)
                figure = shapes[1]
                self.assertAlmostEqual(figure.width, 80, delta=.5)
                self.assertAlmostEqual((figure.x0 + figure.x1) / 2, page.rect.width / 2, delta=1)
                labels = {}
                for prefix in ('Рисунок', 'Таблица'):
                    words = page.get_text('words')
                    first = next(word for word in words if word[4] == prefix)
                    line = [word for word in words if abs(word[1] - first[1]) < 1]
                    labels[prefix] = pymupdf.Rect(min(word[0] for word in line), min(word[1] for word in line),
                                                max(word[2] for word in line), max(word[3] for word in line))
                    self.assertAlmostEqual((labels[prefix].x0 + labels[prefix].x1) / 2,
                                           page.rect.width / 2, delta=1)
                self.assertLess(figure.y1, labels['Рисунок'].y0)
                table_header = next(word for word in page.get_text('words') if word[4] == 'Объект')
                self.assertLess(labels['Таблица'].y1, table_header[1])

    def test_captions_stay_with_objects_at_page_boundaries_in_both_profiles(self):
        import pymupdf
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            with pymupdf.open() as graphic:
                page = graphic.new_page(width=120, height=70)
                page.insert_text((8, 35), 'FigureContent')
                graphic.save(folder / 'figure.pdf')
            with pymupdf.open() as logo:
                logo.new_page(width=80, height=20)
                logo.save(folder / 'logo.pdf')
            source = (r'\null\par\vspace*{.90\textheight}\par' + '\n\n'
                      '![Описание](figure.pdf)\n\n*Рисунок 1 — FigureCaption*\n\n'
                      + r'\clearpage\null\par\vspace*{.97\textheight}\par' + '\n\n'
                      '*Таблица 1 — TableCaption*\n\n| ColumnHead | Value |\n| --- | ---: |\n'
                      '| Startrow | 0 |\n'
                      + '\n'.join(f'| Row{i} | {i} |' for i in range(1, 90))
                      + '\n| Endrow | 90 |\n')
            ast = json.loads(subprocess.check_output(
                ['pandoc', '-f', 'markdown-implicit_figures', '-t', 'json'], input=source, text=True))
            (folder / 'source.json').write_text(json.dumps(format_objects(ast)))
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//'
                       + os.pathsep + os.environ.get('TEXINPUTS', ''))
            for package in ('academichandbook', 'belarustextbook'):
                with self.subTest(package=package):
                    (folder / 'header.tex').write_text(
                        '\\usepackage{' + package + '}\n'
                        '\\renewcommand{\\handbooklogo}{logo.pdf}\n\\title{Проверка}\n')
                    result = subprocess.run(
                        ['pandoc', 'source.json', '-f', 'json', '--pdf-engine=pdflatex',
                         '--lua-filter', str(REPO_ROOT / 'utils/pdf/keep-short-code.lua'),
                         '--include-in-header', 'header.tex', '-V', 'fontenc:T2A', '-V', 'lang:ru-RU',
                         '-V', 'fontfamily:handbookfonts', '-V', 'fontsize:12pt', '-V', 'papersize:a4',
                         '-V', 'classoption:twoside', '-o', 'objects.pdf'],
                        cwd=folder, env=env, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr[-3000:])
                    with pymupdf.open(folder / 'objects.pdf') as document:
                        def find(text):
                            return [(i, rect) for i, page in enumerate(document) for rect in page.search_for(text)]
                        figure, caption = find('FigureContent'), find('FigureCaption')
                        table, first, last = find('TableCaption'), find('Startrow'), find('Endrow')
                        for name, matches in [('figure', figure), ('caption', caption), ('table', table),
                                              ('first', first), ('last', last)]:
                            self.assertEqual(len(matches), 1, name + ': ' + '\n'.join(page.get_text() for page in document))
                        self.assertEqual(figure[0][0], caption[0][0])
                        self.assertGreater(figure[0][0], 0, 'Figure must move off the nearly full page')
                        self.assertGreater(caption[0][1].y0, figure[0][1].y1)
                        self.assertLess(caption[0][1].y0 - figure[0][1].y1, 60)
                        self.assertEqual(table[0][0], first[0][0])
                        self.assertGreater(first[0][1].y0, table[0][1].y1)
                        self.assertLess(first[0][1].y0 - table[0][1].y1, 60)
                        self.assertGreater(last[0][0], first[0][0])
                        for i in range(first[0][0], last[0][0] + 1):
                            self.assertIn('ColumnHead', document[i].get_text())

    def test_graphics_dimensions_with_legacy_and_current_pandoc_defaults(self):
        import pymupdf
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            colors = {'logo': (0.1, 0.2, 0.7), 'wide': (0.1, 0.8, 0.2), 'tall': (0.8, 0.2, 0.1)}
            for name, width, height in [('logo', 141.25, 18.79), ('wide', 400, 200), ('tall', 100, 400)]:
                document = pymupdf.open()
                page = document.new_page(width=width, height=height)
                page.draw_rect(page.rect, color=None, fill=colors[name])
                document.save(folder / f'{name}.pdf')
                if name == 'wide':
                    page.get_pixmap().save(folder / 'raster.png')
                document.close()
            legacy = r'''
\makeatletter
\def\maxwidth{\ifdim\Gin@nat@width>\linewidth\linewidth\else\Gin@nat@width\fi}
\def\maxheight{\ifdim\Gin@nat@height>\textheight\textheight\else\Gin@nat@height\fi}
\makeatother
\setkeys{Gin}{width=\maxwidth,height=\maxheight,keepaspectratio}
'''
            template = r'''
\documentclass[a4paper,10pt]{article}
\usepackage[T2A]{fontenc}
\usepackage[russian]{babel}
\usepackage{amsmath,amssymb,graphicx,hyperref}
%GRAPHICS_DEFAULTS%
\usepackage{academichandbook}
\renewcommand{\handbooklogo}{logo.pdf}
\title{Синтетический документ}
\begin{document}
\includegraphics[width=.85\linewidth]{wide.pdf}
\clearpage
\includegraphics[width=.85\linewidth]{tall.pdf}
\clearpage
\includegraphics[width=.85\linewidth]{raster.png}
\end{document}
'''
            env = dict(os.environ, TEXINPUTS=str(REPO_ROOT / 'utils/latex/tex/latex') + '//' + os.pathsep + os.environ.get('TEXINPUTS', ''))
            for mode, defaults in [('current', ''), ('legacy', legacy)]:
                with self.subTest(mode=mode):
                    (folder / 'sizing.tex').write_text(template.replace('%GRAPHICS_DEFAULTS%', defaults))
                    for _ in range(2):
                        result = subprocess.run(['pdflatex', '-halt-on-error', '-interaction=nonstopmode', 'sizing.tex'],
                                                cwd=folder, env=env, text=True, capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
                    with pymupdf.open(folder / 'sizing.pdf') as document:
                        self.assertEqual(len(document), 3)
                        # olymp's 175 mm text width, 250 mm text height; PDF uses bp.
                        pt_per_mm = 72 / 25.4
                        width = .85 * 175 * pt_per_mm
                        height = .78 * 250 * pt_per_mm
                        for page in document:
                            logos = [path['rect'] for path in page.get_drawings()
                                     if path['fill'] and all(abs(a - b) < .01 for a, b in zip(path['fill'], colors['logo']))]
                            self.assertEqual(len(logos), 1)
                            self.assertAlmostEqual(logos[0].width, 34 * pt_per_mm, delta=.5)
                            self.assertAlmostEqual(logos[0].width / logos[0].height, 141.25 / 18.79, delta=.02)
                        for page, name, expected_width, expected_height in [
                                (document[0], 'wide', width, width / 2),
                                (document[1], 'tall', height / 4, height)]:
                            boxes = [path['rect'] for path in page.get_drawings()
                                     if path['fill'] and all(abs(a - b) < .01 for a, b in zip(path['fill'], colors[name]))]
                            self.assertEqual(len(boxes), 1)
                            self.assertAlmostEqual(boxes[0].width, expected_width, delta=.5)
                            self.assertAlmostEqual(boxes[0].height, expected_height, delta=.5)
                        raster = pymupdf.Rect(document[2].get_image_info()[0]['bbox'])
                        self.assertAlmostEqual(raster.width, width, delta=.5)
                        self.assertAlmostEqual(raster.height, width / 2, delta=.5)

    def test_logo_cache_and_font_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(REPO_ROOT / 'utils/pdf', root / 'utils/pdf')
            shutil.copytree(REPO_ROOT / 'utils/site/fonts', root / 'utils/site/fonts')
            scratch = root / 'scratch'
            scratch.mkdir()
            calls = []

            def fake_run(command, **kwargs):
                calls.append(command)
                if command[0] == 'xelatex':
                    (kwargs['cwd'] / 'logo.pdf').write_bytes(b'%PDF-test-logo')
                return ''

            with patch.dict(os.environ, BUILD_CACHE_DIR=str(root / 'cache'), BUILD_CACHE_DISABLE='0'), \
                    patch('handbook_pdf.run', side_effect=fake_run):
                prepare_logo(root, scratch, 'environment')
                prepare_logo(root, scratch, 'environment')
                self.assertEqual(sum(c[0] == 'xelatex' for c in calls), 1)
                font = root / 'utils/site/fonts/unbounded-latin-cyrillic.woff2'
                from fontTools.ttLib import TTFont
                with TTFont(font) as changed:
                    changed['name'].setName('Changed test font metadata', 10, 3, 1, 0x409)
                    changed.save(font)
                prepare_logo(root, scratch, 'environment')
                self.assertEqual(sum(c[0] == 'xelatex' for c in calls), 2)
                template = root / 'utils/pdf/logo.tex'
                template.write_text(template.read_text() + '\n% new logo\n')
                prepare_logo(root, scratch, 'environment')
                self.assertEqual(sum(c[0] == 'xelatex' for c in calls), 3)

    def test_reader_fonts_navigation_and_page_furniture(self):
        import pymupdf
        import subprocess

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ('utils/pdf', 'utils/latex/tex/latex', 'utils/site/fonts'):
                shutil.copytree(REPO_ROOT / directory, root / directory)
            books = []
            for slug in ('alpha', 'beta'):
                book = root / 'handbooks' / slug
                chapter = book / '01-section'
                paragraph = chapter / '01-paragraph'
                paragraph.mkdir(parents=True)
                (book / 'meta.yml').write_text(yaml.safe_dump(dict(chapters=['01-section'],
                    contributors=[dict(name='Синтетический Автор', github='writer')]), allow_unicode=True))
                books.append(dict(slug=slug, title='Синтетический учебник с длинным названием для проверки колонтитула',
                                  description='Описание'))
                for folder, metadata in [(chapter, dict(slug='section', paragraphs=['01-paragraph'])),
                                         (paragraph, dict(slug='paragraph'))]:
                    metadata.update(title=('Глава' if folder == chapter else 'Материал') + ' синтетической книги', description='Описание',
                                    authors=['Автор'], status='draft', build=True)
                    (folder / 'meta.yaml').write_text(yaml.safe_dump(metadata, allow_unicode=True))
                    (folder / 'README.md').write_text('# Описание')
                (book / 'content.md').write_text('Введение в синтетический учебник.' +
                    ('\n\n<!-- handbook-contributors -->\n' if slug == 'alpha' else ''))
                (paragraph / 'figure.svg').write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="200">'
                    '<rect width="80" height="200" fill="white"/>'
                    '<text x="4" y="25" font-family="Liberation Serif, serif">Vector</text></svg>')
                content = '''## Проверка текста {#target}

Русский текст и Latin text. Символы: → ← ⇒ ≈ ≤ ≥ ≠ − ▶ ⋯.
Формула: $\\frac{1}{2} + x_i^2 \\leq \\sqrt{3}$.
[Внутренняя ссылка](#target), [соседний раздел](../01-paragraph/content.md#target).

![Векторный рисунок](figure.svg)

*Рисунок 1 — Векторный рисунок*

```python
# Кириллица в листинге
print("short")
```

<details><summary>Подсказка</summary>

Подсказка полностью видна.

</details>

### Заголовок следующего уровня
#### Ещё один уровень
##### Глубокий заголовок
###### Последний уровень

Текст под глубоким заголовком.

*Таблица 1 — Длинная таблица*

| Значение | Описание |
| --- | --- |
'''
                content += '\n'.join(f'| {i} | Строка длинной таблицы |' for i in range(90))
                content += '\n\n```python\n' + '\n'.join(f'print({i})' for i in range(55)) + '\n```\n'
                (paragraph / 'content.md').write_text(content)
            (root / 'handbooks/handbooks.yml').write_text(yaml.safe_dump(
                dict(title='Каталог', description='Описание', handbooks=books), allow_unicode=True))
            with patch.dict(os.environ, BUILD_CACHE_DIR=str(root / 'cache'), BUILD_CACHE_DISABLE='0'):
                with redirect_stdout(io.StringIO()):
                    build(root, jobs=1)
            for pdf in (root / 'output/pdf').rglob('*.pdf'):
                with self.subTest(pdf=pdf.relative_to(root)):
                    document = pymupdf.open(pdf)
                    self.assertGreater(len(document), 1)
                    self.assertTrue(document.get_toc())
                    self.assertTrue(any(page.get_links() for page in document))
                    full_text = '\n'.join(page.get_text() for page in document)
                    if pdf.name == 'handbook.pdf':
                        self.assertNotIn('Содержание', document[0].get_text())
                        inline_authors = pdf.parent.name == 'alpha'
                        toc_page = 1 if inline_authors else 2
                        author_page = toc_page + 1 if inline_authors else 1
                        self.assertIn('Синтетический Автор', document[author_page].get_text())
                        self.assertIn('@writer', document[author_page].get_text())
                        self.assertIn('Содержание', document[toc_page].get_text())
                        self.assertIn('Редакция:', document[0].get_text())
                        self.assertNotIn('Страница', document[0].get_text())
                        self.assertIn('Введение в синтетический учебник.', document[toc_page + 1].get_text())
                        self.assertIn('Глава синтетической книги', document[toc_page + 2].get_text())
                        header = document[-1].get_text(clip=pymupdf.Rect(0, 0, document[-1].rect.width, 60))
                        self.assertIn('Глава синтетической книги', header)
                        self.assertIn('Материал синтетической книги', header)
                    self.assertIn('Подсказка полностью видна.', full_text)
                    self.assertNotIn('??', full_text)
                    for number, page in enumerate(document, 1):
                        text = page.get_text()
                        self.assertIn('BelOAI', text)
                        self.assertIn('.team', text)
                        if pdf.name == 'handbook.pdf' and number == 1:
                            continue
                        self.assertIn(f'Страница {number} из {len(document)}', text)
                        self.assertEqual(page.get_images(), [], 'Рисунки и логотип должны оставаться векторными')
                        footer = page.search_for(f'Страница {number} из {len(document)}')[0]
                        for block in page.get_text('blocks'):
                            self.assertGreaterEqual(block[1], 0)
                            self.assertLessEqual(block[3], page.rect.height)
                            if 'Векторный рисунок' in block[4]:
                                self.assertLess(block[3], footer.y0 - 12, 'Подпись не должна касаться колонтитула')
                    fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True)
                    self.assertNotIn('Type 3', fonts)
                    # Chromium keeps SVG typography in imported Form XObjects.
                    # Only direct page resources belong to the LaTeX reader;
                    # imported figures may legitimately use Liberation/DejaVu.
                    main_fonts = '\n'.join(font[3] for page in document
                                           for font in page.get_fonts(full=True) if font[6] == 0)
                    for forbidden in ('Liberation', 'DejaVu', 'LMRoman', 'LMSans'):
                        self.assertNotIn(forbidden, main_fonts)
                    figure_fonts = {span['font'] for page in document
                                    for block in page.get_text('dict')['blocks'] if block['type'] == 0
                                    for line in block['lines'] for span in line['spans'] if span['text'] == 'Vector'}
                    self.assertTrue(figure_fonts, 'Текст SVG должен сохраняться в PDF')
                    self.assertTrue(figure_fonts.isdisjoint(font.split('+')[-1] for font in main_fonts.splitlines()),
                                    'SVG использует собственный импортированный шрифт')
                    self.assertIn('Unbounded', fonts)
                    self.assertIn('IBMPlexSans', fonts)
                    self.assertRegex(main_fonts, r'(SFRM|SFBX|CMR)')
                    self.assertRegex(main_fonts, r'(SFTT|CMTT)')
                    document.close()
