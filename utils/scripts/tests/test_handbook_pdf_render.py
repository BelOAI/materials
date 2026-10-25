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
from handbook_pdf import build, prepare_logo
from repo_paths import REPO_ROOT


@unittest.skipUnless(os.environ.get('PDF_RENDER_TESTS') == '1', 'Нужно PDF_RENDER_TESTS=1 и окружение utils/pdf')
class HandbookPdfRenderingTests(unittest.TestCase):
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
            (root / 'CONTRIBUTORS.md').write_text('- [Синтетический Автор (@writer)](https://github.com/writer)')
            books = []
            for slug in ('alpha', 'beta'):
                book = root / 'handbooks' / slug
                chapter = book / '01-section'
                paragraph = chapter / '01-paragraph'
                paragraph.mkdir(parents=True)
                books.append(dict(slug=slug, title='Синтетический учебник с длинным названием для проверки колонтитула',
                                  description='Описание', chapters=['01-section']))
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
                    '<rect width="80" height="200" fill="white"/><text x="4" y="25">Vector</text></svg>')
                content = '''## Проверка текста {#target}

Русский текст и Latin text. Символы: → ← ⇒ ≈ ≤ ≥ ≠ −.
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
            (root / 'handbooks/handbooks.json').write_text(json.dumps(
                dict(title='Каталог', description='Описание', handbooks=books), ensure_ascii=False))
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
                    for forbidden in ('Liberation', 'DejaVu', 'LMRoman', 'LMSans'):
                        self.assertNotIn(forbidden, fonts)
                    self.assertIn('Unbounded', fonts)
                    self.assertIn('IBMPlexSans', fonts)
                    self.assertRegex(fonts, r'(SFRM|SFBX|CMR)')
                    self.assertRegex(fonts, r'(SFTT|CMTT)')
                    document.close()
