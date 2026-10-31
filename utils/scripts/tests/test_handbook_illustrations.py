"""Общее оформление на синтетических SVG и автономных Python-генераторах."""
from pathlib import Path
from xml.etree import ElementTree as ET
import importlib.util
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'utils/illustrations'))
sys.path.insert(0, str(ROOT / 'utils/scripts'))
from style import BEGIN, END, CSS, normalize_svg, normalize_generator, standalone_block

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 80">
<title id="title">Пример</title><desc id="desc">Объяснение</desc>
<style id="local">.point { fill:var(--blue); }</style>
<defs><pattern id="pattern" width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 0L4 4"/></pattern></defs>
<rect x="10" y="20" width="40" height="20" fill="url(#pattern)"/>
<text x="60" y="40">x<tspan dy="-4">2</tspan><tspan dy="4"> + y</tspan></text>
</svg>'''
NS = {'s': 'http://www.w3.org/2000/svg'}


class IllustrationStyleTests(unittest.TestCase):
    def test_style_is_self_contained_and_repeatable(self):
        result = normalize_svg(SVG)
        self.assertEqual(normalize_svg(result), result)
        root = ET.fromstring(result)
        style = root.find('s:style[@id="handbook-style"]', NS).text
        self.assertIn('prefers-color-scheme:dark', style)
        self.assertIn('@media print', style)
        self.assertIn("'PT Sans','DejaVu Sans'", style)
        self.assertNotIn('@import', result)
        self.assertEqual(len(root.findall('s:style[@id="handbook-style"]', NS)), 1)
        self.assertIsNotNone(root.find('.//s:marker[@id="handbook-arrow"]', NS))

    def test_content_and_local_geometry_are_preserved(self):
        before, after = ET.fromstring(SVG), ET.fromstring(normalize_svg(SVG))
        for selector in ('s:rect', 's:text', 's:style[@id="local"]', './/s:pattern', 's:title', 's:desc'):
            a, b = before.find(selector, NS), after.find(selector, NS)
            self.assertEqual(a.attrib, b.attrib)
            self.assertEqual(''.join(a.itertext()).strip(), ''.join(b.itertext()).strip())
        self.assertEqual(after.get('viewBox'), before.get('viewBox'))

    def test_portable_block_runs_without_repository_imports(self):
        source = 'value = 42\n' + BEGIN + '\n# old\n' + END + '\nresult = value + 1\n'
        updated = normalize_generator(source)
        self.assertEqual(normalize_generator(updated), updated)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'standalone.py'
            path.write_text(updated)
            spec = importlib.util.spec_from_file_location('synthetic_plot', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.result, 43)
            self.assertEqual(module.CSS, CSS)
            self.assertEqual(module.normalize_svg(SVG), normalize_svg(SVG))

    def test_unmarked_or_ambiguous_generator_fails(self):
        for source in ('print(1)', standalone_block() + '\n' + standalone_block()):
            with self.assertRaises(ValueError):
                normalize_generator(source)

    def test_check_is_read_only_and_write_updates_once(self):
        spec = importlib.util.spec_from_file_location('illustration_command', ROOT / 'utils/scripts/handbook-illustrations.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'handbooks/example'
            folder.mkdir(parents=True)
            path = folder / 'figure.svg'
            source = SVG.replace('<title', '<style id="handbook-style">old</style><title', 1)
            path.write_text(source)
            self.assertEqual(module.synchronize(root), ['handbooks/example/figure.svg'])
            self.assertEqual(path.read_text(), source)
            self.assertEqual(module.synchronize(root, write=True), ['handbooks/example/figure.svg'])
            self.assertEqual(module.synchronize(root, write=True), [])
            self.assertEqual(path.read_text(), normalize_svg(source))
            path.write_text(SVG)
            with self.assertRaisesRegex(ValueError, 'нет отмеченного блока'):
                module.synchronize(root)


if __name__ == '__main__':
    unittest.main()
