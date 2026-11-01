"""Инкрементальная PDF-сборка параграфов, глав и учебников."""
from __future__ import annotations
from handbook_blocks import parse as parse_blocks, markdown as block_markdown, pdf_questions

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import quote, unquote, urljoin, urlsplit

from authorship import authors_text, expand_authors, expand_contributors, contributors_markdown, CONTRIBUTORS_MARKER
from build_cache import Cache
from handbook_catalog import load_catalog
from handbook_publication import read_publication, frontmatter, endmatter
from handbook_svg import renderer_identity, render_svg
from handbook_layout import load_layout, layout_part
from repo_paths import REPO_ROOT

DEFAULT_SITE = 'https://materials.beloai.by/'
PROFILES = ('reader', 'belarus-textbook')
TEX_FONTS = ('cmr10', 'cmbx10', 'cmti10', 'cmss10', 'cmtt10', 'cmmi10', 'cmsy10', 'cmex10',
             'sfrm1000', 'sfbx1000', 'sfti1000', 'sfss1000', 'sfsx1000', 'sftt1000')


def digest(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, **kwargs):
    result = subprocess.run(command, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(f"Ошибка команды {command[0]}:\n{result.stdout}\n{result.stderr}")
    return result.stdout


def tool_identity(name):
    binary = shutil.which(name)
    if not binary:
        raise ValueError(f'Не найдена утилита {name}; см. utils/pdf/README.md')
    # Хэш бинарника определяет версию без запуска Pandoc на тёплой сборке.
    return file_hash(Path(binary).resolve())


def environment():
    tools = {name: tool_identity(name) for name in ('pandoc', 'pdflatex', 'xelatex', 'pdfinfo')}
    # Форматы TeX и реестр пакетов меняются независимо от бинарника движка.
    tex = []
    for name in ('pdflatex.fmt', 'xelatex.fmt', 'texlive.tlpdb', *(font + '.pfb' for font in TEX_FONTS)):
        path = ''
        if name.endswith('.fmt'):
            engine = 'xetex' if name == 'xelatex.fmt' else 'pdftex'
            result = subprocess.run(['kpsewhich', '-engine=' + engine, name], text=True, capture_output=True)
            path = result.stdout.strip()
        elif name.endswith('.pfb'):
            path = run(['kpsewhich', name]).strip()
        if not path and name == 'texlive.tlpdb':
            # MiKTeX has no TeX Live package database or TEXMFROOT variable.
            # Keep the format and font hashes above, and skip this one input.
            result = subprocess.run(['kpsewhich', '-var-value=TEXMFROOT'],
                                    text=True, capture_output=True)
            if result.returncode == 0 and result.stdout.strip():
                path = str(Path(result.stdout.strip()) / 'tlpkg/texlive.tlpdb')
        if path and Path(path).is_file():
            tex.append(file_hash(path))
    return tools, digest(tools, tex, os.environ.get('BUILD_ENV_ID', ''))


def profile_files(root, profile='reader'):
    """Все локальные зависимости оформления, независимо от каталога TeX."""
    style = root / 'utils/pdf'
    paths = [style / ('pdf-header.tex' if profile == 'reader' else 'belarus-textbook-header.tex'),
             style / 'logo.tex', style / 'keep-short-code.lua']
    packages = root / 'utils/latex/tex/latex'
    shared = packages / 'academichandbook'
    paths.extend(shared / name for name in ('handbookcommon.sty', 'handbookfonts.sty'))
    if profile == 'reader':
        paths.append(shared / 'academichandbook.sty')
        paths.extend((packages / 'olymp').glob('*.sty'))
    else:
        paths.extend((packages / 'belarustextbook').glob('*.sty'))
        for name in ('print-layout.yml',):
            if (style / name).is_file():
                paths.append(style / name)
    result = [(p.relative_to(root).as_posix(), file_hash(p)) for p in sorted(paths)]
    if profile == 'belarus-textbook':
        result.append(('handbook_layout.py', file_hash(Path(__file__).with_name('handbook_layout.py'))))
    return result


def source_revision(root):
    """Стабильная редакция исходников: тег/commit, дата commit и локальные правки."""
    def git(*args):
        try:
            result = subprocess.run(['git', '-C', str(root), *args], text=True, capture_output=True)
        except FileNotFoundError:
            return ''
        return result.stdout.strip() if result.returncode == 0 else ''

    sha = git('rev-parse', '--short=12', 'HEAD')
    if not sha:
        return 'Локальная редакция (без Git)', ''
    tags = [tag for tag in git('tag', '--points-at', 'HEAD').splitlines()
            if re.fullmatch(r'v\d{4}\.\d{2}\.\d{2}(?:\.[1-9]\d*)?', tag)]
    revision = (max(tags, key=lambda tag: tuple(map(int, tag[1:].split('.')))) + ' / ' if tags else '') + sha
    if git('status', '--porcelain', '--untracked-files=normal'):
        revision += ' (с локальными изменениями)'
    return revision, git('log', '-1', '--format=%cs')


def prepare_logo(root, scratch, env):
    """Одна векторная эмблема для всех документов; шрифты берутся с сайта."""
    try:
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError as error:
        raise ValueError('Для логотипа установите зависимости utils/pdf/requirements.txt') from error

    fonts = root / 'utils/site/fonts'
    sources = [('unbounded-latin-cyrillic.woff2', 'Unbounded.ttf', 700),
               ('ibm-plex-sans-latin-cyrillic.woff2', 'IBMPlexSans.ttf', 400)]
    template = root / 'utils/pdf/logo.tex'
    key = digest(env, file_hash(template), file_hash(__file__), importlib.metadata.version('fonttools'),
                 [(name, file_hash(fonts / name), weight) for name, _, weight in sources])
    cache = Cache('handbook-logo', key)
    target = scratch / 'handbook-logo.pdf'
    with tempfile.TemporaryDirectory(prefix='logo-', dir=scratch) as temp:
        folder = Path(temp)
        pdf = folder / 'logo.pdf'
        if not (cache.restore(folder) and pdf.is_file()):
            for name, filename, weight in sources:
                with TTFont(fonts / name) as font:
                    axes = {axis.axisTag: axis.defaultValue for axis in font['fvar'].axes}
                    axes['wght'] = weight
                    static = instantiateVariableFont(font, axes, inplace=False, updateFontNames=True)
                    static.flavor = None
                    static.save(folder / filename)
            shutil.copyfile(template, folder / 'logo.tex')
            run(['xelatex', '-halt-on-error', '-interaction=nonstopmode', 'logo.tex'], cwd=folder)
            run(['pdfinfo', str(pdf)])
            cache.save(folder, [pdf])
        shutil.copyfile(pdf, target)
    return file_hash(target)


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def printable(value):
    """Удалять HTML-обёртки в AST, оставляя содержимое и fenced code нетронутыми."""
    if isinstance(value, list):
        result, summary = [], False
        for node in value:
            if isinstance(node, dict) and node.get('t') in {'RawBlock', 'RawInline'} and node['c'][0] == 'html':
                html = node['c'][1]
                if re.fullmatch(r'\s*</?details(?:\s[^>]*)?>\s*', html):
                    continue
                if re.fullmatch(r'\s*<summary(?:\s[^>]*)?>\s*', html):
                    summary = True
                    continue
                if re.fullmatch(r'\s*</summary>\s*', html):
                    summary = False
                    continue
                if re.fullmatch(r'\s*<br\s*/?>\s*', html):
                    result.append({'t': 'LineBreak'})
                    continue
            node = printable(node)
            if summary and isinstance(node, dict) and node.get('t') in {'Plain', 'Para'}:
                node = {'t': 'Para', 'c': [{'t': 'Strong', 'c': node['c']}]}
            result.append(node)
        return result
    if isinstance(value, dict):
        return {key: printable(child) for key, child in value.items()}
    return value


def format_objects(value):
    """Связать отдельные курсивные подписи с рисунками и таблицами в AST.

    Номера берутся из текста, чтобы не менять существующие ссылки. Alt-текст
    не становится подписью. Обход включает списки, цитаты и раскрытые решения.
    """
    def caption(node, kind):
        if node.get('t') != 'Para' or len(node['c']) != 1 or node['c'][0]['t'] != 'Emph':
            return None
        inlines = deepcopy(node['c'][0]['c'])
        leading = ''
        for inline in inlines:
            if inline['t'] == 'Str':
                leading += inline['c']
            elif inline['t'] in {'Space', 'SoftBreak'}:
                leading += ' '
            else:
                break
        match = re.match(r'^(Рисунок|Рис\.|Таблица)\s+(\d+)\s*(?:—|[.:-])\s+', leading)
        if not match or ('table' if match[1] == 'Таблица' else 'figure') != kind:
            return None
        remaining = match.end()
        while remaining:
            inline = inlines[0]
            size = len(inline['c']) if inline['t'] == 'Str' else 1
            if size <= remaining:
                inlines.pop(0)
                remaining -= size
            else:
                inline['c'] = inline['c'][remaining:]
                remaining = 0
        if inlines and inlines[-1]['t'] == 'Str':
            inlines[-1]['c'] = re.sub(r'\.\s*$', '', inlines[-1]['c'])
        prefix = ('Таблица' if kind == 'table' else 'Рисунок') + f' {match[2]} — '
        return [{'t': 'Str', 'c': prefix}] + inlines

    def image(node):
        if node.get('t') != 'Para' or len(node['c']) != 1:
            return False
        inline = node['c'][0]
        return inline['t'] == 'Image' or (inline['t'] == 'Link' and len(inline['c'][1]) == 1
                                         and inline['c'][1][0]['t'] == 'Image')

    if isinstance(value, dict):
        return {key: format_objects(child) for key, child in value.items()}
    if not isinstance(value, list):
        return value
    nodes = [format_objects(child) for child in value]
    result, index = [], 0
    while index < len(nodes):
        node = nodes[index]
        if not isinstance(node, dict):
            result.append(node)
            index += 1
            continue
        following = nodes[index + 1] if index + 1 < len(nodes) and isinstance(nodes[index + 1], dict) else {}
        if image(node):
            label = caption(following, 'figure')
            blocks = [node]
            if label:
                blocks.append({'t': 'Div', 'c': [['', ['handbook-caption'], []], [{'t': 'Para', 'c': label}]]})
                index += 1
            result.append({'t': 'Div', 'c': [['', ['handbook-figure'], []], blocks]})
        elif following.get('t') == 'Table' and not following['c'][1][1] and (label := caption(node, 'table')):
            following['c'][1] = [None, [{'t': 'Plain', 'c': label}]]
            result.append(following)
            index += 1
        else:
            result.append(node)
        index += 1
    return result


def require_object_captions(value, context):
    """Reject unlabelled standalone objects before publishing a handbook."""
    for node in walk(value):
        if node.get('t') == 'Div' and 'handbook-figure' in node['c'][0][1]:
            if len(node['c'][1]) < 2:
                raise ValueError(f'{context}: рисунок без соседней подписи «Рисунок N — Название»')
        elif node.get('t') == 'Table' and not node['c'][1][1]:
            raise ValueError(f'{context}: таблица без подписи «Таблица N — Название» сверху')


def editorial_layout(value):
    """Переносить таблицы, код, ссылки и группы формул на узкой полосе."""
    if isinstance(value, list):
        return [editorial_layout(child) for child in value]
    if not isinstance(value, dict):
        return value
    node = {key: editorial_layout(child) for key, child in value.items()}
    if node.get('t') == 'Table':
        specs = node['c'][2]
        if specs and all(width['t'] == 'ColWidthDefault' for _, width in specs):
            # Explicit paragraph columns allow wrapping and keep longtable's
            # repeating headers. Equal widths are stable across Pandoc versions.
            for spec in specs:
                spec[1] = {'t': 'ColWidth', 'c': 1 / len(specs)}
        # TeX does not hyphenate the first word of a paragraph automatically.
        # A zero-width space enables it in Pandoc's narrow paragraph columns,
        # including the minipages used for repeated table headers.
        start = {'t': 'RawInline', 'c': ['latex', r'\hspace{0pt}']}
        for block in walk(node['c'][3:]):
            if block.get('t') in ('Plain', 'Para') and block['c'] and block['c'][0] != start:
                block['c'].insert(0, start.copy())
        # Russian hyphenation cannot break Latin column labels. Add invisible
        # opportunities scaled to the number of columns, without shrinking text.
        chunk = max(3, min(8, 32 // max(1, len(specs))))
        for inline in walk(node['c'][3:]):
            if inline.get('t') not in ('Str', 'Code'):
                continue
            kind = inline['t']
            content = inline['c'] if kind == 'Str' else inline['c'][1]
            pieces = re.split(r'([A-Za-z]{' + str(chunk + 1) + r',})', content)
            if len(pieces) == 1:
                continue
            inlines = []
            for piece in filter(None, pieces):
                parts = [piece[i:i + chunk] for i in range(0, len(piece), chunk)] if piece.isascii() and piece.isalpha() else [piece]
                for index, part in enumerate(parts):
                    if index:
                        inlines.append({'t': 'RawInline', 'c': ['latex', r'\allowbreak{}']})
                    inlines.append({'t': kind, 'c': part if kind == 'Str' else [inline['c'][0], part]})
            inline.update(t='Span', c=[['', [], []], inlines])
    if node.get('t') == 'Link':
        inlines = []
        for inline in node['c'][1]:
            if inline['t'] == 'Str' and re.search(r'[./]', inline['c']):
                parts = re.split(r'(?<=[./_\-])', inline['c'])
                for part in filter(None, parts):
                    inlines.extend([{'t': 'Str', 'c': part}, {'t': 'RawInline', 'c': ['latex', r'\allowbreak{}']}])
            else:
                inlines.append(inline)
        node['c'][1] = inlines
    if node.get('t') == 'Code' and len(node['c'][1]) > 8:
        attr, content = node['c']
        parts = re.split(r'(?<=[./_\\\-])|(?<=[a-z0-9])(?=[A-Z])', content)
        inlines = []
        for part in filter(None, parts):
            for offset in range(0, len(part), 8):
                inlines.extend([{'t': 'Code', 'c': [attr, part[offset:offset + 8]]},
                                {'t': 'RawInline', 'c': ['latex', r'\allowbreak{}']}])
        node = {'t': 'Span', 'c': [['', [], []], inlines]}
    if node.get('t') == 'Math' and node['c'][0]['t'] == 'DisplayMath':
        expression = node['c'][1]
        # Source authors already separate independent expressions with qquad.
        # Keep explicit matrices/alignment and paired delimiters intact.
        if r'\qquad' in expression and not re.search(r'\\(?:begin|left|right)\b', expression):
            pieces = re.split(r'\\qquad\b', expression)
            if len(pieces) > 1 and all(piece.count('{') == piece.count('}') for piece in pieces):
                node['c'][1] = r'\begin{gathered}' + r'\\[3pt]'.join(pieces) + r'\end{gathered}'
        elif len(expression) > 100 and not re.search(r'\\(?:begin|left|right)\b|&', expression):
            # Split long chains at top-level equalities, never inside fractions
            # or text. Keep the first equality on the first line and align the
            # remaining equalities without changing any mathematical tokens.
            depth = 0
            cuts = []
            for match in re.finditer(r'\\.|[{}=]', expression):
                token = match.group()
                if token == '{':
                    depth += 1
                elif token == '}':
                    depth -= 1
                elif token == '=' and depth == 0:
                    cuts.append(match.start())
            if len(cuts) > 1 and depth == 0:
                rows = [expression[:cuts[0]] + '&' + expression[cuts[0]:cuts[1]]]
                rows.extend('&' + expression[start:end] for start, end in
                            zip(cuts[1:], [*cuts[2:], len(expression)]))
                node['c'][1] = r'\begin{aligned}' + r'\\[3pt]'.join(rows) + r'\end{aligned}'
    return node


def namespace(identifier):
    return identifier.replace('/', '--')


def header(level, item, title=None):
    context = 'handbook-context-chapter' if level == 1 else 'handbook-context-section'
    return {'t': 'Header', 'c': [level, [namespace(item['id']), [context], []], [{'t': 'Str', 'c': title or item['title']}]]}


def separate_answers(blocks, identifier):
    questions, answers = pdf_questions(blocks, identifier)
    return questions, answers, ('answers--' + namespace(identifier) if answers else None)


def documents(catalog):
    """План задач в порядке метаданных, включая главы без вводного текста."""
    result = []
    for book in catalog['handbooks']:
        if book.get('build') is False or book.get('status') == 'planned':
            continue
        book_items = [(book, 0)] if '_content' in book else []
        for chapter in book['sections']:
            if chapter['status'] == 'planned':
                continue
            paragraphs = [catalog['_lessons'][pid] for pid in chapter['lessons']
                          if catalog['_lessons'][pid]['status'] != 'planned']
            if '_content' not in chapter and not paragraphs:
                continue
            chapter_items = [(chapter, 1)] + [(item, 2) for item in paragraphs]
            book_items.extend(chapter_items)
            for item in paragraphs:
                result.append(dict(item=item, parts=[(item, 1)], filename=item['id'] + '/paragraph.pdf'))
            result.append(dict(item=chapter, parts=chapter_items, filename=chapter['id'] + '/chapter.pdf'))
        if book_items:
            result.append(dict(item=book, parts=book_items, filename=book['id'] + '/handbook.pdf'))
    return result


class Builder:
    def __init__(self, root, scratch, site_url, tools, env, profile='reader'):
        self.root, self.scratch, self.site_url = root, scratch, site_url
        self.code = digest(file_hash(__file__), file_hash(Path(__file__).with_name('handbook_catalog.py')),
                           file_hash(Path(__file__).with_name('authorship.py')),
                           file_hash(Path(__file__).with_name('handbook_svg.py')),
                           file_hash(Path(__file__).with_name('handbook_blocks.py')))
        self.tools, self.env = tools, env
        self.svg_identity = None
        self.prepared, self.images = {}, {}
        self.compilations = 0
        self.image_conversions = 0
        self.hits = 0
        self.profile_name = profile
        self.profile = profile_files(root, profile)
        self.logo = prepare_logo(root, scratch, env)
        self.contributors = {}
        self.revision = None

    def book_frontmatter(self, item):
        if self.revision is None:
            self.revision = source_revision(self.root)
        if '_content' in item and CONTRIBUTORS_MARKER in item['_content'].read_text(encoding='utf-8'):
            return []
        source = contributors_markdown(item.get('_contributors', []))
        if not source:
            return []
        if source not in self.contributors:
            _, ast, hit = self.prepare({'id': 'contributors', '_source': source})
            self.hits += hit
            self.contributors[source] = ast['blocks']
        return [
            {'t': 'RawBlock', 'c': ['latex', '\\clearpage']},
            {'t': 'Header', 'c': [1, ['handbook-contributors', ['unnumbered', 'handbook-context-chapter'], []],
                                 [{'t': 'Str', 'c': 'Авторы и участники проекта BelOAI'}]]},
            *deepcopy(self.contributors[source]),
            {'t': 'RawBlock', 'c': ['latex', '\\clearpage']},
        ]

    def prepare(self, item):
        source = item['_source'] if '_source' in item else item['_content'].read_text(encoding='utf-8')
        source = expand_contributors(expand_authors(source, item.get('_content_authors', item.get('authors'))),
                                     item.get('_contributors', []))
        source = block_markdown(parse_blocks(source, item['id']))
        key = digest(source, self.tools['pandoc'], self.code)
        cache = Cache('handbook-source', key)
        folder = self.scratch / 'sources' / namespace(item['id'])
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'source.json'
        hit = cache.restore(folder) and path.is_file()
        if not hit:
            ast = format_objects(printable(json.loads(run(
                ['pandoc', '--from=markdown+raw_tex+raw_html-implicit_figures', '--to=json'], input=source))))
            require_object_captions(ast, item['id'])
            path.write_text(json.dumps(ast, ensure_ascii=False), encoding='utf-8')
            cache.save(folder, [path])
        return item['id'], json.loads(path.read_text(encoding='utf-8')), hit

    def image_path(self, item, href):
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"{item['id']}: изображение должно быть локальным: {href}")
        path = (item['_folder'] / unquote(parsed.path)).resolve()
        if not path.is_relative_to((self.root / 'handbooks').resolve()) or not path.is_file():
            raise ValueError(f"{item['id']}: изображение отсутствует или вне handbooks: {href}")
        return path

    def image(self, path):
        svg = path.suffix.lower() == '.svg'
        vector_patterns = svg and self.profile_name == 'belarus-textbook' and b'<pattern' in path.read_bytes()
        key = digest(file_hash(path), 'svg' if svg else path.suffix.lower(),
                     [self.svg_identity, self.env] if svg else '', self.code,
                     'vector-patterns' if vector_patterns else '')
        filename = key + ('.pdf' if svg else path.suffix.lower())
        target = self.scratch / 'images' / filename
        target.parent.mkdir(exist_ok=True)
        if svg:
            cache = Cache('handbook-svg', key)
            with tempfile.TemporaryDirectory(dir=self.scratch) as temp:
                folder = Path(temp)
                rendered = folder / 'image.pdf'
                hit = cache.restore(folder) and rendered.is_file()
                if not hit:
                    if vector_patterns:
                        render_svg(path, rendered, vector_patterns=True)
                    else:
                        render_svg(path, rendered)
                    cache.save(folder, [rendered])
                shutil.copyfile(rendered, target)
            return path, 'images/' + filename, hit, not hit
        shutil.copyfile(path, target)
        return path, 'images/' + filename, False, False

    def compose(self, task, all_items):
        included = {item['id'] for item, _ in task['parts']}
        paths = {}
        for item in all_items.values():
            folder = item['_folder'].resolve()
            for path in (folder, folder / 'README.md', folder / 'content.md', folder / 'index.html'):
                paths[path] = item
            if '/' not in item['id'] and (folder / 'CURRICULUM.md').is_file():
                paths[folder / 'CURRICULUM.md'] = dict(id=item['id'] + '/curriculum')
        ast = None
        blocks = []
        paragraph = len(task['item']['id'].split('/')) == 3
        chapter = len(task['item']['id'].split('/')) == 2
        answer_sections = []
        paragraph_number = 0
        chapter_number = -1
        overrides = load_layout(self.root / 'utils/pdf/print-layout.yml') if self.profile_name == 'belarus-textbook' else {}
        def flush_answers():
            if not answer_sections:
                return
            blocks.append({'t': 'RawBlock', 'c': ['latex', r'\clearpage']})
            blocks.append({'t': 'Header', 'c': [2, ['answers-' + namespace(answer_sections[0][0]['id']), ['unnumbered'], []],
                           [{'t': 'Str', 'c': 'Подсказки и решения'}]]})
            for owner, number, feedback, label in answer_sections:
                blocks.append({'t': 'RawBlock', 'c': ['latex', r'\par\addvspace{14pt}\Needspace{10\baselineskip}']})
                blocks.append({'t': 'Para', 'c': [{'t': 'Strong', 'c': [{'t': 'Str', 'c': owner['title']}]}]})
                blocks.extend(feedback)
            answer_sections.clear()

        for item, level in task['parts']:
            if level == 1:
                flush_answers()
            level = 1 if paragraph else level
            if level == 0:
                blocks.append({'t': 'RawBlock', 'c': ['latex', '\\handbookchapter{Об учебнике}']})
            chapter_heading = level == 1 and not paragraph
            paragraph_heading = level == 2 or paragraph
            if chapter_heading or paragraph_heading:
                blocks.append({'t': 'RawBlock', 'c': ['latex', '\\clearpage']})
            if chapter and level == 2:
                paragraph_number += 1
            if level:
                title = ('Глава 1. ' + item['title'] if chapter and level == 1 else
                         f'1.{paragraph_number}. {item["title"]}' if chapter and level == 2 else None)
                if self.profile_name == 'belarus-textbook' and chapter_heading:
                    chapter_number += 1
                    title = f'Глава {chapter_number}. {item["title"]}'
                heading = header(level, item, title)
                if self.profile_name == 'belarus-textbook' and chapter_heading:
                    heading['c'][1][1].append('handbook-chapter-opening')
                elif self.profile_name == 'belarus-textbook' and paragraph_heading:
                    heading['c'][1][1].append('handbook-lesson-opening')
                blocks.append(heading)
            credit = authors_text(item.get('authors', []))
            if credit and not chapter:
                blocks.append({'t': 'Para', 'c': [{'t': 'Emph', 'c': [{'t': 'Str', 'c': credit}]}]})
            if item['id'] not in self.prepared:
                continue
            part = deepcopy(self.prepared[item['id']])
            part['blocks'], answer_blocks, answer_label = separate_answers(part['blocks'], item['id'])
            if answer_blocks:
                answer_sections.append((item, paragraph_number, answer_blocks, answer_label))
            if self.profile_name == 'belarus-textbook':
                part = layout_part(part, item['id'], item['_folder'], overrides)
            ast = part
            headings = [node for node in walk(part['blocks']) if node.get('t') == 'Header']
            minimum = min((node['c'][0] for node in headings), default=1)
            for node in walk(part['blocks'] + answer_blocks):
                if node.get('t') in {'Div', 'Span', 'CodeBlock', 'Table', 'Figure', 'Image', 'Link'} and node['c'][0][0]:
                    node['c'][0][0] = namespace(item['id']) + '--' + node['c'][0][0]
                if node.get('t') == 'Header':
                    node['c'][0] = min(6, node['c'][0] - minimum + level + 1)
                    if node['c'][0] == 2:
                        node['c'][1][1].append('handbook-context-section')
                    elif level == 0 and node is headings[0] and node['c'][0] == 1:
                        node['c'][1][1].append('handbook-context-chapter')
                    node['c'][1][0] = namespace(item['id']) + '--' + node['c'][1][0]
                elif node.get('t') == 'Image':
                    path = self.image_path(item, node['c'][2][0])
                    node['c'][2][0] = self.images[path]
                elif node.get('t') == 'Link':
                    href = node['c'][2][0]
                    parsed = urlsplit(href)
                    if parsed.scheme or parsed.netloc:
                        continue
                    target = (item['_folder'] / unquote(parsed.path)).resolve() if parsed.path else item['_folder'].resolve()
                    if not target.is_relative_to((self.root / 'handbooks').resolve()):
                        raise ValueError(f"{item['id']}: ссылка вне handbooks: {href}")
                    destination = paths.get(target)
                    if destination and destination['id'] in included and not parsed.query:
                        anchor = namespace(destination['id'])
                        if parsed.fragment:
                            anchor += '--' + unquote(parsed.fragment)
                        node['c'][2][0] = '#' + anchor
                    else:
                        if destination:
                            route = 'handbooks/' + destination['id'] + '/'
                        else:
                            owners = [owner for owner in all_items.values()
                                      if target.is_relative_to(owner['_folder'].resolve())]
                            if owners:
                                owner = max(owners, key=lambda owner: len(owner['_folder'].parts))
                                relative = target.relative_to(owner['_folder'].resolve()).as_posix()
                                route = 'handbooks/' + owner['id'] + '/' + relative
                            else:
                                route = target.relative_to(self.root).as_posix()
                        node['c'][2][0] = urljoin(self.site_url, quote(route, safe='/'))
                        if parsed.query:
                            node['c'][2][0] += '?' + parsed.query
                        if parsed.fragment:
                            node['c'][2][0] += '#' + parsed.fragment
            if level == 0:
                blocks.append({'t': 'Div', 'c': [[namespace(item['id']), [], []], part['blocks']]})
            else:
                blocks.extend(part['blocks'])
            if chapter and level == 1:
                book = all_items[item['id'].split('/')[0]]
                contributors = contributors_markdown(book.get('_contributors', []))
                if contributors:
                    blocks.append({'t': 'Header', 'c': [2, ['chapter-contributors', [], []],
                                   [{'t': 'Str', 'c': 'Авторы и участники'}]]})
                    credits = printable(json.loads(run(['pandoc', '--from=markdown', '--to=json'],
                                                       input=contributors)))
                    blocks.extend(credits['blocks'])
        if chapter:
            conclusion = task['item']['_folder'] / 'conclusion.md'
            if conclusion.is_file():
                blocks.append({'t': 'RawBlock', 'c': ['latex', '\\clearpage']})
                blocks.append({'t': 'Header', 'c': [1, ['chapter-conclusion', ['handbook-context-chapter'], []],
                               [{'t': 'Str', 'c': 'Заключение'}]]})
                closing = printable(json.loads(run(['pandoc', '--from=markdown+raw_tex+raw_html', '--to=json'],
                                                   input=conclusion.read_text(encoding='utf-8'))))
                blocks.extend(closing['blocks'])
        flush_answers()
        if ast is None:
            raise ValueError(f"{task['item']['id']}: нет текста")
        ast['blocks'] = blocks
        ast['meta'] = {'title': {'t': 'MetaString', 'c': task['item']['title']},
                       'lang': {'t': 'MetaString', 'c': 'ru-RU'}}
        ast['meta']['handbook-level'] = {'t': 'MetaString', 'c':
            ('book', 'chapter', 'paragraph')[len(task['item']['id'].split('/')) - 1]}
        if ast['meta']['handbook-level']['c'] == 'book':
            ast['meta']['include-before'] = {'t': 'MetaBlocks', 'c': self.book_frontmatter(task['item'])}
            revision, date = self.revision
            details = [{'t': 'Str', 'c': 'Редакция: ' + revision}]
            if date:
                details.extend([{'t': 'LineBreak'}, {'t': 'Str', 'c': 'Дата исходников: ' + date}])
            details.extend([
                {'t': 'LineBreak'},
                {'t': 'Link', 'c': [['', [], []], [{'t': 'Str', 'c': 'materials.beloai.by'}], [self.site_url, '']]},
                {'t': 'LineBreak'},
                {'t': 'Link', 'c': [['', [], []], [{'t': 'Str', 'c': 'CC BY 4.0'}],
                                   ['https://creativecommons.org/licenses/by/4.0/', '']]},
            ])
            ast['meta']['date'] = {'t': 'MetaInlines', 'c': details}
            if self.profile_name == 'belarus-textbook':
                data = task['publication']
                # Publication pages are structured AST blocks. Keep the title
                # itself free of Pandoc's subtitle/date composition, including
                # in the running title and PDF metadata.
                ast['meta']['date'] = {'t': 'MetaString', 'c': ''}
                ast['meta']['include-before']['c'] = frontmatter(data, task['item']['title']) + ast['meta']['include-before']['c']
                ast['meta']['include-after'] = {'t': 'MetaBlocks', 'c': endmatter(
                    data, task['item']['title'], self.revision, self.site_url)}
                ast = editorial_layout(ast)
        return ast

    def compile(self, task, ast, output):
        style = self.root / 'utils/pdf'
        key = digest(ast, self.env, self.code, self.profile_name, self.profile, self.logo,
                     task.get('publication'), file_hash(Path(__file__).with_name('handbook_publication.py')))
        cache = Cache('handbook-pdf', key)
        destination = output / task['filename']
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.handbook-', dir=destination.parent) as temp:
            folder = Path(temp)
            pdf = folder / 'document.pdf'
            hit = cache.restore(folder) and pdf.is_file()
            if not hit:
                source = folder / 'document.json'
                source.write_text(json.dumps(ast, ensure_ascii=False), encoding='utf-8')
                header_path = folder / 'document-header.tex'
                header_name = 'pdf-header.tex' if self.profile_name == 'reader' else 'belarus-textbook-header.tex'
                header_path.write_text((style / header_name).read_text(encoding='utf-8') +
                                       ('\n\\handbookwholebooktrue\n' if self.profile_name == 'reader' and ast['meta']['handbook-level']['c'] == 'book' else ''),
                                       encoding='utf-8')
                tex_env = os.environ.copy()
                tex_env['TEXINPUTS'] = str(self.root / 'utils/latex/tex/latex') + '//' + os.pathsep + tex_env.get('TEXINPUTS', '')
                layout = (['-V', 'papersize:a4', '-V', 'fontsize:10pt'] if self.profile_name == 'reader'
                          else ['-V', 'fontsize:12pt', '-V', 'classoption:twoside', '-V', 'indent:true'])
                run(['pandoc', str(source), '--from=json', '--pdf-engine=pdflatex',
                     '--lua-filter', str(style / 'keep-short-code.lua'),
                     '--include-in-header', str(header_path),
                     '--table-of-contents', '--toc-depth=2',
                     *layout,
                     '-V', 'fontenc:T2A', '-V', 'fontfamily:handbookfonts',
                     '--output', str(pdf)], cwd=self.scratch, env=tex_env)
            info = run(['pdfinfo', str(pdf)])
            if not re.search(r'Pages:\s*[1-9]\d*', info) or re.search(r'Encrypted:\s*yes', info):
                raise ValueError(f'Неверный PDF: {pdf}')
            if not hit:
                cache.save(folder, [pdf])
            os.replace(pdf, destination)
        print(f"PDF {task['item']['id']}: {destination}", flush=True)
        return hit


def build(root=REPO_ROOT, *, selected=None, output=None, output_dir=None, jobs=2, site_url=DEFAULT_SITE, book_only=False,
          profile='reader', press_ready=False):
    start = time.monotonic()
    root = root.resolve()
    if press_ready and (profile != 'belarus-textbook' or not book_only):
        raise ValueError('--press-ready требует --profile belarus-textbook --book-only')
    if profile not in PROFILES:
        raise ValueError(f'Неизвестный PDF-профиль: {profile}')
    if profile == 'belarus-textbook' and not book_only:
        raise ValueError('Профиль belarus-textbook поддерживает только полные книги: укажите --book-only')
    catalog = load_catalog(root)
    tasks = documents(catalog)
    all_items = {item['id']: item for item in [
        *catalog['handbooks'], *catalog['_chapters'].values(), *catalog['_lessons'].values()
    ]}
    scope = ''
    if selected:
        selected = selected.resolve()
        matches = [item for item in [*all_items.values(), *catalog['_excluded']] if item['_folder'].resolve() == selected]
        if not matches:
            raise ValueError(f'Путь не входит в каталог учебников: {selected}')
        scope = matches[0]['id']
        tasks = [task for task in tasks if task['item']['id'] == scope or task['item']['id'].startswith(scope + '/')]
    if book_only:
        books = {book['id'] for book in catalog['handbooks']}
        if selected and scope not in books:
            raise ValueError('--book-only требует путь учебника или --all')
        tasks = [task for task in tasks if task['item']['id'] in books]
    if output and len(tasks) != 1:
        raise ValueError('--output требует ровно один документ; используйте --output-dir для поддерева')
    # Validate before cleanup or expensive preparation, without changing the site catalog.
    if profile == 'belarus-textbook':
        for task in tasks:
            task['publication'] = read_publication(task['item']['_folder'])
    if press_ready:
        from handbook_press import export_press, teaching_hashes
        frozen = teaching_hashes(root)
        for task in tasks:
            name = f'beloai-{task["item"]["id"]}-handbook-press.pdf'
            destination = output.resolve() if output else (output_dir or root / 'output/press').resolve() / task['item']['id'] / name
            with tempfile.TemporaryDirectory(prefix='handbook-proof-') as temp:
                proof = Path(temp) / 'proof.pdf'
                build(root, selected=task['item']['_folder'], output=proof, jobs=jobs,
                      site_url=site_url, book_only=True, profile=profile)
                export_press(root, proof, destination, frozen)
        return
    default_output = root / 'output/pdf'
    if profile != 'reader':
        default_output /= profile
    output_dir = (output_dir or default_output).resolve()
    expected = {task['filename'] for task in tasks}
    cleanup = output_dir / scope
    if not output and cleanup.exists():
        for path in cleanup.rglob('*.pdf'):
            if profile == 'reader' and not scope and path.is_relative_to(output_dir / 'belarus-textbook'):
                continue
            if (path.name in ({'handbook.pdf'} if book_only else {'handbook.pdf', 'chapter.pdf', 'paragraph.pdf'})
                    and path.relative_to(output_dir).as_posix() not in expected):
                path.unlink()
    if not tasks:
        print('Нет материалов для PDF-сборки.')
        return
    tools, env = environment()
    with tempfile.TemporaryDirectory(prefix='handbook-pdf-') as temp:
        builder = Builder(root, Path(temp), site_url, tools, env, profile)
        sources = {item['id']: item for task in tasks for item, _ in task['parts'] if '_content' in item}
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            source_groups = {}
            for item in sources.values():
                source_groups.setdefault(file_hash(item['_content']), []).append(item)
            for identifier, ast, hit in executor.map(builder.prepare, [group[0] for group in source_groups.values()]):
                for same in source_groups[file_hash(sources[identifier]['_content'])]:
                    builder.prepared[same['id']] = ast
                builder.hits += hit
            images = {builder.image_path(sources[identifier], node['c'][2][0])
                      for identifier, ast in builder.prepared.items() for node in walk(ast)
                      if node.get('t') == 'Image'}
            if any(path.suffix.lower() == '.svg' for path in images):
                builder.svg_identity = renderer_identity()
            # Одинаковое содержимое конвертируется один раз, даже по разным путям.
            groups = {}
            for path in sorted(images):
                groups.setdefault((file_hash(path), path.suffix.lower()), []).append(path)
            for path, rendered, hit, converted in executor.map(builder.image, [paths[0] for paths in groups.values()]):
                for same in groups[(file_hash(path), path.suffix.lower())]:
                    builder.images[same] = rendered
                builder.hits += hit
                builder.image_conversions += converted
            work = [(task, builder.compose(task, all_items)) for task in tasks]
            if output:
                output = output.resolve()
                task, ast = work[0]
                task = dict(task, filename=output.name)
                results = [builder.compile(task, ast, output.parent)]
            else:
                results = list(executor.map(lambda pair: builder.compile(*pair, output_dir), work))
            builder.hits += sum(results)
            builder.compilations = len(results) - sum(results)
        print(f'PDF: {len(tasks)}; CACHE HIT: {builder.hits}; компиляций: {builder.compilations}; '
              f'SVG: {builder.image_conversions}; время: {time.monotonic() - start:.1f} с')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('article', nargs='?', type=Path, help='Папка учебника, главы или параграфа')
    parser.add_argument('--all', action='store_true', help='Все учебники из каталога')
    parser.add_argument('--book-only', action='store_true', help='Только полные книги, без глав и параграфов')
    parser.add_argument('--profile', choices=PROFILES, default='reader', help='Оформление PDF (по умолчанию reader)')
    parser.add_argument('--press-ready', action='store_true', help='Отдельный печатный пакет (только belarus-textbook --book-only)')
    parser.add_argument('--output', type=Path, help='Путь одного PDF')
    parser.add_argument('--output-dir', type=Path, help='Корень результатов (по умолчанию output/pdf)')
    parser.add_argument('--jobs', type=int, default=2, help='Число параллельных задач (по умолчанию 2)')
    parser.add_argument('--site-url', default=DEFAULT_SITE, help='Корень опубликованного сайта, включая /dev/ при необходимости')
    args = parser.parse_args()
    if bool(args.article) == args.all or args.jobs < 1:
        parser.error('Укажите путь или --all; --jobs должен быть положительным')
    if args.output and args.output_dir:
        parser.error('--output и --output-dir несовместимы')
    if urlsplit(args.site_url).scheme not in {'http', 'https'} or not args.site_url.endswith('/'):
        parser.error('--site-url должен быть HTTP(S)-адресом с завершающим /')
    try:
        build(selected=args.article, output=args.output, output_dir=args.output_dir,
              jobs=args.jobs, site_url=args.site_url, book_only=args.book_only, profile=args.profile, press_ready=args.press_ready)
    except (ValueError, OSError, importlib.metadata.PackageNotFoundError) as error:
        parser.exit(1, f'Ошибка PDF-сборки: {error}\n')
