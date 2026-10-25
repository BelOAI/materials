"""Проверка целостности и безопасного восстановления кэша."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_cache import Cache, fingerprint
from notebook_export import export_notebook


class BuildCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, BUILD_CACHE_DIR=str(self.root / 'cache'))
        env.start()
        self.addCleanup(env.stop)

    def test_partial_corrupt_and_unsafe_entries_miss(self):
        output = self.root / 'output'
        output.mkdir()
        file = output / 'a.txt'
        file.write_text('good')
        cache = Cache('test', 'key')
        cache.save(output, [file])
        file.unlink()
        self.assertTrue(cache.restore(output))
        (cache.path / 'files/a.txt').write_text('bad')
        file.unlink()
        self.assertFalse(cache.restore(output))
        self.assertFalse(file.exists())
        (cache.path / 'manifest.json').write_text(json.dumps({'../outside': 'bad'}))
        self.assertFalse(cache.restore(output))
        (cache.path / 'manifest.json').unlink()
        self.assertFalse(cache.restore(output))

    def test_content_not_mtime_and_environment(self):
        source = self.root / 'source'
        source.write_text('a')
        first = fingerprint([source])
        os.utime(source, (1, 1))
        self.assertEqual(first, fingerprint([source]))
        source.write_text('b')
        self.assertNotEqual(first, fingerprint([source]))
        with patch.dict(os.environ, BUILD_ENV_ID='other'):
            self.assertNotEqual(first, fingerprint([source]))

    def test_notebook_cache_and_export_failure(self):
        notebook = self.root / 'task.ipynb'
        notebook.write_text('{}')
        html = notebook.with_suffix('.html')
        def convert(*args, **kwargs):
            html.write_text('<html>export</html>')
            return type('Result', (), {'returncode': 0})()
        with patch('notebook_export.shutil.which', return_value=sys.executable), patch('notebook_export.subprocess.run', side_effect=convert) as run:
            self.assertTrue(export_notebook(notebook))
            html.unlink()
            self.assertTrue(export_notebook(notebook))
            self.assertEqual(run.call_count, 1)
            metadata = self.root / 'meta.yaml'
            metadata.write_text('status: draft')
            self.assertTrue(export_notebook(notebook, dependencies=[metadata]))
            self.assertTrue(export_notebook(notebook, dependencies=[metadata]))
            self.assertEqual(run.call_count, 2)
            metadata.write_text('status: reviewed')
            self.assertTrue(export_notebook(notebook, dependencies=[metadata]))
            self.assertEqual(run.call_count, 3)
            notebook.write_text('{"changed": true}')
            run.side_effect = None
            run.return_value.returncode = 1
            self.assertFalse(export_notebook(notebook))
            self.assertFalse(html.exists())
        with patch('notebook_export.shutil.which', return_value=None):
            self.assertFalse(export_notebook(notebook))
