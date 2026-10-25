"""Последовательное/параллельное выполнение и ошибки изолированных ядер."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from notebook_checks import check_notebooks, execute_notebook


class NotebookChecksTests(unittest.TestCase):
    def test_parallel_and_sequential_check_same_paths_and_report_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = root / 'gliders.csv'
            data.write_text('a\n1\n')
            paths = []
            for name, code in [('good', 'from pathlib import Path\nassert Path("gliders.csv").is_file()'),
                               ('bad', 'raise ValueError("expected failure")')]:
                path = root / f'{name}.ipynb'
                path.write_text(json.dumps({'nbformat': 4, 'nbformat_minor': 5, 'metadata': {},
                    'cells': [{'id': name, 'cell_type': 'code', 'metadata': {}, 'source': code,
                               'execution_count': None, 'outputs': []}]}))
                paths.append(path)
            results = []
            for workers in ('1', '2'):
                with patch.dict(os.environ, NOTEBOOK_TEST_WORKERS=workers):
                    results.append(dict(check_notebooks(paths, data)))
            self.assertEqual(set(results[0]), set(results[1]))
            for result in results:
                self.assertIsNone(result[str(paths[0])])
                self.assertIn('expected failure', result[str(paths[1])])
            # Короткий timeout для проверки обработки зависшего ядра.
            document = json.loads(paths[0].read_text())
            document['cells'][0]['source'] = 'import time\ntime.sleep(30)'
            paths[0].write_text(json.dumps(document))
            path, error = execute_notebook((paths[0], data, 1))
            self.assertEqual(path, str(paths[0]))
            self.assertIn('timed out', error.lower())
            # Исходники не содержат результатов выполнения.
            self.assertEqual(json.loads(paths[0].read_text())['cells'][0]['outputs'], [])
