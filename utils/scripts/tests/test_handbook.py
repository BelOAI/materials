"""Локальный каталог ML, ресурсы, переходы и выполнение ноутбуков."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from html import escape
from pathlib import Path
from unittest.mock import patch

import yaml
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_site import load_handbook, publish_handbook, validate_links
from handbook_notebooks import synchronize, synchronize_authors, render_notebook
from notebook_checks import check_notebooks
from repo_paths import REPO_ROOT as ROOT

OLD = {'start': 'intro', 'environment': 'intro', 'diy-nn': 'nn-in-practice', 'how-they-learn': 'how-nns-learn', 'advanced-math': 'math-of-ai'}


class HandbookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        base = self.root / 'handbooks'
        base.mkdir()
        (base / 'README.md').write_text('# Fixture catalogue\n\n[Book](ml/README.md)\n')
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
        (base / 'ml/meta.yml').write_text(yaml.safe_dump(dict(chapters=folders)))
        (base / 'handbooks.yml').write_text(yaml.safe_dump(dict(title='Fixture', description='Fixture.',
            handbooks=[dict(slug='ml', title='ML', description='Fixture.')])))
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
    def test_landing_content_and_links_follow_source(self, export):
        source = self.root / 'handbooks/README.md'
        for marker in ('catalogue-one', 'catalogue-two'):
            source.write_text(f'# {marker}\n\n[Book](ml/README.md)\n\n[Plan](ml/CURRICULUM.md)\n')
            publish_handbook(self.root, self.output, [])
            html = (self.output / 'handbooks/index.html').read_text()
            self.assertIn(marker, html)
            self.assertIn('href="ml/"', html)
            self.assertIn('href="ml/curriculum/"', html)
            self.assertNotIn('href="ml/README.md"', html)
            validate_links(self.output)

    @patch('handbook_site.export_notebook', return_value=False)
    def test_navigation_scopes_books_chapters_and_lessons(self, export):
        self.paragraph()
        base = self.root / 'handbooks'
        shutil.copytree(base / 'ml', base / 'guide')
        path = base / 'handbooks.yml'
        catalog = yaml.safe_load(path.read_text())
        catalog['handbooks'].append(catalog['handbooks'][0] | dict(slug='guide', title='Second fixture'))
        catalog['handbooks'].append(dict(slug='disabled', title='Disabled fixture', description='Fixture.', build=False))
        (base / 'disabled').mkdir()
        (base / 'disabled/README.md').write_text('Автор: Excluded draft writer\n')
        path.write_text(yaml.safe_dump(catalog))
        publish_handbook(self.root, self.output, [])
        landing = (self.output / 'handbooks/index.html').read_text()
        navigation = landing.split('<course-navigation>', 1)[1].split('</course-navigation>', 1)[0]
        self.assertIn('href="../handbooks/ml/"', navigation)
        self.assertIn('href="../handbooks/guide/"', navigation)
        self.assertNotIn('curriculum/', navigation)
        self.assertNotIn('Disabled fixture', navigation)
        self.assertNotIn('handbook-chapters', navigation)
        self.assertIn('data-page="handbooks"', landing)
        for slug, other in [('ml', 'Second fixture'), ('guide', '>ML<')]:
            lesson = (self.output / f'handbooks/{slug}/classic-ml/example/index.html').read_text()
            navigation = lesson.split('<course-navigation>', 1)[1].split('</course-navigation>', 1)[0]
            self.assertIn('← Все учебники', navigation)
            self.assertIn(f'handbooks/{slug}/curriculum/', navigation)
            self.assertIn(f'handbooks/{slug}/classic-ml/"', navigation)
            self.assertIn(f'handbooks/{slug}/classic-ml/example/" aria-current="page"', navigation)
            self.assertNotIn(other, navigation)
            self.assertEqual(navigation.count('aria-current="page"'), 1)
            self.assertIn('class="breadcrumbs"', lesson)
        validate_links(self.output)
        # Каталог работает и без учебника с историческим slug ml.
        catalog['handbooks'] = [catalog['handbooks'][1]]
        path.write_text(yaml.safe_dump(catalog))
        (base / 'README.md').write_text('# Catalogue\n\n[Guide](guide/README.md)\n')
        publish_handbook(self.root, self.output, [])
        self.assertFalse((self.output / 'handbooks/ml').exists())
        self.assertFalse((self.output / 'handbooks/start').exists())
        validate_links(self.output)

    @patch('handbook_site.export_notebook', return_value=False)
    def test_chapter_text_and_contents_have_separate_roles(self, export):
        self.paragraph()
        self.metadata(self.root / 'handbooks/ml/00-intro', description='Unique summary marker.')
        self.metadata(self.chapter, description='Chapter summary marker.')
        publish_handbook(self.root, self.output, [])
        intro = (self.output / 'handbooks/ml/intro/index.html').read_text()
        self.assertIn('name="description" content="Unique summary marker."', intro)
        self.assertNotIn('Unique summary marker.', intro.split('<main', 1)[1])
        chapter = (self.output / 'handbooks/ml/classic-ml/index.html').read_text()
        self.assertIn('<h2>Содержание</h2><ol><li><a href="example/"', chapter)
        self.assertIn('name="description" content="Chapter summary marker."', chapter)
        self.assertNotIn('Chapter summary marker.', chapter.split('<body', 1)[1])
        overview = (self.output / 'handbooks/ml/index.html').read_text()
        self.assertIn('name="description" content="Fixture."', overview)
        self.assertNotIn('Fixture.', overview.split('<body', 1)[1])
        lesson = (self.output / 'handbooks/ml/classic-ml/example/index.html').read_text()
        self.assertIn('name="description" content="Проверка ресурсов."', lesson)
        self.assertNotIn('Проверка ресурсов.', lesson.split('<body', 1)[1])

    @patch('handbook_site.export_notebook', return_value=False)
    def test_book_contents_follow_catalog_without_changing_preface(self, export):
        self.paragraph()
        future = self.chapter / '02-future'
        future.mkdir()
        (future / 'README.md').write_text('# Future fixture\n')
        (future / 'meta.yaml').write_text('slug: future\ntitle: Future fixture\ndescription: Fixture.\nstatus: planned\n')
        self.metadata(self.chapter, paragraphs=['02-future', '01-example'])
        source = self.root / 'handbooks/ml/content.md'
        preface = '## Preface fixture\n\nOriginal wording & punctuation.\n'
        source.write_text(preface)
        publish_handbook(self.root, self.output, [])
        html = (self.output / 'handbooks/ml/index.html').read_text()
        toc = html.split('<nav class="handbook-toc"', 1)[1].split('</nav>', 1)[0]
        self.assertIn('<h2>Содержание</h2>', toc)
        self.assertIn('href="classic-ml/"', toc)
        self.assertIn('href="classic-ml/example/"', toc)
        self.assertNotIn('href="classic-ml/future/"', toc)
        self.assertLess(toc.index('Future fixture'), toc.index('href="classic-ml/example/"'))
        self.assertIn('(готовится)', toc)
        self.assertIn('class="section-planned"', toc)
        self.assertLess(html.index('class="handbook-toc"'), html.index('id="preface-fixture"'))
        self.assertIn('Original wording &amp; punctuation.', html)
        self.assertEqual(source.read_text(), preface)
        validate_links(self.output)

    @patch('handbook_site.export_notebook', return_value=False)
    def test_preface_and_curriculum_authors_come_from_local_metadata(self, export):
        folder = self.root / 'handbooks/ml'
        preface = '## Greeting fixture\n\n<!-- handbook-authors -->\n\nOriginal greeting.'
        programme = '# Plan fixture\n\n<!-- handbook-authors -->\n\nOriginal programme.'
        (folder / 'content.md').write_text(preface)
        (folder / 'CURRICULUM.md').write_text(programme)
        metadata = yaml.safe_load((folder / 'meta.yml').read_text())
        for name in ['Writer <one>', 'Writer & two']:
            (folder / 'meta.yml').write_text(yaml.safe_dump(metadata | dict(
                preface=dict(authors=[name]), curriculum=dict(authors=['Planner', 'Reviewer']))))
            publish_handbook(self.root, self.output, [])
            html = (self.output / 'handbooks/ml/index.html').read_text()
            self.assertIn('<h2 id="greeting-fixture">Greeting fixture</h2>\n' +
                          '<p class="authors">Автор: ' + escape(name) + '</p>', html)
            self.assertEqual(html.count('Автор: ' + escape(name)), 1)
            plan = (self.output / 'handbooks/ml/curriculum/index.html').read_text()
            self.assertIn('<p class="authors">Авторы: Planner, Reviewer</p>', plan)
            self.assertNotIn('handbook-authors', html + plan)
            self.assertIn('Original greeting.', html)
            self.assertIn('Original programme.', plan)
            self.assertEqual((folder / 'content.md').read_text(), preface)
            self.assertEqual((folder / 'CURRICULUM.md').read_text(), programme)
            validate_links(self.output)
        for invalid in ['preface: [Writer]', 'preface: {authors: []}', 'curriculum: {authors: nope}',
                        'preface: {authors: [Writer]}\npreface: {authors: [Other]}', 'prefaec: {}']:
            (folder / 'meta.yml').write_text(yaml.safe_dump(metadata) + invalid)
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                load_handbook(self.root)

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

    def test_yaml_catalog_and_local_book_metadata_validation(self):
        catalog_path = self.root / 'handbooks/handbooks.yml'
        original_catalog = catalog_path.read_text()
        metadata_path = self.root / 'handbooks/ml/meta.yml'
        original_metadata = metadata_path.read_text()
        catalog = yaml.safe_load(original_catalog)
        metadata = yaml.safe_load(original_metadata)
        reordered = metadata['chapters'][:1] + list(reversed(metadata['chapters'][1:]))
        metadata_path.write_text(yaml.safe_dump(metadata | dict(chapters=reordered)))
        loaded = load_handbook(self.root)
        self.assertEqual([s['_folder'].name for s in loaded['handbooks'][0]['sections']], reordered)
        for invalid in ['title: [', original_catalog + '\ntitle: Duplicate', 'handbooks: []',
                        yaml.safe_dump(catalog | dict(handbooks='ml')),
                        yaml.safe_dump(catalog | dict(handbooks=[catalog['handbooks'][0] | dict(chapters=[])]))]:
            catalog_path.write_text(invalid)
            with self.subTest(catalog=invalid), self.assertRaises(ValueError):
                load_handbook(self.root)
        catalog_path.write_text(original_catalog)
        for invalid in ['chapters: [', 'chapters: []\nchapters: []', 'preface: {authors: [Writer]}',
                        'chapters: nope', 'chapters: [../outside]',
                        yaml.safe_dump(dict(chapters=[metadata['chapters'][0]] * 2))]:
            metadata_path.write_text(invalid)
            with self.subTest(metadata=invalid), self.assertRaises(ValueError):
                load_handbook(self.root)
        metadata_path.unlink()
        with self.assertRaises(ValueError):
            load_handbook(self.root)
        metadata_path.write_text(original_metadata)

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

    def test_cross_lesson_resources_rewrite_in_pages_and_notebook_previews(self):
        folder = self.paragraph()
        sibling = self.chapter / '02-other'
        sibling.mkdir()
        (sibling / 'README.md').write_text('# Fixture\n')
        (sibling / 'content.md').write_text('## Fixture\n')
        (sibling / 'meta.yaml').write_text(yaml.safe_dump(dict(
            slug='other', title='Other', description='Fixture.', status='draft',
            build=True, authors=['Fixture Writer'], resources=[
                dict(path='attachments/example.zip', label='Archive'),
            ],
        )))
        self.metadata(self.chapter, paragraphs=[folder.name, sibling.name])
        for name, data in (
            ('data/shared #1.csv', b'x\n1\n'),
            ('media/figure.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
            ('attachments/example.zip', b'fixture archive'),
        ):
            path = sibling / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        intro = self.root / 'handbooks/ml/00-intro/data'
        intro.mkdir()
        (intro / 'example.csv').write_text('x\n2\n')
        links = (
            '<a href="../02-other/data/shared%20%231.csv?download=1&amp;mode=full#sample">Data</a>'
            '<img src="../02-other/media/figure.svg">'
            '<a href="../02-other/attachments/example.zip">Archive</a>'
            '<a href="../../00-intro/data/example.csv">Intro data</a>'
        )
        path = folder / 'content.md'
        path.write_text(path.read_text() + '\n' + links + '\n')

        def export(path, **kwargs):
            path.with_suffix('.html').write_text('<html><head></head><body>' + links + '</body></html>')
            return True

        with patch('handbook_site.export_notebook', side_effect=export):
            publish_handbook(self.root, self.output, [])
        destination = self.output / 'handbooks/ml/classic-ml/example'
        for name in ('index.html', 'notebook.html'):
            html = (destination / name).read_text()
            self.assertIn('href="../other/data/shared%20%231.csv?download=1&amp;mode=full#sample"', html)
            self.assertIn('src="../other/media/figure.svg"', html)
            self.assertIn('href="../other/attachments/example.zip"', html)
            self.assertIn('href="../../intro/data/example.csv"', html)
        self.assertEqual((destination.parent / 'other/data/shared #1.csv').read_bytes(), b'x\n1\n')
        validate_links(self.output)

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

    def test_author_only_sync_updates_notebooks_without_changing_tasks(self):
        folder = self.paragraph()
        original = json.loads((folder / 'notebook.ipynb').read_text())
        self.metadata(folder, authors=['New Writer'])
        expected_path = (folder / 'notebook.ipynb').relative_to(self.root).as_posix()
        self.assertEqual(synchronize_authors(self.root), [expected_path])
        synchronize_authors(self.root, write=True)
        updated = json.loads((folder / 'notebook.ipynb').read_text())
        self.assertEqual(updated['cells'], original['cells'])
        self.assertEqual(updated['metadata']['authors'], [{'name': 'New Writer'}])
        self.assertEqual(synchronize_authors(self.root), [])
        with patch('handbook_site.export_notebook', return_value=False):
            publish_handbook(self.root, self.output, [])
        published = json.loads((self.output / 'handbooks/ml/classic-ml/example/notebook.ipynb').read_text())
        self.assertIn('Автор: New Writer', ''.join(published['cells'][0]['source']))

    def test_manual_authorship_in_markdown_is_rejected(self):
        path = self.root / 'handbooks/ml/content.md'
        for text in ['## Preface\n\nАвтор: Writer', '**Авторы:** Writer, Editor', 'Автор программы: Writer']:
            path.write_text(text)
            with self.subTest(text=text), self.assertRaisesRegex(ValueError, 'перенесите авторство в метаданные'):
                load_handbook(self.root)
        path.write_text('## Preface\n\nАвторы:\n\n```text\nАвтор: Example\n```\n')
        load_handbook(self.root)

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
