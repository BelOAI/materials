"""Авторство проверяется на фикстурах, без чтения учебных материалов."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from authorship import normalize_authors, authors_html, authors_markdown, expand_contributors
from course_site import publish_pages
from handbook_notebooks import render_notebook
from meta_parser import parse_meta
from repo_paths import REPO_ROOT


class AuthorshipTests(unittest.TestCase):
    def test_contributors_are_included_without_a_duplicate_heading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            text = '## Preface\n\n<!-- handbook-contributors -->\n\nNext paragraph.'
            (root / 'CONTRIBUTORS.md').write_text('# Project authors\n\n- [Writer (@writer)](https://github.com/writer)\n')
            rendered = expand_contributors(text, root)
            self.assertIn('[Writer (@writer)](https://github.com/writer)', rendered)
            self.assertNotIn('# Project authors', rendered)
            self.assertNotIn('<!-- handbook-contributors -->', rendered)
            self.assertEqual(expand_contributors('Unchanged text', root), 'Unchanged text')

    def test_strings_objects_roles_and_escaping(self):
        self.assertEqual(normalize_authors([' Writer ']), [{'name': 'Writer'}])
        people = ['Writer <one>', {'name': 'Editor & two', 'role': 'revision <script>'}]
        html = authors_html(people)
        self.assertIn('Writer &lt;one&gt;', html)
        self.assertIn('revision &lt;script&gt; — Editor &amp; two', html)
        self.assertNotIn('<script>', html)
        self.assertIn(r'Writer \<one\>', authors_markdown(people))
        self.assertEqual(authors_html([]), '')
        for value in ['name', [None], [''], [{'name': ''}], [{'name': 'X', 'role': 1}]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_authors(value)

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
        self.assertIn(r'Writer \<one\>', ''.join(authored['cells'][0]['source']))

    def test_course_credits_persist_in_static_html_without_manifest_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'utils/site'
            source.mkdir(parents=True)
            shutil.copy(REPO_ROOT / 'utils/site/index.html', source / 'index.html')
            meta = root / 'course/lectures/01-fixture/meta.yaml'
            meta.parent.mkdir(parents=True)
            meta.write_text('authors:\n  - name: Writer <one>\n    role: original\n  - name: Editor\n    role: revision\n')
            item = dict(id='lectures/01-fixture', kind='lecture', title='Fixture', number='1',
                        date='', time='', description='', subtitle='', materials=[], references=[], pdf='fixture.pdf')
            week = dict(slug='fixture', number=1, title='Fixture', description='', materials=[item['id']])
            manifest = dict(version=2, course=dict(title='Fixture', description='', weeks=[week]), materials=[item])
            original = json.dumps(manifest)
            output = root / '_site'
            publish_pages(root, output, manifest)
            self.assertEqual(json.dumps(manifest), original)
            for path in ('weeks/fixture/index.html', 'materials/index.html'):
                html = (output / path).read_text()
                self.assertIn('original — Writer &lt;one&gt;', html)
                self.assertIn('revision — Editor', html)
                self.assertNotIn('Writer <one>', html)
