"""Старые адреса сохраняют доступ к текущим страницам и файлам учебников."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_redirects import publish_legacy_handbook


class HandbookRedirectTests(unittest.TestCase):
    def test_redirects_resources_and_stale_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'handbooks/ml/example'
            source.mkdir(parents=True)
            html = '<html><head></head><body><h2 id="anchor">Тема</h2></body></html>'
            (source / 'index.html').write_text(html)
            (source / 'Тема #1.html').write_text(html)
            (source / 'notebook.ipynb').write_bytes(b'notebook')
            (root / 'handbooks/data').mkdir()
            (root / 'handbooks/data/data.csv').write_bytes(b'x\n1\n')
            stale = root / 'handbook/ml/knn'
            stale.mkdir(parents=True)
            (stale / 'index.html').write_text('obsolete')
            publish_legacy_handbook(root)
            self.assertFalse(stale.exists())
            redirect = (root / 'handbook/ml/example/index.html').read_text()
            self.assertIn('noindex, nofollow', redirect)
            self.assertIn('../../../handbooks/ml/example/', redirect)
            self.assertIn('target.search=location.search;target.hash=location.hash', redirect)
            self.assertIn('http-equiv="refresh"', redirect)
            self.assertEqual((source / 'index.html').read_text(), html)
            preview = (root / 'handbook/ml/example/Тема #1.html').read_text()
            self.assertIn('%20%231.html', preview)
            self.assertEqual((root / 'handbook/ml/example/notebook.ipynb').read_bytes(), b'notebook')
            self.assertEqual((root / 'handbook/data/data.csv').read_bytes(), b'x\n1\n')
            # Удаление источника удаляет и его совместимую копию.
            (source / 'notebook.ipynb').unlink()
            publish_legacy_handbook(root)
            self.assertFalse((root / 'handbook/ml/example/notebook.ipynb').exists())

    def test_absent_handbooks_clear_legacy_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'handbook').mkdir()
            (root / 'handbook/stale.html').touch()
            publish_legacy_handbook(root)
            self.assertFalse((root / 'handbook').exists())
