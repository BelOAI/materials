"""Единое оформление объектов на синтетическом Markdown, без реальных глав."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_pdf import format_objects, require_object_captions, walk
from repo_paths import REPO_ROOT


class Captions(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.labels, self.current, self.images, self.tables = [], None, [], 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in {'caption', 'figcaption'}:
            self.current = [tag, '']
        if tag == 'img':
            self.images.append(dict(attrs)['alt'])
        if tag == 'table':
            self.tables += 1

    def handle_data(self, data):
        if self.current:
            self.current[1] += data

    def handle_endtag(self, tag):
        if self.current and tag == self.current[0]:
            self.labels.append(tuple(self.current))
            self.current = None


SOURCE = '''![Два разных значения](small.svg)

*Рис. 7. Значения **до** и `после`.*

*Таблица 3 — Результаты*

| Объект | Значение |
| :--- | ---: |
| А | 2 |

![Только альтернативное описание](plain.svg)

*Рисунок 8 — Не единая подпись* и *обычный текст*

Текст с ![встроенным рисунком](inline.svg) внутри предложения.

*Рисунок 9 — Отдельное упоминание*

Это обычный абзац.

```markdown
![Пример](example.svg)

*Рисунок 1 — Не подпись*
```

> ![Описание в цитате](nested.svg)
>
> *Рисунок 2 — Вложенный рисунок*

*Таблица 4 — Нет таблицы*

Обычный текст.
'''


class HandbookObjectsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('pandoc'), 'Нужен Pandoc')
    def test_print_lesson_heading_reserves_space_for_credit_and_following_heading(self):
        ast = json.loads(subprocess.check_output(['pandoc', '-f', 'markdown', '-t', 'json'],
                                                input='## Synthetic\n\nBody.', text=True))
        ast['blocks'][0]['c'][1][1].append('handbook-lesson-opening')
        latex = subprocess.check_output(['pandoc', '-f', 'json', '-t', 'latex', '--lua-filter',
                                         str(REPO_ROOT / 'utils/pdf/keep-short-code.lua')],
                                        input=json.dumps(ast), text=True)
        self.assertIn(r'\Needspace{10\baselineskip}', latex)

    @unittest.skipUnless(shutil.which('pandoc') and shutil.which('node'), 'Нужны Pandoc и Node.js')
    def test_publishing_rejects_missing_captions_including_nested_objects(self):
        labelled = ('![Описание](figure.svg)\n\n*Рисунок 1 — Пример*\n\n'
                    '*Таблица 1 — Значения*\n\n| Имя | Число |\n| --- | ---: |\n| А | 2 |\n')
        for source in (labelled, '> ' + labelled.replace('\n', '\n> '),
                       '![Описание](figure.svg)', '| Имя |\n| --- |\n| А |',
                       '> ![Описание](figure.svg)',
                       '![Описание](figure.svg)\n\nОбычный текст.\n\n*Рисунок 1 — Далеко*'):
            with self.subTest(source=source):
                ast = json.loads(subprocess.check_output(
                    ['pandoc', '-f', 'markdown-implicit_figures', '-t', 'json'], input=source, text=True))
                result = subprocess.run(['node', str(REPO_ROOT / 'utils/site/render-handbook.mjs')],
                                        input=json.dumps([dict(source=source, name='synthetic', requireCaptions=True)]),
                                        capture_output=True, text=True)
                if 'Значения' in source:
                    require_object_captions(format_objects(ast), 'synthetic')
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    with self.assertRaisesRegex(ValueError, 'synthetic:.*подписи'):
                        require_object_captions(format_objects(ast), 'synthetic')
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('synthetic:', result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Нужен Node.js')
    def test_site_semantic_captions_and_untouched_prose(self):
        result = subprocess.run(['node', str(REPO_ROOT / 'utils/site/render-handbook.mjs')],
                                input=json.dumps([dict(source=SOURCE, name='synthetic')]),
                                capture_output=True, text=True, check=True)
        html = json.loads(result.stdout)[0]['html']
        parsed = Captions(html)
        self.assertEqual(parsed.labels, [('figcaption', 'Рисунок 7 — Значения до и после'),
                                         ('figcaption', 'Таблица 3 — Результаты'),
                                         ('figcaption', 'Рисунок 2 — Вложенный рисунок')])
        self.assertEqual(parsed.tables, 1)
        self.assertIn('Два разных значения', parsed.images)
        self.assertEqual(html.count('<figure class="handbook-figure"'), 3)
        self.assertIn('<strong>до</strong>', html)
        self.assertIn('<code>после</code>', html)
        self.assertIn('style="text-align:right"', html)
        self.assertIn('aria-labelledby="handbook-table-caption-1"', html)
        self.assertLess(html.index('Таблица 3 — Результаты'), html.index('class="handbook-table-scroll"'))
        self.assertIn('<em>Рисунок 9 — Отдельное упоминание</em>', html)
        self.assertIn('<em>Рисунок 8 — Не единая подпись</em> и <em>обычный текст</em>', html)
        self.assertIn('<em>Таблица 4 — Нет таблицы</em>', html)
        self.assertIn('Текст с <img', html)

    @unittest.skipUnless(shutil.which('pandoc'), 'Нужен Pandoc')
    def test_pdf_captions_match_site_without_implicit_alt_caption(self):
        ast = json.loads(subprocess.check_output(
            ['pandoc', '-f', 'markdown-implicit_figures', '-t', 'json'], input=SOURCE, text=True))
        original = deepcopy(ast)
        formatted = format_objects(ast)
        self.assertEqual(ast, original)
        latex = subprocess.check_output(
            ['pandoc', '-f', 'json', '-t', 'latex', '--lua-filter',
             str(REPO_ROOT / 'utils/pdf/keep-short-code.lua')], input=json.dumps(formatted), text=True)
        self.assertEqual(latex.count('\\begin{figure}[H]\\centering'), 3)
        self.assertEqual(latex.count('\\caption*{'), 2)
        self.assertIn(r'\caption*{Рисунок 7 --- Значения \textbf{до} и \texttt{после}}', latex)
        self.assertIn(r'\caption{Таблица 3 --- Результаты}', latex)
        self.assertNotIn(r'\caption{Только альтернативное описание}', latex)
        self.assertIn(r'\emph{Рисунок 9 --- Отдельное упоминание}', latex)
        images = [node for node in walk(formatted) if node.get('t') == 'Image']
        self.assertEqual(images[0]['c'][1], original['blocks'][0]['c'][0]['c'][1])
        self.assertEqual([node for node in walk(formatted) if node.get('t') == 'CodeBlock'],
                         [node for node in walk(original) if node.get('t') == 'CodeBlock'])

    def test_linked_images_and_caption_kind_mismatch(self):
        image = {'t': 'Image', 'c': [['', [], []], [], ['image.svg', '']]}
        linked = {'t': 'Para', 'c': [{'t': 'Link', 'c': [['', [], []], [image], ['full.svg', '']]}]}
        label = {'t': 'Para', 'c': [{'t': 'Emph', 'c': [{'t': 'Str', 'c': 'Таблица 1 — Название'}]}]}
        result = format_objects([linked, label])
        self.assertEqual(result[0]['t'], 'Div')
        self.assertEqual(result[0]['c'][1], [linked])
        self.assertEqual(result[1], label)


if __name__ == '__main__':
    unittest.main()
