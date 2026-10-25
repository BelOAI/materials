"""Локальный каталог ML, ресурсы, переходы и выполнение ноутбуков."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_site import load_handbook, publish_handbook, validate_links
from handbook_notebooks import synchronize, render_notebook
from notebook_checks import check_notebooks
from repo_paths import REPO_ROOT as ROOT

OLD = {'start': 'intro', 'environment': 'intro', 'diy-nn': 'nn-in-practice', 'how-they-learn': 'how-nns-learn', 'advanced-math': 'math-of-ai'}


class HandbookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        base = self.root / 'handbooks'
        folders = []
        # Техническая фикстура независима от содержания реального учебника.
        for index, slug in enumerate(['intro', 'classic-ml', 'dl-basics', 'nn-in-practice', 'how-nns-learn', 'math-of-ai']):
            folder = base / 'ml' / f'{index:02}-{slug}'
            folder.mkdir(parents=True)
            folders.append(folder.name)
            (folder / 'README.md').write_text('# Fixture\n')
            item = dict(slug=slug, title=slug, description='Fixture.', authors=['Fixture author'],
                        status='draft' if index == 0 else 'planned', paragraphs=[])
            if index == 0:
                item['build'] = True
                (folder / 'content.md').write_text('## Fixture\n\n[Guide](content.md)\n')
            (folder / 'meta.yaml').write_text(yaml.safe_dump(item))
        (base / 'ml/content.md').write_text('Welcome fixture.\n\n[Section](00-intro/content.md)\n')
        (base / 'ml/CURRICULUM.md').write_text('## Plan fixture\n\n[Example](01-classic-ml/README.md)\n')
        (base / 'handbooks.json').write_text(json.dumps(dict(title='Fixture', description='Fixture.',
            handbooks=[dict(slug='ml', title='ML', description='Fixture.', chapters=folders)])))
        (self.root / 'utils/site').mkdir(parents=True)
        for name in ('index.html', 'render-handbook.mjs'):
            shutil.copyfile(ROOT / 'utils/site' / name, self.root / 'utils/site' / name)
        (self.root / 'utils/site/node_modules').symlink_to(ROOT / 'utils/site/node_modules', target_is_directory=True)
        self.output = self.root / '_site'
        (self.output / 'assets/fontawesome').mkdir(parents=True)
        for name in ('site.css', 'materials.js'):
            (self.output / 'assets' / name).touch()
        for name in ('github', 'instagram', 'tiktok', 'telegram', 'creative-commons'):
            (self.output / f'assets/fontawesome/{name}.svg').touch()
        for path in ('index.html', 'materials/index.html', 'license/index.html', 'favicon.svg'):
            target = self.output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('<html><main id="content"></main></html>')
        self.chapter = self.root / 'handbooks/ml/01-classic-ml'

    def metadata(self, folder, **updates):
        path = folder / 'meta.yaml'
        item = yaml.safe_load(path.read_text())
        item.update(updates)
        path.write_text(yaml.safe_dump(item, allow_unicode=True, sort_keys=False))

    def paragraph(self):
        folder = self.chapter / '01-example'
        folder.mkdir()
        self.metadata(self.chapter, status='draft', build=True, paragraphs=['01-example'])
        (folder / 'README.md').write_text('# Тестовый параграф\n')
        (folder / 'meta.yaml').write_text('''slug: example
title: Пример
description: Проверка ресурсов.
status: draft
build: true
authors: [Fixture Writer]
sync_notebook: true
resources:
  - path: data/sample.csv
    label: Данные
  - path: notebook.ipynb
    label: Ноутбук
''')
        text = '## Чему научимся\n\n![Рисунок](media/image.svg)\n\n[Данные](data/sample.csv)\n\n```python\nfrom pathlib import Path\nassert Path("data/sample.csv").is_file()\n```\n\n$$x^2$$\n'
        (folder / 'content.md').write_text(text)
        for d in ('data', 'media'):
            (folder / d).mkdir()
        (folder / 'data/sample.csv').write_text('x\n1\n')
        (folder / 'media/image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10"/></svg>')
        (folder / 'notebook.ipynb').write_text(json.dumps(render_notebook('Пример', text, assets=folder, authors=['Fixture Writer'])))
        return folder

    @patch('handbook_site.export_notebook', return_value=False)
    def test_main_content_and_curriculum_follow_sources(self, export):
        source = self.root / 'handbooks/ml/content.md'
        for marker in ('fixture-one', 'fixture-two'):
            source.write_text(marker + '\n\n[Plan](CURRICULUM.md)\n')
            publish_handbook(self.root, self.output, [])
            html = (self.output / 'handbooks/ml/index.html').read_text()
            self.assertIn(marker, html)
            self.assertIn('href="curriculum/"', html)
            self.assertTrue((self.output / 'handbooks/ml/curriculum/index.html').is_file())

    def test_invalid_local_metadata(self):
        path = self.chapter / 'meta.yaml'
        original = path.read_text()
        cases = ['title: [', original + 'slug: duplicate\n']
        item = yaml.safe_load(original)
        for updates in [dict(slug='../escape'), dict(slug='intro'), dict(status='unknown'), dict(status='draft'),
                        dict(authors=['']), dict(paragraphs=None), dict(paragraphs=['../outside']),
                        dict(paragraphs=['01-missing']), dict(paragraphs=['_paragraph-template']),
                        dict(paragraphs=['01-missing', '01-missing']), dict(resources=[{'path':'../../../../LICENSE','label':'Bad'}])]:
            cases.append(yaml.safe_dump(item | updates))
        for content in cases:
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    load_handbook(self.root)
        path.write_text(original)
        (self.chapter / 'content.md').write_text('planned text')
        with self.assertRaises(ValueError):
            load_handbook(self.root)

    def test_paragraph_order_and_duplicate_slugs(self):
        folder = self.paragraph()
        second = self.chapter / '02-second'
        shutil.copytree(folder, second)
        self.metadata(second, slug='second')
        self.metadata(self.chapter, paragraphs=['02-second', '01-example'])
        self.assertEqual(list(load_handbook(self.root)['_lessons']), ['ml/classic-ml/second', 'ml/classic-ml/example'])
        self.metadata(second, slug='example')
        with self.assertRaises(ValueError):
            load_handbook(self.root)
        self.metadata(second, slug='second')
        (folder / 'content.md').unlink()
        with self.assertRaises(ValueError):
            load_handbook(self.root)

    @patch('handbook_site.export_notebook', return_value=False)
    def test_pages_redirects_and_stale_output(self, export):
        for prefix in ('handbooks', 'handbook'):
            for old in ('python/old/notebook.ipynb', 'math/old/index.html', 'ml/knn/index.html', 'ml/_paragraph-template/index.html'):
                stale = self.output / prefix / old
                stale.parent.mkdir(parents=True, exist_ok=True)
                stale.touch()
        publish_handbook(self.root, self.output, [])
        for prefix in ('handbooks', 'handbook'):
            for path in ('python', 'math', 'ml/knn', 'ml/_paragraph-template'):
                self.assertFalse((self.output / prefix / path).exists())
        overview = (self.output / 'handbooks/ml/index.html').read_text()
        book = load_handbook(self.root)
        self.assertEqual(overview.count('class="section-planned"'), sum(c['status'] == 'planned' for c in book['_chapters'].values()))
        for i, chapter in enumerate(load_handbook(self.root)['_chapters'].values()):
            path = self.output / 'handbooks' / chapter['id'] / 'index.html'
            html = path.read_text()
            self.assertIn(f'{i}. {chapter["title"]}', html)
            self.assertIn('noindex, nofollow', html)
            self.assertNotIn('rel="next"', html)
            self.assertNotIn('<ol></ol>', html)
            self.assertEqual(html.count('aria-current="page"'), 1)
            if chapter['status'] == 'planned':
                self.assertIn('class="section-planned"', html)
        for old, new in OLD.items():
            html = (self.output / 'handbooks/ml' / old / 'index.html').read_text()
            self.assertIn('../' + new + '/', html)
            self.assertIn('target.search=location.search;target.hash=location.hash', html)
            self.assertTrue((self.output / 'handbook/ml' / old / 'index.html').is_file())
        self.assertFalse(export.called)
        validate_links(self.output)

    def test_notebook_preview_rewrites_source_routes(self):
        self.paragraph()
        def export(path, **kwargs):
            path.with_suffix('.html').write_text('<html><head></head><body>'
                '<a href="../../00-intro/README.md?mode=read#fixture">Intro</a>'
                '<a href="content.md">Text</a><img src="media/image.svg"></body></html>')
            return True
        with patch('handbook_site.export_notebook', side_effect=export):
            publish_handbook(self.root, self.output, [])
        preview = (self.output / 'handbooks/ml/classic-ml/example/notebook.html').read_text()
        self.assertIn('href="../../intro/?mode=read#fixture"', preview)
        self.assertIn('href="./"', preview)
        self.assertIn('src="media/image.svg"', preview)

    def test_paragraph_resources_export_sync_and_deletion(self):
        folder = self.paragraph()
        publish_handbook(self.root, self.output, [])
        dest = self.output / 'handbooks/ml/classic-ml/example'
        self.assertEqual((dest / 'data/sample.csv').read_bytes(), (folder / 'data/sample.csv').read_bytes())
        html = (dest / 'index.html').read_text()
        self.assertIn('media/image.svg', html)
        self.assertIn('<math', html)
        self.assertIn('Автор: Fixture Writer', html)
        self.assertTrue((dest / 'notebook.html').is_file())
        self.assertIn('noindex, nofollow', (dest / 'notebook.html').read_text())
        self.assertFalse((dest / 'meta.yaml').exists())
        self.assertEqual(synchronize(self.root), [])
        (folder / 'content.md').write_text((folder / 'content.md').read_text() + '\nДополнение.\n')
        self.assertEqual(synchronize(self.root), ['ml/classic-ml/example'])
        synchronize(self.root, write=True)
        self.assertEqual(synchronize(self.root), [])
        for path, error in check_notebooks([folder / 'notebook.ipynb']):
            self.assertIsNone(error, f'{path}: {error}')
        self.metadata(self.chapter, status='planned', paragraphs=[])
        shutil.rmtree(folder)
        publish_handbook(self.root, self.output, [])
        self.assertFalse(dest.exists())
        self.assertFalse((self.output / 'handbook/ml/classic-ml/example').exists())

    def test_missing_links_and_formula_errors_fail(self):
        folder = self.paragraph()
        path = folder / 'content.md'
        original = path.read_text()
        for value in ['[Bad](missing.csv)', '[Bad](#нет-якоря)', '[Bad](/handbooks/ml/)', '$$\\unknowncommand{x}$$']:
            path.write_text(original + '\n' + value + '\n')
            with self.subTest(value=value):
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    publish_handbook(self.root, self.output, [])



if __name__ == '__main__':
    unittest.main()
