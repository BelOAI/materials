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
