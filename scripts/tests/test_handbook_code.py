"""Граничные случаи функций из реальных примеров учебника."""
import ast
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def example_functions(identifier, notebook=False, **namespace):
    folder = ROOT / 'handbook' / identifier
    if notebook:
        document = json.loads((folder / 'notebook.ipynb').read_text())
        blocks = [''.join(c['source']) for c in document['cells'] if c['cell_type'] == 'code']
    else:
        blocks = re.findall(r'^```python\n(.*?)^```', (folder / 'index.md').read_text(), re.M | re.S)
    definitions = [node for block in blocks for node in ast.parse(block).body
                   if isinstance(node, ast.FunctionDef)]
    module = ast.Module(body=definitions, type_ignores=[])
    exec(compile(module, str(folder), 'exec'), namespace)
    return namespace


class HandbookCodeTests(unittest.TestCase):
    def test_first_experiment_mae_and_invalid_inputs(self):
        for notebook in (False, True):
            mae = example_functions('ml/classic-ml/first-experiment', notebook)['mae']
            self.assertEqual(mae([21, 25, 35], [24, 24, 24]), 5)
            self.assertEqual(mae([10, 20], [15, 15]), 5)
            self.assertEqual(mae([1, 2], [1, 2]), 0)
            for answers, predictions in [([], []), ([1, 2], [1]), ([1], [1, 2])]:
                with self.subTest(notebook=notebook, answers=answers), self.assertRaises(ValueError):
                    mae(answers, predictions)


if __name__ == "__main__":
    unittest.main()
