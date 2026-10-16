"""Граничные случаи функций из реальных примеров учебника."""
import ast
import json
import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

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
    def test_knn_domain_ties_and_scaling(self):
        for identifier, notebook in [
            ('ml/nearest-neighbors/distance-voting', False),
            ('ml/nearest-neighbors/selection-evaluation', False),
            ('ml/knn', True),
        ]:
            with self.subTest(lesson=identifier):
                functions = example_functions(identifier, notebook, sqrt=math.sqrt)
                predict = functions['predict']
                rows = [{'id': 'b', 'x': [1., 0.], 'y': 'B'},
                        {'id': 'a', 'x': [-1., 0.], 'y': 'A'}]
                self.assertEqual(predict([0., 0.], rows, 1), 'A')
                self.assertEqual(predict([0., 0.], rows, 2), 'A')
                for k in [0, -1, 3, 1.5, True, '1']:
                    with self.subTest(k=k), self.assertRaises(ValueError):
                        predict([0., 0.], rows, k)
                for query, data in [([], rows), ([0.], rows), ([0., 0.], [])]:
                    with self.assertRaises(ValueError):
                        predict(query, data, 1)
                if 'fit_scale' in functions:
                    vectors = [[10., 7.], [20., 7.]]
                    data = vectors if notebook else [{'x': point} for point in vectors]
                    scale = functions['fit_scale'](data)
                    self.assertEqual(functions['transform']([15., 9.], scale), [0.5, 2.])
                    with self.assertRaises(ValueError):
                        functions['fit_scale']([])
                    with self.assertRaises(ValueError):
                        functions['transform']([15.], scale)

    def test_iou_geometry_and_invalid_rectangles(self):
        iou = example_functions('ml/neural-networks/detection-segmentation', math=math)['box_iou']
        a, b = [0, 0, 2, 2], [1, 0, 3, 2]
        self.assertAlmostEqual(iou(a, b), 1 / 3)
        self.assertEqual(iou(a, b), iou(b, a))
        self.assertEqual(iou(a, a), 1)
        self.assertEqual(iou(a, [2, 0, 4, 2]), 0)
        self.assertEqual(iou(a, [1, 1, 1, 1]), 0)
        for bad in [[0, 0], [2, 0, 0, 2], [0, 2, 2, 0],
                    [0, 0, math.inf, 2], [0, 0, math.nan, 2]]:
            with self.subTest(box=bad), self.assertRaises(ValueError):
                iou(a, bad)
        with self.assertRaises(ValueError):
            iou([0, 0, 0, 0], [1, 1, 1, 1])

    def test_sampling_uses_the_selected_prefix(self):
        class Generator:
            def __init__(self):
                self.answers = iter(['кот', 'спит', 'пёс', 'играет'])
                self.probabilities = []

            def choice(self, options, p):
                self.probabilities.append(list(p))
                answer = next(self.answers)
                self.assert_option(answer, options)
                return answer

            @staticmethod
            def assert_option(answer, options):
                if answer not in options:
                    raise AssertionError('Ответ не входит в предложенное распределение')

        generator = Generator()
        numpy = SimpleNamespace(random=SimpleNamespace(default_rng=lambda seed: generator))
        sample = example_functions('ml/language-models/generative-models', np=numpy,
                                   first={'кот': 0.6, 'пёс': 0.4},
                                   sleep={'кот': 0.5, 'пёс': 0.9})['sample']
        self.assertEqual(sample(17, count=2), ['кот спит', 'пёс играет'])
        self.assertEqual(generator.probabilities[1], [0.5, 0.5])
        self.assertAlmostEqual(generator.probabilities[3][0], 0.9)
        self.assertAlmostEqual(generator.probabilities[3][1], 0.1)


if __name__ == '__main__':
    unittest.main()
