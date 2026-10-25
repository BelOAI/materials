"""Выбор сборок, объединение версий и защита опубликованного сайта."""
from contextlib import chdir
import importlib.util
import io
import json
import os
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('assemble_pages', Path(__file__).parents[1] / 'assemble-pages.py')
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


def archive(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as output:
        for name, text in files.items():
            output.writestr(name, text)
    return buffer.getvalue()


class PagesDeployTests(unittest.TestCase):
    def setUp(self):
        preview = patch.object(pages, 'preview_artifacts', return_value={})
        preview.start()
        self.addCleanup(preview.stop)

    def test_latest_success_ignores_pr_and_expired_artifact_fails(self):
        def run(event, number):
            return {'event': event, 'head_branch': 'main', 'head_repository': {'full_name': 'org/repo'},
                    'id': number, 'head_sha': str(number)}
        runs = [run('pull_request', 3), run('push', 2), run('push', 1)]
        with patch.object(pages, 'pages', side_effect=[iter(runs), iter([{'name': 'site-main-2', 'expired': False}])]):
            selected, _ = pages.latest_artifact('org/repo', 'main')
            self.assertEqual(selected['id'], 2)
        with patch.object(pages, 'pages', side_effect=[iter(runs), iter([{'name': 'site-main-2', 'expired': True}])]):
            with self.assertRaisesRegex(ValueError, 'main'):
                pages.latest_artifact('org/repo', 'main')
        with patch.object(pages, 'pages', return_value=iter([])):
            self.assertIsNone(pages.latest_artifact('org/repo', 'dev'))

    def test_merge_preserves_main_and_marks_only_dev(self):
        html = '<html><head></head><body><a href="materials/">Каталог</a></body></html>'
        site = archive({'index.html': html, 'materials.json': '{}', 'materials/index.html': '<html><head></head><body><a href="../">Домой</a></body></html>'})
        for sha in ('one', 'two'):
            with self.subTest(sha=sha), tempfile.TemporaryDirectory() as folder, chdir(folder):
                selected = lambda repo, branch: ({'head_sha': sha if branch == 'dev' else 'main', 'html_url': 'url'}, {'id': branch})
                with patch.dict(os.environ, GITHUB_REPOSITORY='org/repo'), patch.object(pages, 'latest_artifact', side_effect=selected), patch.object(pages, 'api', return_value=site):
                    pages.main()
                root = Path('_pages')
                self.assertEqual((root / 'index.html').read_text(), html)
                dev = (root / 'dev/index.html').read_text()
                self.assertIn('Тестовая версия dev', dev)
                self.assertIn('noindex, nofollow', dev)
                self.assertIn('href="materials/"', dev)
                self.assertEqual(json.loads((root / 'build-info.json').read_text())['dev']['sha'], sha)

    def test_pr_merge_and_cleanup_use_current_selection(self):
        html = '<html><head></head><body><a href="./">Home</a></body></html>'
        site = archive({'index.html': html, 'materials.json': '{}'})
        pr_site = archive({'index.html': html, 'materials.json': '{}', 'build-source.json':
                           json.dumps({'head_sha': 'head', 'merge_sha': 'merge', 'run_id': 7, 'pr': 7})})
        run = {'id': 7, 'head_sha': 'head', 'head_branch': 'topic', 'html_url': 'https://example.org/run'}
        def download(path, binary=False):
            if '/commits/merge' in path:
                return {'parents': [{'sha': 'base'}, {'sha': 'head'}]}
            return pr_site if '/artifacts/7/' in path else site
        with tempfile.TemporaryDirectory() as folder, chdir(folder), \
                patch.dict(os.environ, GITHUB_REPOSITORY='org/repo'), \
                patch.object(pages, 'latest_artifact', return_value=(run, {'id': 1})), \
                patch.object(pages, 'api', side_effect=download):
            with patch.object(pages, 'preview_artifacts', return_value={'pr-7': (run, {'id': 7})}):
                pages.main()
            root = Path('_pages')
            self.assertIn('Тестовая версия pr-7', (root / 'test/pr-7/index.html').read_text())
            info = json.loads((root / 'build-info.json').read_text())
            self.assertEqual(info['pr-7']['merge_sha'], 'merge')
            self.assertEqual(info['pr-7']['root'], 'test/pr-7/')
            # Closing the PR or deleting its branch removes the complete subtree.
            pages.main()
            self.assertFalse((root / 'test/pr-7').exists())
            self.assertTrue((root / 'dev/index.html').exists())

    def test_reserved_path_preserves_output(self):
        for reserved in ('dev', 'test'):
            with self.subTest(reserved=reserved), tempfile.TemporaryDirectory() as folder, chdir(folder):
                Path('_pages').mkdir()
                Path('_pages/keep').write_text('old')
                site = archive({'index.html': '<head></head><body></body>', 'materials.json': '{}',
                                reserved + '/index.html': 'unexpected'})
                with patch.dict(os.environ, GITHUB_REPOSITORY='org/repo'), \
                        patch.object(pages, 'latest_artifact', return_value=({'head_sha': 'sha', 'html_url': 'url'}, {'id': 1})), \
                        patch.object(pages, 'api', return_value=site), self.assertRaises(ValueError):
                    pages.main()
                self.assertEqual(Path('_pages/keep').read_text(), 'old')

    def test_bad_pr_provenance_preserves_output(self):
        html = '<html><head></head><body></body></html>'
        run = {'id': 7, 'head_sha': 'head', 'html_url': 'url'}
        for head, run_id, parent in [('other', 7, 'head'), ('head', 8, 'head'), ('head', 7, 'other')]:
            with self.subTest(head=head, run_id=run_id, parent=parent), tempfile.TemporaryDirectory() as folder, chdir(folder):
                Path('_pages').mkdir()
                Path('_pages/keep').write_text('old')
                site = archive({'index.html': html, 'materials.json': '{}', 'build-source.json':
                                json.dumps({'head_sha': head, 'merge_sha': 'merge', 'run_id': run_id, 'pr': 7})})
                def api(path, binary=False):
                    return {'parents': [{'sha': parent}]} if '/commits/' in path else site
                with patch.dict(os.environ, GITHUB_REPOSITORY='org/repo'), \
                        patch.object(pages, 'latest_artifact', return_value=(run, {'id': 1})), \
                        patch.object(pages, 'preview_artifacts', return_value={'pr-7': (run, {'id': 7})}), \
                        patch.object(pages, 'api', side_effect=api), self.assertRaises(ValueError):
                    pages.main()
                self.assertEqual(Path('_pages/keep').read_text(), 'old')

    def test_missing_published_dev_stops_without_touching_output(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = Path.cwd()
            os.chdir(folder)
            try:
                Path('_pages').mkdir()
                Path('_pages/keep').write_text('published')
                selected = lambda repo, branch: None if branch == 'dev' else ({}, {})
                with patch.dict(os.environ, GITHUB_REPOSITORY='org/repo'), patch.object(pages, 'latest_artifact', side_effect=selected), patch.object(pages.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"dev": {}}')):
                    with self.assertRaisesRegex(ValueError, 'dev'):
                        pages.main()
                self.assertEqual(Path('_pages/keep').read_text(), 'published')
            finally:
                os.chdir(previous)

    def test_first_production_without_dev_and_unsafe_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            previous = Path.cwd()
            os.chdir(folder)
            try:
                site = archive({'index.html': '<head></head><body></body>', 'materials.json': '{}'})
                selected = lambda repo, branch: None if branch == 'dev' else ({'head_sha': 'main', 'html_url': 'url'}, {'id': 1})
                missing = urllib.error.HTTPError('url', 404, 'missing', None, None)
                with patch.dict(os.environ, GITHUB_REPOSITORY='org/repo'), patch.object(pages, 'latest_artifact', side_effect=selected), patch.object(pages, 'api', return_value=site), patch.object(pages.urllib.request, 'urlopen', side_effect=missing):
                    pages.main()
                self.assertFalse(Path('_pages/dev').exists())
                with self.assertRaises(ValueError):
                    pages.extract(archive({'../escape': 'bad'}), Path('_pages'))
            finally:
                os.chdir(previous)
