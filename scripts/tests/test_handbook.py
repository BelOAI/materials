"""Структура учебника, переходы со старых адресов и выполнение практики."""
import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_site import load_handbook, publish_handbook, validate_links, PageLinks, lesson_routes
from handbook_notebooks import synchronize
from course_site import write_page

ROOT = Path(__file__).resolve().parents[2]
FIRST = 'python/basic-constructs/input-output'
NUMPY = 'python/numerical-data/numpy-arrays'
KNN = 'ml/nearest-neighbors/distance-voting'


class HandbookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'handbook', self.root / 'handbook')
        (self.root / 'site').mkdir()
        for name in ('index.html', 'render-handbook.mjs'):
            shutil.copyfile(ROOT / 'site' / name, self.root / 'site' / name)
        (self.root / 'site/node_modules').symlink_to(ROOT / 'site/node_modules', target_is_directory=True)
        self.output = self.root / '_site'
        (self.output / 'assets/fontawesome').mkdir(parents=True)
        for name in ('site.css', 'materials.js'):
            (self.output / 'assets' / name).touch()
        for name in ('github', 'instagram', 'tiktok', 'telegram', 'creative-commons'):
            (self.output / f'assets/fontawesome/{name}.svg').touch()
        for path in ('index.html', 'materials/index.html', 'license/index.html', 'favicon.svg'):
            dest = self.output / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text('<html><main id="content"></main></html>', encoding='utf-8')
        self.book = json.loads((self.root / 'handbook/handbook.json').read_text())

    def write(self):
        (self.root / 'handbook/handbook.json').write_text(json.dumps(self.book), encoding='utf-8')

    def first(self):
        return self.book['tracks'][0]['chapters'][0]['lessons'][0]

    def test_curriculum_and_hierarchy(self):
        book = load_handbook(ROOT)
        lessons = book['_lessons']
        seen = set()
        for phase in book['curriculum']['phases']:
            self.assertTrue(phase['learning_outcomes'])
            for identifier in phase['lessons']:
                self.assertNotIn(identifier, seen)
                self.assertTrue(set(lessons[identifier]['prerequisites']).issubset(seen), identifier)
                seen.add(identifier)
        self.assertEqual(seen, {i for i, item in lessons.items() if not item.get('optional')})
        self.assertEqual(book['curriculum']['phases'][0]['lessons'], book['reading_order'])
        for track in book['tracks']:
            for chapter in track['chapters']:
                self.assertEqual(len(chapter['id'].split('/')), 2)
                self.assertNotIn('status', chapter)
                for lesson in chapter['lessons']:
                    self.assertTrue(lesson['id'].startswith(chapter['id'] + '/'))
                    self.assertEqual(len(lesson['id'].split('/')), 3)

    def test_bad_metadata_dependencies_and_paths(self):
        original = copy.deepcopy(self.book)
        changes = [
            lambda: self.first().update(status='unknown'),
            lambda: self.first().update(id='math/basic-constructs/input-output'),
            lambda: self.book['tracks'][0]['chapters'][0].update(lessons=[]),
            lambda: self.book['tracks'][0]['chapters'][1].update(id=self.book['tracks'][0]['chapters'][0]['id']),
            lambda: self.book['tracks'][0]['chapters'][0]['lessons'][1].update(id=FIRST),
            lambda: self.first().update(prerequisites=['missing']),
            lambda: self.first().update(prerequisites=['python/basic-constructs']),
            lambda: self.first().update(prerequisites=[NUMPY]),
            lambda: self.book['start'].update(prerequisites=[FIRST]),
            lambda: self.book.update(reading_order=list(reversed(self.book['reading_order']))),
            lambda: self.book['start'].update(date='2026-02-30'),
            lambda: self.first().update(build=False),
            lambda: self.first()['resources'][0].update(path='../../../../README.md'),
            lambda: self.book['start'].update(references=[{'label': 'Контест', 'url': 'javascript:alert(1)'}]),
            lambda: self.book['aliases'][0].update(id='../../outside'),
            lambda: self.book['aliases'][0].update(lessons=['missing']),
            lambda: self.book['aliases'][0]['anchors'][0].update(target='missing#anchor'),
        ]
        for change in changes:
            with self.subTest(change=change):
                self.book = copy.deepcopy(original)
                change()
                self.write()
                with self.assertRaises(ValueError):
                    load_handbook(self.root)

    def test_invalid_full_routes_fail_publication(self):
        original = copy.deepcopy(self.book)
        changes = [
            lambda: self.book.update(curriculum=None),
            lambda: self.book['curriculum'].update(phases=[]),
            lambda: self.book['curriculum']['phases'][1].update(slug='first-model'),
            lambda: self.book['curriculum']['phases'][1]['lessons'].reverse(),
            lambda: self.book['curriculum']['phases'][1]['lessons'].pop(),
            lambda: self.book['curriculum']['phases'][1]['lessons'].append(FIRST),
            lambda: self.book['curriculum']['phases'][1]['lessons'].append('math/discrete-math/graphs'),
            lambda: self.book['curriculum']['phases'][1]['lessons'].append('missing'),
            lambda: self.book['curriculum']['phases'][0]['lessons'].pop(),
        ]
        for change in changes:
            with self.subTest(change=change):
                self.book = copy.deepcopy(original)
                change()
                self.write()
                with self.assertRaises(ValueError):
                    load_handbook(self.root)

    @patch('handbook_site.export_notebook', return_value=False)
    def test_pages_navigation_resources_and_legacy_anchors(self, export):
        stale = self.output / 'handbook/removed/index.html'
        stale.parent.mkdir(parents=True)
        stale.touch()
        publish_handbook(self.root, self.output, [{'slug': 'example', 'number': 1, 'title': 'Неделя'}])
        self.assertFalse(stale.exists())
        book = load_handbook(ROOT)
        for item in [*book['_lessons'].values(), *book['_chapters'].values(), *book['aliases']]:
            if item.get('status') == 'planned':
                self.assertFalse((self.output / 'handbook' / item['id'] / 'index.html').exists())
                continue
            path = self.output / 'handbook' / item['id'] / 'index.html'
            self.assertTrue(path.is_file(), item['id'])
            html = path.read_text()
            self.assertIn('<meta name="robots" content="noindex, nofollow" />', html)
            self.assertEqual(html.count('class="draft-badge"'), 1)
            sidebar = html.split('<aside class="sidebar">')[1].split('</aside>')[0]
            self.assertIn('← На основной сайт', sidebar)
            self.assertIn('Оглавление учебника', sidebar)
            self.assertNotIn('week-navigation', sidebar)
            self.assertNotIn('weeks/example', sidebar)
            self.assertNotIn('Все материалы', sidebar)
            for unwanted in ('handbook-notice', 'chapter-status', '<time', 'содержательной и технической проверки'):
                self.assertNotIn(unwanted, html)
            for resource in item.get('resources', []):
                self.assertTrue((path.parent / resource['path']).is_file())
        html = (self.output / 'handbook' / FIRST / 'index.html').read_text()
        self.assertIn('href="../../../../"', html)
        self.assertIn('href="../../../../handbook/"', html)
        self.assertIn('<details class="handbook-chapter" open>', html)
        self.assertIn('href="../../../../handbook/' + FIRST + '/" aria-current="page"', html)
        self.assertIn('aria-label="Путь к уроку"', html)
        self.assertIn('aria-label="Оглавление урока"', html)
        self.assertIn('rel="next"', html)
        knn = (self.output / 'handbook' / KNN / 'index.html').read_text()
        self.assertIn('<math', knn)
        self.assertIn('<details>', knn)
        self.assertIn('language-python', knn)
        self.assertIn('href="notebook.ipynb" download', knn)
        for alias in book['aliases']:
            parsed = PageLinks((self.output / 'handbook' / alias['id'] / 'index.html').read_text())
            self.assertTrue({a['id'] for a in alias['anchors']}.issubset(parsed.ids))
        legacy_html = (self.output / 'handbook/python/first-programs/index.html').read_text()
        self.assertIn('списки-и-циклы', PageLinks(legacy_html).ids)
        self.assertIn('handbook/python/basic-constructs/loops/#список-и-перебор', legacy_html)
        self.assertIn('handbook/python/functions-files/functions-arguments/#как-определить-функцию', legacy_html)
        expected_exports = sum(r['path'].endswith('.ipynb') for item in [*book['_lessons'].values(), *book['aliases']] for r in item.get('resources', []))
        self.assertEqual(export.call_count, expected_exports)
        # Each page offers exactly one continuation in the agreed learning route.
        for route in lesson_routes(book):
            for index, identifier in enumerate(route):
                html = (self.output / 'handbook' / identifier / 'index.html').read_text()
                root = '../' * (len(identifier.split('/')) + 1)
                for offset, rel in [(-1, 'prev'), (1, 'next')]:
                    if 0 <= index + offset < len(route):
                        self.assertEqual(html.count(f'rel="{rel}"'), 1, identifier)
                        self.assertIn(f'href="{root}handbook/{route[index + offset]}/"',
                                      re.search(r'<nav class="week-pagination".*?</nav>', html).group(), identifier)
                    else:
                        self.assertNotIn(f'rel="{rel}"', html, identifier)
                self.assertNotIn('reading-next', html)
        optional_routes = lesson_routes(book)[1:]
        self.assertIn(['ml/additional-topics/time-series', 'ml/additional-topics/forecasting'], optional_routes)
        self.assertIn(['ml/additional-topics/logical-ai', 'ml/additional-topics/logical-inference',
                       'ml/additional-topics/knowledge-ml'], optional_routes)
        self.assertEqual({i for route in lesson_routes(book) for i in route}, set(book['_lessons']))
        validate_links(self.output)

    def test_draft_is_not_advertised_on_main_site(self):
        # The draft exists in the source tree but must not enter public navigation.
        write_page(self.root, self.output, [], '', 'BelOAI', 'Материалы',
                   '<h1>Материалы</h1>', 'home', '')
        html = (self.output / 'index.html').read_text()
        self.assertNotIn('handbook/', html)
        self.assertNotIn('name="robots"', html)

    @patch('handbook_site.export_notebook', return_value=False)
    def test_missing_links_and_alias_anchors_fail(self, export):
        chapter = self.root / 'handbook' / FIRST / 'index.md'
        text = chapter.read_text()
        for href in ('../missing/', '#нет-якоря', '../../../../../outside.txt', '/handbook/start/'):
            with self.subTest(href=href):
                chapter.write_text(text + '\n[Ошибка](' + href + ')\n')
                with self.assertRaises(ValueError):
                    publish_handbook(self.root, self.output, [])
        chapter.write_text(text)
        self.book['aliases'][0]['anchors'][0]['target'] = FIRST + '#несуществующий-якорь'
        self.write()
        with self.assertRaises(ValueError):
            publish_handbook(self.root, self.output, [])

    def test_bad_formula_is_fatal(self):
        path = self.root / 'handbook/math/linear-algebra/vectors-distances/index.md'
        path.write_text(path.read_text() + '\n$$\\unknowncommand{x}$$\n')
        with self.assertRaises(subprocess.CalledProcessError):
            publish_handbook(self.root, self.output, [])

    def test_ready_lessons_have_examples_and_six_solvable_tasks(self):
        book = load_handbook(ROOT)
        for item in book['_lessons'].values():
            if item['id'] == 'start' or item['status'] == 'planned':
                continue
            text = (ROOT / 'handbook' / item['id'] / 'index.md').read_text()
            self.assertTrue(text.startswith('## Чему научимся'))
            self.assertIn('Разобранный пример', text, item['id'])
            for level in ('Базовая', 'Прикладная', 'Олимпиадная'):
                self.assertEqual(len(re.findall(r'^### [1-6]\. ' + level + r'$', text, re.M)), 2, item['id'])
            self.assertEqual(text.count('<summary>Подсказка</summary>'), 6)
            self.assertEqual(text.count('<summary>Решение</summary>'), 6)
            if item['id'].startswith(('python/', 'ml/')):
                self.assertTrue((ROOT / 'handbook' / item['id'] / 'notebook.ipynb').is_file())

    def test_programme_resources_and_optional_routes(self):
        book = load_handbook(ROOT)
        programme = (ROOT / 'handbook/PROGRAM.md').read_text()
        for track in book['tracks']:
            for chapter in track['chapters']:
                self.assertIn(chapter['title'], programme)
                for lesson in chapter['lessons']:
                    with self.subTest(lesson=lesson['id']):
                        self.assertIn(lesson['title'], programme)
                        row = next(line for line in programme.splitlines()
                                   if line.startswith('| ' + lesson['title'] + ' |')
                                   or line.startswith('| ' + lesson['title'] + ' (дополнительно) |'))
                        expected = '; '.join(book['_lessons'][i]['title'] for i in lesson['prerequisites'])
                        self.assertEqual(row.split('|')[-2].strip(), expected)
                        if lesson['status'] == 'planned':
                            continue
                        paths = [r['path'] for r in lesson.get('resources', [])]
                        if track['slug'] == 'ml':
                            self.assertIn('notebook.ipynb', paths)
                        if track['slug'] == 'math':
                            self.assertFalse(any(p.endswith('.ipynb') for p in paths))
                        text = (ROOT / 'handbook' / lesson['id'] / 'index.md').read_text()
                        if track['slug'] in ('math', 'ml'):
                            self.assertIn('Типичные ошибки', text)
                            self.assertIn('самопровер', text.lower())
                        if lesson['id'].startswith('ml/additional-topics/'):
                            self.assertTrue(lesson.get('optional'))
        for identifier in book['reading_order']:
            self.assertFalse(identifier.startswith(('math/calculus/', 'math/probability-statistics/')))
        optional = {i for i, lesson in book['_lessons'].items() if lesson.get('optional')}
        for lesson in book['_lessons'].values():
            if not lesson.get('optional'):
                self.assertTrue(optional.isdisjoint(lesson.get('prerequisites', [])), lesson['id'])

    def test_notebooks_match_lesson_texts(self):
        self.assertEqual(synchronize(ROOT), [])

    def test_legacy_notebook_links_sync_without_changing_code(self):
        alias = next(a for a in self.book['aliases']
                     if any(r['path'].endswith('.ipynb') for r in a.get('resources', [])))
        resource = next(r for r in alias['resources'] if r['path'].endswith('.ipynb'))
        path = self.root / 'handbook' / alias['id'] / resource['path']
        document = json.loads(path.read_text())
        code = [c for c in document['cells'] if c['cell_type'] == 'code']
        document['cells'] = [c for c in document['cells'] if c.get('id') != 'lesson-links']
        path.write_text(json.dumps(document))
        self.assertIn(alias['id'], synchronize(self.root))
        synchronize(self.root, write=True)
        self.assertEqual(synchronize(self.root), [])
        repaired = json.loads(path.read_text())
        self.assertEqual([c for c in repaired['cells'] if c['cell_type'] == 'code'], code)
        self.assertEqual(repaired['cells'][1]['id'], 'lesson-links')

    def test_first_experiment_works_without_optional_packages(self):
        runner = '''import json,sys
from pathlib import Path
ns={}
for cell in json.loads(Path(sys.argv[1]).read_text())["cells"]:
 if cell["cell_type"]=="code":exec(compile("".join(cell["source"]),sys.argv[1],"exec"),ns)
'''
        with tempfile.TemporaryDirectory() as folder:
            shutil.copyfile(ROOT / 'handbook/data/gliders.csv', Path(folder) / 'gliders.csv')
            for identifier in [FIRST, 'ml/first-experiment/split-baseline', 'ml/nearest-neighbors/selection-evaluation']:
                path = ROOT / 'handbook' / identifier / 'notebook.ipynb'
                result = subprocess.run([sys.executable, '-I', '-S', '-c', runner, str(path)], cwd=folder, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_notebooks_execute_with_clean_kernel(self):
        import nbformat
        from nbclient import NotebookClient
        from jupyter_client import KernelManager
        book = load_handbook(ROOT)
        items = [*book['_lessons'].values(), *book['aliases']]
        paths = {ROOT / 'handbook' / item['id'] / r['path'] for item in items for r in item.get('resources', []) if r['path'].endswith('.ipynb')}
        for path in sorted(paths):
            with self.subTest(notebook=path), tempfile.TemporaryDirectory() as folder:
                shutil.copyfile(ROOT / 'handbook/data/gliders.csv', Path(folder) / 'gliders.csv')
                document = nbformat.read(path, as_version=4)
                nbformat.validate(document)
                manager = KernelManager(kernel_name='python3')
                manager.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
                client = NotebookClient(document, km=manager, timeout=120, resources={'metadata': {'path': folder}})
                try:
                    client.execute(cleanup_kc=True)
                finally:
                    if manager.has_kernel:
                        manager.shutdown_kernel(now=True)
                self.assertFalse(any(o.output_type == 'error' for c in document.cells if c.cell_type == 'code' for o in c.outputs))


if __name__ == '__main__':
    unittest.main()
