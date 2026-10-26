"""Авторство проверяется на фикстурах, без чтения учебных материалов."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from authorship import normalize_authors, normalize_contributors, authors_text, authors_html, authors_markdown, expand_authors, expand_contributors
from course_site import publish_pages
from handbook_notebooks import render_notebook, notebook_authors
from meta_parser import parse_meta
from repo_paths import REPO_ROOT


class AuthorshipTests(unittest.TestCase):
    def test_authors_marker_uses_shared_format_and_preserves_position(self):
        source = '## Heading\n\n<!-- handbook-authors -->\n\nOriginal text.'
        authors = ['Writer <one>', {'name': 'Editor & two', 'role': 'revision'}]
        self.assertEqual(expand_authors(source, authors),
                         source.replace('<!-- handbook-authors -->', authors_markdown(authors)))
        self.assertEqual(expand_authors(source, authors, html=True),
                         source.replace('<!-- handbook-authors -->', authors_html(authors)))
        self.assertEqual(expand_authors('Original text.', None), 'Original text.')
        with self.assertRaises(ValueError):
            expand_authors(source, [])

    def test_contributors_are_included_without_a_duplicate_heading(self):
        text = '## Preface\n\n<!-- handbook-contributors -->\n\nNext paragraph.'
        people = [{'name': 'Writer', 'github': 'writer'}, {'name': 'Editor <two>'}]
        rendered = expand_contributors(text, people)
        self.assertIn('[Writer (@writer)](https://github.com/writer)', rendered)
        self.assertIn(r'Editor \<two\>', rendered)
        self.assertNotIn('<!-- handbook-contributors -->', rendered)
        self.assertEqual(expand_contributors('Unchanged text', people), 'Unchanged text')
        with self.assertRaises(ValueError):
            normalize_contributors([{'name': 'Writer', 'github': '../unsafe'}])
        with self.assertRaises(ValueError):
            expand_contributors(text, [])

    def test_strings_objects_roles_and_escaping(self):
        self.assertEqual(normalize_authors([' Writer ']), [{'name': 'Writer'}])
        people = ['Writer <one>', {'name': 'Editor & two', 'role': 'revision <script>'}]
        html = authors_html(people)
        self.assertIn('Writer &lt;one&gt;', html)
        self.assertIn('Авторы: Writer &lt;one&gt;, Editor &amp; two (revision &lt;script&gt;)', html)
        self.assertNotIn('<script>', html)
        self.assertIn(r'Writer \<one\>', authors_markdown(people))
        self.assertEqual(authors_html([]), '')
        for value in ['name', [None], [''], [{'name': ''}], [{'name': 'X', 'role': 1}]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_authors(value)

    def test_author_labels_depend_on_count_and_preserve_roles(self):
        self.assertEqual(authors_text(['Writer']), 'Автор: Writer')
        self.assertEqual(authors_text(['Writer', 'Editor']), 'Авторы: Writer, Editor')
        self.assertEqual(authors_text([{'name': 'Writer', 'role': 'original'}]), 'Автор: Writer (original)')
        self.assertEqual(authors_text([{'name': 'Writer', 'role': 'original'}, 'Editor']),
                         'Авторы: Writer (original), Editor')

    def test_course_parser_accepts_string_and_object_entries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'meta.yaml'
            path.write_text('authors:\n  - Writer\n  - name: Editor\n    role: revision\n')
            self.assertEqual(normalize_authors(parse_meta(path)['authors']),
                             [{'name': 'Writer'}, {'name': 'Editor', 'role': 'revision'}])

    def test_notebook_credits_use_metadata_and_preserve_code(self):
        text = '```python\nvalue = 42\n```\n'
        original = render_notebook('Fixture', text)
        authored = render_notebook('Fixture', text, authors=[{'name': 'Writer <one>', 'role': 'revision'}])
        self.assertEqual([c for c in original['cells'] if c['cell_type'] == 'code'],
                         [c for c in authored['cells'] if c['cell_type'] == 'code'])
        self.assertEqual(authored['metadata']['authors'], [{'name': 'Writer <one>', 'role': 'revision'}])
        self.assertNotIn('Writer', ''.join(authored['cells'][0]['source']))
        published = notebook_authors(authored, authored['metadata']['authors'], include_credit=True)
        self.assertIn(r'Автор: Writer \<one\> \(revision\)', ''.join(published['cells'][0]['source']))
        self.assertEqual(published['cells'][1:], authored['cells'][1:])
        self.assertEqual(notebook_authors(published, authored['metadata']['authors']), authored)

    def test_notebook_author_migration_preserves_license_code_and_outputs(self):
        notebook = dict(metadata={}, cells=[dict(cell_type='markdown', metadata={},
            source=['# Fixture\n', '\n', 'Автор: Old Writer. CC BY 4.0.\n', '\n', 'Task.']),
            dict(cell_type='code', metadata={}, source=['value = 42\n'], outputs=[{'text': '42'}], execution_count=1)])
        clean = notebook_authors(notebook, ['New Writer'])
        self.assertNotIn('Old Writer', ''.join(clean['cells'][0]['source']))
        self.assertIn('CC BY 4.0.', ''.join(clean['cells'][0]['source']))
        self.assertEqual(clean['cells'][1], notebook['cells'][1])
        self.assertEqual(clean['metadata']['authors'], [{'name': 'New Writer'}])
        self.assertEqual(notebook_authors(clean, ['New Writer']), clean)
        self.assertIn('Old Writer', ''.join(notebook['cells'][0]['source']))

    def test_author_only_updates_preserve_unrelated_spacing(self):
        notebook = dict(metadata={}, cells=[dict(cell_type='markdown', metadata={},
            source='# Fixture\n\nАвтор: Old Writer\n\nFirst paragraph.\n\n\n\nSecond paragraph.')])
        clean = notebook_authors(notebook, ['New Writer'])
        self.assertEqual(clean['cells'][0]['source'], '# Fixture\n\nFirst paragraph.\n\n\n\nSecond paragraph.')
        self.assertEqual(notebook_authors(clean, ['New Writer']), clean)
        notebook['cells'][0]['source'] = '# Title only'
        published = notebook_authors(notebook, ['New Writer'], include_credit=True)
        self.assertTrue(published['cells'][0]['source'].startswith('# Title only\n\nАвтор: New Writer'))

    def test_course_credits_persist_in_static_html_without_manifest_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'utils/site'
            source.mkdir(parents=True)
            shutil.copy(REPO_ROOT / 'utils/site/index.html', source / 'index.html')
            meta = root / 'course/01-fixture/lecture/material.yml'
            meta.parent.mkdir(parents=True)
            meta.write_text('authors:\n  - name: Writer <one>\n    role: original\n  - name: Editor\n    role: revision\n')
            item = dict(id='01-fixture/lecture', kind='lecture', title='Fixture', number='1',
                        date='', time='', description='', subtitle='', materials=[], references=[], pdf='fixture.pdf')
            week = dict(slug='fixture', number=1, title='Fixture', description='', materials=[item['id']])
            manifest = dict(version=2, course=dict(title='Fixture', description='', weeks=[week]), materials=[item])
            original = json.dumps(manifest)
            output = root / '_site'
            publish_pages(root, output, manifest)
            self.assertEqual(json.dumps(manifest), original)
            for path in ('weeks/fixture/index.html', 'materials/index.html'):
                html = (output / path).read_text()
                self.assertIn('Авторы: Writer &lt;one&gt; (original), Editor (revision)', html)
                self.assertNotIn('Writer <one>', html)
