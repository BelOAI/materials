"""Production export checks on synthetic PDFs, independent of textbook contents."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_press import prepare_document, finish_document, preflight, export_press, teaching_hashes, acquire_profile, PROFILE_SHA256


class PressTests(unittest.TestCase):
    def fixture(self, folder):
        import pymupdf
        with pymupdf.open() as doc:
            page = doc.new_page(width=170 / 25.4 * 72, height=240 / 25.4 * 72)
            page.insert_text((72, 90), 'Synthetic black text', fontsize=13)
            page.draw_rect(pymupdf.Rect(72, 120, 180, 170), color=(.1, .2, .8), fill=(.2, .6, .9))
            page.insert_link({'kind': pymupdf.LINK_URI, 'from': pymupdf.Rect(72, 75, 180, 95), 'uri': 'https://example.org'})
            doc.save(folder / 'source.pdf')

    def test_annotation_removal_blank_page_and_visible_text_preservation(self):
        import pymupdf
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.fixture(folder)
            prepare_document(folder / 'source.pdf', folder / 'prepared.pdf')
            reader = PdfReader(folder / 'prepared.pdf')
            self.assertEqual(len(reader.pages), 2)
            self.assertFalse(reader.pages[0].get('/Annots'))
            for page in reader.pages:
                self.assertEqual(page.mediabox, page.trimbox)
                self.assertEqual(page.mediabox, page.bleedbox)
            with pymupdf.open(folder / 'prepared.pdf') as doc:
                self.assertIn('Synthetic black text', doc[0].get_text())
                self.assertFalse(doc[1].get_text())
                self.assertFalse(doc[1].get_drawings())

    def test_missing_intent_and_rgb_fail_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self.fixture(folder)
            report = preflight(folder / 'source.pdf')
            self.assertFalse(report['passed'])
            self.assertTrue(any('OutputIntent' in message for message in report['errors']))
            self.assertTrue(any('цветовые' in message for message in report['errors']))
            self.assertFalse(report['pdfx_conformance_claimed'])

    def test_official_profile_cache_hash_mismatch_is_not_accepted(self):
        import io
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch('handbook_press.urllib.request.urlopen', return_value=io.BytesIO(b'not an ICC profile')):
                with self.assertRaisesRegex(ValueError, 'SHA256'):
                    acquire_profile(root)
            self.assertFalse(list(root.rglob('*.icc')))

    @unittest.skipUnless(os.environ.get('PRESS_RENDER_TESTS') == '1' and shutil.which('gs'), 'Нужны PRESS_RENDER_TESTS=1 и Ghostscript')
    def test_real_colour_export_is_isolated_and_checksummed(self):
        from repo_paths import REPO_ROOT
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'handbooks').mkdir()
            (root / 'handbooks/content.md').write_text('Frozen synthetic material')
            self.fixture(root)
            frozen = teaching_hashes(root)
            profile = acquire_profile(REPO_ROOT)
            with patch('handbook_press.acquire_profile', return_value=profile):
                export_press(root, root / 'source.pdf', root / 'press/master.pdf', frozen)
            report = json.loads((root / 'press/preflight.json').read_text())
            self.assertTrue(report['passed'], report['errors'])
            self.assertEqual(report['pages'], 2)
            self.assertTrue(report['text_preserved'])
            self.assertEqual(teaching_hashes(root), frozen)
            for line in (root / 'press/SHA256SUMS').read_text().splitlines():
                checksum, name = line.split('  ')
                self.assertEqual(hashlib.sha256((root / 'press' / name).read_bytes()).hexdigest(), checksum)
