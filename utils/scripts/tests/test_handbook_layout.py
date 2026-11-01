"""Print-only layout rules on synthetic Pandoc nodes."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_layout import column_widths, layout_part, load_layout
from handbook_pdf import build


@unittest.skipUnless(shutil.which('pandoc'), 'Нужен Pandoc')
class LayoutTests(unittest.TestCase):
    def ast(self):
        source = ('*Таблица 1 — Пример*\n\n| Description | A | B |\n| --- | ---: | ---: |\n'
                  '| A long descriptive name with several words | 1.25 | 2.5 |\n'
                  '| Another descriptive name | 2.25 | 3.5 |\n')
        return json.loads(subprocess.check_output(['pandoc', '-f', 'markdown', '-t', 'json'], input=source, text=True))

    def test_content_sensitive_widths_and_unchanged_input(self):
        ast = self.ast()
        table = ast['blocks'][-1]
        original = deepcopy(ast)
        widths = column_widths(table)
        self.assertAlmostEqual(sum(widths), 1)
        self.assertGreater(widths[0], widths[1] * 1.5)
        result = layout_part(ast, 'book/chapter/lesson', Path('.'), {})
        self.assertEqual(ast, original)
        self.assertEqual(result['blocks'][-1]['c'][3:], table['c'][3:])

    def test_external_object_overrides_and_invalid_width_count(self):
        ast = self.ast()
        key = 'book/chapter/lesson/table:1'
        result = layout_part(ast, 'book/chapter/lesson', Path('.'), {key: {'widths': [.5, .25, .25], 'break_before': True}})
        wrapped = result['blocks'][-1]
        self.assertEqual(wrapped['t'], 'Div')
        self.assertEqual(wrapped['c'][1][0]['c'][1], r'\clearpage')
        self.assertEqual([s[1]['c'] for s in wrapped['c'][1][1]['c'][2]], [.5, .25, .25])
        with self.assertRaisesRegex(ValueError, 'число ширин'):
            layout_part(ast, 'book/chapter/lesson', Path('.'), {key: {'widths': [.5, .5]}})

    def test_invalid_layout_and_cli_combination_fail_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'layout.yml'
            p.write_text('objects:\n  object:\n    widths: [0.2, 0.2]\n')
            with self.assertRaises(ValueError):
                load_layout(p)
        with self.assertRaisesRegex(ValueError, '--press-ready'):
            build(profile='reader', book_only=True, press_ready=True)

    def test_quiz_prompt_group_preserves_order_and_all_content(self):
        ast = {'blocks': [
            {'t': 'Header', 'c': [3, ['q1', [], []], [{'t': 'Str', 'c': '1.'}, {'t': 'Str', 'c': 'Question'}]]},
            {'t': 'Para', 'c': [{'t': 'Str', 'c': 'Choices A B C D'}]},
            {'t': 'Para', 'c': [{'t': 'Str', 'c': 'Feedback stays after the prompt'}]},
        ]}
        original = deepcopy(ast)
        result = layout_part(ast, 'synthetic', Path('.'), {})
        self.assertEqual(ast, original)
        self.assertEqual(result['blocks'][0]['t'], 'Header')
        self.assertEqual(result['blocks'][1:], original['blocks'][1:])

    def test_list_intro_and_feedback_label_cannot_be_stranded(self):
        intro = {'t': 'Para', 'c': [{'t': 'Str', 'c': 'Следующие шаги:'}]}
        label = {'t': 'Para', 'c': [{'t': 'Strong', 'c': [{'t': 'Str', 'c': 'Подсказка'}]}]}
        body = {'t': 'Para', 'c': [{'t': 'Str', 'c': 'Текст подсказки'}]}
        ast = {'blocks': [intro, {'t': 'BulletList', 'c': [[body]]}, label, body]}
        result = layout_part(ast, 'synthetic', Path('.'), {})
        self.assertEqual(result['blocks'][0]['t'], 'RawBlock')
        self.assertEqual(result['blocks'][1], intro)
        self.assertEqual(result['blocks'][3]['t'], 'RawBlock')
        self.assertEqual(result['blocks'][-2:], [label, body])

    def test_raster_width_caps_at_300_ppi_without_modifying_asset(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            image = folder / 'image.png'
            Image.new('RGB', (600, 300), 'white').save(image)
            before = image.read_bytes()
            ast = {'blocks': [{'t': 'Para', 'c': [{'t': 'Image', 'c': [['', [], []], [], ['image.png', '']]}]}]}
            result = layout_part(ast, 'synthetic', folder, {})
            self.assertEqual(result['blocks'][0]['c'][0]['c'][0][2], [['width', '50.8000mm']])
            self.assertEqual(image.read_bytes(), before)
