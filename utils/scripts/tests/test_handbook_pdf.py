"""Общая PDF-сборка на синтетических учебниках, без TeX и реальных учебных текстов."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_catalog import load_catalog
from authorship import contributors_markdown
from handbook_pdf import build, documents, printable, source_revision
from repo_paths import REPO_ROOT


def text(value):
    return {'t': 'Str', 'c': value}


def link(href):
    return {'t': 'Link', 'c': [['', [], []], [text('Ссылка')], [href, '']]}


class HandbookPdfTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.output = self.root / 'output/pdf'
        self.sources, self.asts, self.compiled, self.commands = {}, {}, [], []
        self.parse_count = self.svg_count = 0
        style = self.root / 'utils/pdf'
        shutil.copytree(REPO_ROOT / 'utils/pdf', style)
        shutil.copytree(REPO_ROOT / 'utils/latex/tex/latex', self.root / 'utils/latex/tex/latex')
        patch('handbook_pdf.prepare_logo', return_value='logo-hash').start()
        self.contributors = [{'name': 'Синтетический Автор', 'github': 'writer'}]
        self.asts['contributors'] = {'pandoc-api-version': [1, 23, 1], 'meta': {}, 'blocks': [
            {'t': 'Para', 'c': [text('Синтетический Автор (@writer)')]}]}
        self.asts[contributors_markdown(self.contributors)] = self.asts['contributors']
        books = []
        for book in ('alpha', 'beta'):
            base = self.root / 'handbooks' / book
            base.mkdir(parents=True)
            (base / 'meta.yaml').write_text(yaml.safe_dump(dict(contributors=self.contributors), allow_unicode=True))
            self.source(base, book + '-welcome', [])
            chapter = base / '07-section'
            chapter.mkdir()
            self.metadata(chapter, slug='section', paragraphs=['09-second', '01-first', '_template'])
            for name, slug in [('01-first', 'first'), ('09-second', 'second')]:
                folder = chapter / name
                folder.mkdir()
                self.metadata(folder, slug=slug)
                (folder / 'media').mkdir()
                (folder / 'media/shared.svg').write_text('<svg/>')
                image = {'t': 'Image', 'c': [['', [], []], [text('Рисунок')], ['media/shared.svg', '']]}
                blocks = [{'t': 'Header', 'c': [2, ['повтор', [], []], [text('Заголовок')]]},
                          {'t': 'Para', 'c': [image, link('#повтор'), link('../01-first/content.md#повтор')]},
                          {'t': 'CodeBlock', 'c': [['', ['python'], []], 'print("<details>")']}]
                self.source(folder, book + '-' + slug, blocks)
                self.sources[book, slug] = folder
            planned = base / '02-future'
            planned.mkdir()
            self.metadata(planned, slug='future', status='planned', paragraphs=[])
            books.append(dict(slug=book, title=book, description='Описание', chapters=['07-section', '02-future']))
        (self.root / 'handbooks/handbooks.json').write_text(json.dumps(dict(title='Каталог', description='Описание', handbooks=books)))
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, BUILD_CACHE_DIR=str(self.root / 'cache'), BUILD_CACHE_DISABLE='0').start()
        self.env = patch('handbook_pdf.environment', return_value=({'pandoc': 'pandoc-version'}, 'environment-version')).start()
        patch('handbook_pdf.run', side_effect=self.fake_run).start()
        patch('handbook_pdf.renderer_identity', return_value=('playwright-version', 'browser-version')).start()

        def render(source, destination):
            self.svg_count += 1
            destination.write_bytes(b'%PDF-svg')
        patch('handbook_pdf.render_svg', side_effect=render).start()

    def metadata(self, folder, **values):
        item = dict(title='Тема', description='Описание', authors=['Автор'], status='draft', build=True)
        item.update(values)
        (folder / 'README.md').write_text('# Описание')
        (folder / 'meta.yaml').write_text(yaml.safe_dump(item, allow_unicode=True))

    def source(self, folder, marker, blocks):
        (folder / 'content.md').write_text(marker)
        self.asts[marker] = {'pandoc-api-version': [1, 23, 1], 'meta': {},
                             'blocks': [{'t': 'Para', 'c': [text(marker)]}] + blocks}

    def fake_run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if command[0] == 'pandoc' and '--to=json' in command:
            self.parse_count += 1
            return json.dumps(self.asts[kwargs['input']])
        if command[0] == 'pandoc':
            ast = json.loads(Path(command[1]).read_text())
            self.compiled.append(ast)
            Path(command[-1]).write_bytes(b'%PDF-fake')
            return ''
        if command[0] == 'pdfinfo':
            return 'Pages: 2\nEncrypted: no\n'
        raise AssertionError(command)

    def build(self, **kwargs):
        stream = io.StringIO()
        with redirect_stdout(stream):
            build(self.root, **kwargs)
        return stream.getvalue()

    def change_source(self, folder):
        old = (folder / 'content.md').read_text()
        ast = deepcopy(self.asts[old])
        ast['blocks'][0]['c'] = [text(old + '-changed')]
        self.asts[old + '-changed'] = ast
        (folder / 'content.md').write_text(old + '-changed')

    def test_shared_style_and_book_page_breaks(self):
        self.build()
        commands = [(cmd, kwargs) for cmd, kwargs in self.commands if '--pdf-engine=pdflatex' in cmd]
        self.assertEqual(len(commands), 8)
        for command, options in commands:
            self.assertIn('fontfamily:handbookfonts', command)
            self.assertIn('fontenc:T2A', command)
            self.assertFalse(any('geometry:' in value or 'mainfont:' in value for value in command))
            self.assertIn(str(self.root / 'utils/latex/tex/latex') + '//', options['env']['TEXINPUTS'])
        books = [ast for ast in self.compiled if ast['meta']['handbook-level']['c'] == 'book']
        self.assertEqual(len(books), 2)
        for ast in books:
            self.assertIn({'t': 'RawBlock', 'c': ['latex', '\\clearpage']}, ast['blocks'])
        before = len(self.compiled)
        style = self.root / 'utils/latex/tex/latex/academichandbook/academichandbook.sty'
        style.write_text(style.read_text() + '\n% Changed typography\n')
        parse_count, svg_count = self.parse_count, self.svg_count
        self.build()
        self.assertEqual(len(self.compiled), before + 8)
        self.assertEqual((self.parse_count, self.svg_count), (parse_count, svg_count))

    def test_preface_author_metadata_updates_pdf_source_and_cache(self):
        folder = self.root / 'handbooks/alpha'
        source = 'alpha-welcome\n\n<!-- handbook-authors -->'
        (folder / 'content.md').write_text(source)
        for name in ['First Writer', 'Second Writer']:
            (folder / 'meta.yaml').write_text(yaml.safe_dump(dict(preface=dict(authors=[name]))))
            expanded = 'alpha-welcome\n\nАвтор: ' + name
            self.asts[expanded] = {'pandoc-api-version': [1, 23, 1], 'meta': {},
                                  'blocks': [{'t': 'Para', 'c': [text('Автор: ' + name)]}]}
            before = len(self.compiled)
            self.build(selected=folder, book_only=True)
            self.assertEqual(len(self.compiled), before + 1)
            self.assertIn('Автор: ' + name, json.dumps(self.compiled[-1], ensure_ascii=False))
            self.assertTrue(any(options.get('input') == expanded for _, options in self.commands))
            self.assertEqual((folder / 'content.md').read_text(), source)

    def test_logo_change_rebuilds_pdf_without_reparsing(self):
        self.build()
        before = len(self.compiled)
        with patch('handbook_pdf.prepare_logo', return_value='updated-logo'):
            self.build()
        self.assertEqual(len(self.compiled), before + 8)
        self.assertEqual(self.parse_count, 7)

    def test_book_frontmatter_and_scoped_contributors_cache(self):
        self.build()
        books = [ast for ast in self.compiled if ast['meta']['handbook-level']['c'] == 'book']
        self.assertEqual(len(books), 2)
        for ast in books:
            self.assertIn('@writer', json.dumps(ast['meta']['include-before'], ensure_ascii=False))
            self.assertIn('Редакция:', json.dumps(ast['meta']['date'], ensure_ascii=False))
        for ast in self.compiled:
            if ast['meta']['handbook-level']['c'] != 'book':
                self.assertNotIn('include-before', ast['meta'])
                self.assertNotIn('date', ast['meta'])
        updated = self.contributors + [{'name': 'Другой Автор'}]
        for slug in ('alpha', 'beta'):
            (self.root / f'handbooks/{slug}/meta.yaml').write_text(yaml.safe_dump(dict(contributors=updated), allow_unicode=True))
        self.asts['contributors-updated'] = deepcopy(self.asts['contributors'])
        self.asts['contributors-updated']['blocks'].append({'t': 'Para', 'c': [text('Другой Автор')]})
        self.asts[contributors_markdown(updated)] = self.asts['contributors-updated']
        self.build()
        self.assertEqual(len(self.compiled), 10, 'Участники меняют только полные книги')
        with patch('handbook_pdf.source_revision', return_value=('new-commit', '2026-10-25')):
            self.build()
        self.assertEqual(len(self.compiled), 12, 'Редакция меняет только полные книги')

    def test_revision_tag_date_and_dirty_state(self):
        import subprocess
        values = {('rev-parse', '--short=12', 'HEAD'): 'abcdef123456',
                  ('tag', '--points-at', 'HEAD'): 'main-preview\nv2026.10.25.2\nv2026.10.25.10',
                  ('status', '--porcelain', '--untracked-files=normal'): ' M CONTRIBUTORS.md',
                  ('log', '-1', '--format=%cs'): '2026-10-25'}
        def git(command, **kwargs):
            return subprocess.CompletedProcess(command, 0, values[tuple(command[3:])], '')
        with patch('handbook_pdf.subprocess.run', side_effect=git):
            revision, date = source_revision(self.root)
        self.assertEqual(revision, 'v2026.10.25.10 / abcdef123456 (с локальными изменениями)')
        self.assertEqual(date, '2026-10-25')
        with patch('handbook_pdf.subprocess.run', side_effect=FileNotFoundError):
            self.assertEqual(source_revision(self.root), ('Локальная редакция (без Git)', ''))

    def test_inline_contributors_replace_the_separate_frontmatter(self):
        book = self.root / 'handbooks/alpha'
        (book / 'content.md').write_text('welcome <!-- handbook-contributors -->')
        source = 'welcome ' + contributors_markdown(self.contributors)
        self.asts[source] = deepcopy(self.asts['alpha-welcome'])
        self.asts[source]['blocks'].append({'t': 'Para', 'c': [text('Автор (@writer)')]})
        self.build(selected=book)
        full = next(ast for ast in self.compiled if ast['meta']['handbook-level']['c'] == 'book')
        self.assertEqual(full['meta']['include-before']['c'], [])
        self.assertIn('@writer', json.dumps(full['blocks'], ensure_ascii=False))
        self.assertNotIn('handbook-contributors', json.dumps(full['blocks']))

    def test_each_book_uses_its_own_contributor_metadata(self):
        for slug, name in [('alpha', 'Alpha person'), ('beta', 'Beta person')]:
            people = [dict(name=name)]
            (self.root / f'handbooks/{slug}/meta.yaml').write_text(yaml.safe_dump(dict(contributors=people)))
            self.asts[contributors_markdown(people)] = {'pandoc-api-version': [1, 23, 1], 'meta': {},
                'blocks': [{'t': 'Para', 'c': [text(name)]}]}
        self.build(book_only=True)
        books = [json.dumps(ast, ensure_ascii=False) for ast in self.compiled]
        self.assertEqual(sum('Alpha person' in book for book in books), 1)
        self.assertEqual(sum('Beta person' in book for book in books), 1)
        self.assertFalse(any('Alpha person' in book and 'Beta person' in book for book in books))

    def test_book_only_single_output_and_preserves_other_levels(self):
        self.build()
        paragraph = self.output / 'alpha/section/first/paragraph.pdf'
        before = paragraph.read_bytes()
        target = self.root / 'release/book.pdf'
        self.build(selected=self.root / 'handbooks/alpha', book_only=True, output=target)
        self.assertTrue(target.is_file())
        self.assertEqual(paragraph.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'путь учебника'):
            self.build(selected=self.sources['alpha', 'first'], book_only=True)
        shutil.rmtree(self.output)
        self.build(book_only=True)
        self.assertEqual(sorted(p.relative_to(self.output).as_posix() for p in self.output.rglob('*.pdf')),
                         ['alpha/handbook.pdf', 'beta/handbook.pdf'])

    def test_all_levels_order_namespaces_and_shared_images(self):
        self.build(jobs=2)
        self.assertEqual(len(list(self.output.rglob('*.pdf'))), 8)
        self.assertEqual(self.svg_count, 1)
        self.assertEqual(len(self.compiled), 8)
        ast = next(ast for ast in self.compiled if ast['meta']['title']['c'] == 'alpha')
        value = json.dumps(ast, ensure_ascii=False)
        self.assertLess(value.index('alpha-second'), value.index('alpha-first'))
        self.assertIn('#alpha--section--first--повтор', value)
        self.assertIn('alpha--section--second--повтор', value)
        self.assertIn('Автор:', value)
        self.assertNotIn('future', value)
        self.assertTrue((self.output / 'alpha/section/first/paragraph.pdf').is_file())

    def test_warm_restore_and_precise_invalidation(self):
        self.build()
        parses = self.parse_count
        shutil.rmtree(self.output)
        self.assertIn('компиляций: 0', self.build())
        self.assertEqual(self.parse_count, parses)
        self.assertEqual(self.svg_count, 1)
        self.assertEqual(len(self.compiled), 8)
        self.change_source(self.sources['alpha', 'first'])
        self.build()
        self.assertEqual(self.parse_count, parses + 1)
        self.assertEqual(self.svg_count, 1)
        self.assertEqual(len(self.compiled), 11)

    def test_profile_environment_and_corrupt_cache(self):
        self.build()
        style = self.root / 'utils/pdf/pdf-header.tex'
        style.write_text(style.read_text() + '\n% changed\n')
        self.build()
        self.assertEqual(len(self.compiled), 16)
        self.env.return_value = ({'pandoc': 'pandoc-version'}, 'new-environment')
        self.build()
        self.assertEqual(len(self.compiled), 24)
        for pdf in (self.root / 'cache/handbook-pdf').rglob('document.pdf'):
            pdf.write_bytes(b'corrupt')
        self.build()
        self.assertEqual(len(self.compiled), 32)
        self.assertEqual(self.parse_count, 7)

    def test_selected_subtree_cleanup_and_custom_output(self):
        self.build()
        folder = self.sources['alpha', 'first']
        self.metadata(folder, slug='first', build=False)
        self.build(selected=folder)
        self.assertFalse((self.output / 'alpha/section/first/paragraph.pdf').exists())
        self.assertTrue((self.output / 'beta/section/first/paragraph.pdf').is_file())
        custom = self.root / 'С пробелами/Параграф.pdf'
        self.build(selected=self.sources['beta', 'first'], output=custom)
        self.assertTrue(custom.is_file())
        with self.assertRaisesRegex(ValueError, 'один документ'):
            self.build(selected=self.root / 'handbooks/beta', output=custom)

    def test_deleted_material_and_cache_disabled(self):
        self.build()
        chapter = self.root / 'handbooks/alpha/07-section'
        meta = yaml.safe_load((chapter / 'meta.yaml').read_text())
        meta['paragraphs'] = ['09-second']
        (chapter / 'meta.yaml').write_text(yaml.safe_dump(meta))
        shutil.rmtree(self.sources['alpha', 'first'])
        self.build(selected=self.root / 'handbooks/alpha')
        self.assertFalse((self.output / 'alpha/section/first/paragraph.pdf').exists())
        self.assertTrue((self.output / 'beta/section/first/paragraph.pdf').exists())
        before = len(self.compiled)
        with patch.dict(os.environ, BUILD_CACHE_DISABLE='1'):
            self.build()
        self.assertEqual(len(self.compiled), before + 7)

    def test_external_links_prefix_and_image_escape(self):
        folder = self.sources['alpha', 'second']
        custom = self.root / 'single.pdf'
        self.build(selected=folder, output=custom, site_url='https://example.org/materials/dev/')
        value = json.dumps(self.compiled[-1], ensure_ascii=False)
        self.assertIn('https://example.org/materials/dev/handbooks/alpha/section/first/#повтор', value)
        (folder / 'media/shared.svg').unlink()
        (folder / 'media/shared.svg').symlink_to(self.root / 'outside.svg')
        (self.root / 'outside.svg').write_text('<svg/>')
        with self.assertRaisesRegex(ValueError, 'вне handbooks'):
            self.build(selected=folder)

    def test_failed_compilation_is_not_cached_or_published(self):
        def fail(command, **kwargs):
            if command[0] == 'pandoc' and '--pdf-engine=pdflatex' in command:
                raise ValueError('compile failed')
            return self.fake_run(command, **kwargs)
        with patch('handbook_pdf.run', side_effect=fail):
            with self.assertRaisesRegex(ValueError, 'compile failed'):
                self.build(selected=self.sources['alpha', 'first'])
        self.assertFalse(list(self.output.rglob('*.pdf')))
        self.assertFalse((self.root / 'cache/handbook-pdf').exists())
        self.build(selected=self.sources['alpha', 'first'])
        self.assertEqual(len(self.compiled), 1)

    def test_generic_catalog_and_skipped_materials(self):
        catalog = load_catalog(self.root)
        self.assertEqual([b['slug'] for b in catalog['handbooks']], ['alpha', 'beta'])
        self.assertEqual(len(documents(catalog)), 8)
        folder = self.sources['alpha', 'first']
        self.metadata(folder, slug='first', status='planned')
        (folder / 'content.md').unlink()
        self.assertEqual(len(documents(load_catalog(self.root))), 7)
        # Повтор slug в одном разделе недопустим; между учебниками допустим.
        self.metadata(self.sources['alpha', 'second'], slug='first')
        with self.assertRaisesRegex(ValueError, 'повтор slug'):
            load_catalog(self.root)

    def test_reordering_only_rebuilds_composite_documents(self):
        self.build()
        chapter = self.root / 'handbooks/alpha/07-section'
        self.metadata(chapter, slug='section', paragraphs=['01-first', '09-second'])
        self.build()
        self.assertEqual(len(self.compiled), 10)
        self.assertEqual(self.parse_count, 7)
        self.assertEqual(self.svg_count, 1)

    def test_metadata_resources_and_stale_outputs_are_scoped(self):
        self.build()
        chapter = self.root / 'handbooks/alpha/07-section'
        self.metadata(chapter, slug='section', paragraphs=['09-second', '01-first'],
                      authors=[dict(name='Writer_Name', role='Редактор')])
        self.build()
        self.assertEqual(len(self.compiled), 10)
        value = json.dumps(self.compiled[-1], ensure_ascii=False)
        self.assertIn('Writer_Name', value)
        self.assertNotIn('Writer\\_Name', value)
        # Смена рисунка влияет только на использующий его параграф и предков.
        (self.sources['alpha', 'first'] / 'media/shared.svg').write_text('<svg>changed</svg>')
        self.build()
        self.assertEqual(len(self.compiled), 13)
        self.assertEqual(self.svg_count, 2)
        stale = self.output / 'alpha/deleted/chapter.pdf'
        stale.parent.mkdir()
        stale.write_bytes(b'%PDF-stale')
        unrelated = self.output / 'beta/deleted/chapter.pdf'
        unrelated.parent.mkdir()
        unrelated.write_bytes(b'%PDF-stale')
        self.build(selected=self.root / 'handbooks/alpha')
        self.assertFalse(stale.exists())
        self.assertTrue(unrelated.exists())

    def test_disabled_book_and_book_without_preface(self):
        path = self.root / 'handbooks/handbooks.json'
        data = json.loads(path.read_text())
        data['handbooks'][1]['build'] = False
        path.write_text(json.dumps(data))
        (self.root / 'handbooks/alpha/content.md').unlink()
        self.build()
        self.assertEqual(len(self.compiled), 4)
        self.assertFalse((self.output / 'beta').exists())
        self.assertTrue((self.output / 'alpha/handbook.pdf').exists())

    def test_resource_and_curriculum_links_use_published_slugs(self):
        folder = self.sources['alpha', 'first']
        (self.root / 'handbooks/alpha/CURRICULUM.md').write_text('Программа')
        (folder / 'data').mkdir()
        (folder / 'data/данные с пробелами.csv').write_text('x,y')
        marker = (folder / 'content.md').read_text()
        self.asts[marker]['blocks'].append({'t': 'Para', 'c': [
            link('data/данные с пробелами.csv'), link('../../CURRICULUM.md')
        ]})
        self.build(selected=folder, site_url='https://example.org/dev/')
        value = json.dumps(self.compiled[-1], ensure_ascii=False)
        self.assertIn('https://example.org/dev/handbooks/alpha/section/first/data/', value)
        self.assertIn('%20', value)
        self.assertIn('https://example.org/dev/handbooks/alpha/curriculum/', value)
        self.assertNotIn('07-section', value)
        self.assertNotIn('01-first', value)

    def test_svg_renderer_update_invalidates_images_and_pdfs(self):
        self.build()
        with patch('handbook_pdf.renderer_identity', return_value=('new-playwright', 'new-browser')):
            self.build()
        self.assertEqual(self.parse_count, 7)
        self.assertEqual(self.svg_count, 2)
        self.assertEqual(len(self.compiled), 16)

    def test_details_ast_preserves_code_and_arbitrary_summary(self):
        ast = [{'t': 'RawBlock', 'c': ['html', '<details>']},
               {'t': 'RawBlock', 'c': ['html', '<summary>']},
               {'t': 'Plain', 'c': [text('Любое название')]},
               {'t': 'RawBlock', 'c': ['html', '</summary>']},
               {'t': 'CodeBlock', 'c': [['', [], []], '<details><summary>code</summary>']},
               {'t': 'RawBlock', 'c': ['html', '</details>']}]
        result = printable(ast)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['c'][0]['t'], 'Strong')
        self.assertEqual(result[1], ast[4])


if __name__ == '__main__':
    unittest.main()
