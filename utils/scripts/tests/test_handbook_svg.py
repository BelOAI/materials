"""Проверка настоящего векторного экспорта на синтетическом SVG."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_svg import render_svg, renderer_identity


@unittest.skipUnless(os.environ.get('PDF_RENDER_TESTS') == '1', 'Нужно PDF_RENDER_TESTS=1 и окружение utils/pdf')
class SvgRenderingTests(unittest.TestCase):
    def test_print_variables_patterns_text_and_vector_output(self):
        import pymupdf
        source = '''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="100" viewBox="0 0 160 100">
          <style>
            :root { --surface: #000; --marker: #000; }
            @media (prefers-color-scheme: dark) { :root { --surface: #111; } }
            @media print { :root { --surface: #f8fafc; --marker: #2563eb; } }
            text { font: 12px sans-serif; fill: #123456; }
          </style>
          <defs><pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M20 0H0V20" fill="none" stroke="#334155" stroke-width="2"/>
          </pattern></defs>
          <rect width="160" height="100" fill="var(--surface)"/>
          <rect x="10" y="10" width="40" height="20" fill="var(--marker)"/>
          <rect x="80" y="10" width="60" height="60" fill="url(#grid)"/>
          <text x="10" y="90">Printed SVG</text>
        </svg>'''
        with tempfile.TemporaryDirectory() as folder:
            svg, pdf = Path(folder) / 'figure.svg', Path(folder) / 'figure.pdf'
            svg.write_text(source)
            self.assertEqual(len(renderer_identity()), 2)
            render_svg(svg, pdf)
            with pymupdf.open(pdf) as document:
                self.assertEqual(len(document), 1)
                page = document[0]
                self.assertAlmostEqual(page.rect.width, 120, delta=1)
                self.assertAlmostEqual(page.rect.height, 75, delta=1)
                self.assertIn('Printed SVG', page.get_text())
                self.assertEqual(page.get_images(), [], 'SVG должен оставаться векторным')
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(4 / 3, 4 / 3))
                for position, expected in [((20, 20), (37, 99, 235)),
                                           ((70, 5), (248, 250, 252)),
                                           ((90, 15), (248, 250, 252))]:
                    actual = pixmap.pixel(*position)[:3]
                    self.assertTrue(all(abs(a - b) <= 5 for a, b in zip(actual, expected)),
                                    f'{position}: {actual} != {expected}')
                # На границе ячейки узора допустимо сглаживание, но сетка должна быть видна.
                grid = pixmap.pixel(100, 40)[:3]
                self.assertTrue(min(grid) >= 30 and max(grid) <= 140, grid)

    def test_invalid_svg_fails_without_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            svg, pdf = Path(folder) / 'broken.svg', Path(folder) / 'broken.pdf'
            svg.write_text('invalid SVG')
            with self.assertRaisesRegex(ValueError, 'SVG'):
                render_svg(svg, pdf)
            self.assertFalse(pdf.exists())
