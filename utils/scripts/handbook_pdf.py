"""Инкрементальная PDF-сборка параграфов, глав и учебников."""
from __future__ import annotations

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

from authorship import authors_text
from build_cache import Cache
from handbook_catalog import load_catalog
from handbook_svg import renderer_identity, render_svg
from repo_paths import REPO_ROOT

FONTS = ('Liberation Serif', 'DejaVu Sans Mono')
DEFAULT_SITE = 'https://beloai.github.io/materials/'


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
    tools = {name: tool_identity(name) for name in ('pandoc', 'xelatex', 'pdfinfo')}
    fonts = []
    for family in FONTS:
        for style in ('Regular', 'Bold', 'Italic', 'Bold Italic'):
            match = run(['fc-match', '-f', '%{family}|%{file}', f'{family}:style={style}'])
            actual, filename = match.split('|', 1)
            if family not in actual.split(','):
                raise ValueError(f'Не установлен шрифт {family}; найден {actual}')
            fonts.append(file_hash(filename))
    # Формат XeLaTeX и реестр пакетов меняются независимо от бинарника движка.
    tex = []
    for name in ('xelatex.fmt', 'texlive.tlpdb'):
        path = ''
        if name == 'xelatex.fmt':
            result = subprocess.run(['kpsewhich', '-engine=xetex', name], text=True, capture_output=True)
            path = result.stdout.strip()
        if not path and name == 'texlive.tlpdb':
            root = run(['kpsewhich', '-var-value=TEXMFROOT']).strip()
            path = str(Path(root) / 'tlpkg/texlive.tlpdb')
        if path and Path(path).is_file():
            tex.append(file_hash(path))
    return tools, digest(tools, fonts, tex, os.environ.get('BUILD_ENV_ID', ''))


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


def namespace(identifier):
    return identifier.replace('/', '--')


def header(level, item):
    return {'t': 'Header', 'c': [level, [namespace(item['id']), [], []], [{'t': 'Str', 'c': item['title']}]]}


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
    def __init__(self, root, scratch, site_url, tools, env):
        self.root, self.scratch, self.site_url = root, scratch, site_url
        self.code = digest(file_hash(__file__), file_hash(Path(__file__).with_name('handbook_catalog.py')),
                           file_hash(Path(__file__).with_name('authorship.py')),
                           file_hash(Path(__file__).with_name('handbook_svg.py')))
        self.tools, self.env = tools, env
        self.svg_identity = None
        self.prepared, self.images = {}, {}
        self.compilations = 0
        self.image_conversions = 0
        self.hits = 0

    def prepare(self, item):
        source = item['_content'].read_text(encoding='utf-8')
        key = digest(source, self.tools['pandoc'], self.code)
        cache = Cache('handbook-source', key)
        folder = self.scratch / 'sources' / namespace(item['id'])
        folder.mkdir(parents=True)
        path = folder / 'source.json'
        hit = cache.restore(folder) and path.is_file()
        if not hit:
            ast = printable(json.loads(run(['pandoc', '--from=markdown+raw_tex+raw_html', '--to=json'], input=source)))
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
        key = digest(file_hash(path), 'svg' if svg else path.suffix.lower(),
                     [self.svg_identity, self.env] if svg else '', self.code)
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
        for item, level in task['parts']:
            level = 1 if paragraph else level
            if level:
                blocks.append(header(level, item))
            credit = authors_text(item.get('authors', []))
            if credit:
                blocks.append({'t': 'Para', 'c': [{'t': 'Emph', 'c': [{'t': 'Str', 'c': credit}]}]})
            if item['id'] not in self.prepared:
                continue
            part = deepcopy(self.prepared[item['id']])
            ast = part
            headings = [node for node in walk(part['blocks']) if node.get('t') == 'Header']
            minimum = min((node['c'][0] for node in headings), default=1)
            for node in walk(part['blocks']):
                if node.get('t') in {'Div', 'Span', 'CodeBlock', 'Table', 'Figure', 'Image', 'Link'} and node['c'][0][0]:
                    node['c'][0][0] = namespace(item['id']) + '--' + node['c'][0][0]
                if node.get('t') == 'Header':
                    node['c'][0] = min(6, node['c'][0] - minimum + level + 1)
                    node['c'][1][0] = namespace(item['id']) + '--' + node['c'][1][0]
                elif node.get('t') == 'Image':
                    path = self.image_path(item, node['c'][2][0])
                    node['c'][2][0] = self.images[path]
                    attrs = node['c'][0][2]
                    if not any(name == 'width' for name, _ in attrs):
                        attrs.append(['width', '85%'])
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
        if ast is None:
            raise ValueError(f"{task['item']['id']}: нет текста")
        ast['blocks'] = blocks
        ast['meta'] = {'title': {'t': 'MetaString', 'c': task['item']['title']},
                       'lang': {'t': 'MetaString', 'c': 'ru-RU'}}
        return ast

    def compile(self, task, ast, output):
        style = self.root / 'utils/pdf'
        key = digest(ast, self.env, self.code,
                     [(p.name, file_hash(p)) for p in sorted(style.iterdir()) if p.suffix in {'.tex', '.lua'}])
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
                run(['pandoc', str(source), '--from=json', '--pdf-engine=xelatex',
                     '--lua-filter', str(style / 'keep-short-code.lua'),
                     '--include-in-header', str(style / 'pdf-header.tex'),
                     '--table-of-contents', '--toc-depth=2',
                     '-V', 'papersize:a4', '-V', 'geometry:margin=18mm', '-V', 'fontsize:10pt',
                     '-V', 'mainfont:' + FONTS[0], '-V', 'monofont:' + FONTS[1],
                     '--output', str(pdf)], cwd=self.scratch)
            info = run(['pdfinfo', str(pdf)])
            if not re.search(r'Pages:\s*[1-9]\d*', info) or re.search(r'Encrypted:\s*yes', info):
                raise ValueError(f'Неверный PDF: {pdf}')
            if not hit:
                cache.save(folder, [pdf])
            os.replace(pdf, destination)
        print(f"PDF {task['item']['id']}: {destination}", flush=True)
        return hit


def build(root=REPO_ROOT, *, selected=None, output=None, output_dir=None, jobs=2, site_url=DEFAULT_SITE):
    start = time.monotonic()
    root = root.resolve()
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
    if output and len(tasks) != 1:
        raise ValueError('--output требует ровно один документ; используйте --output-dir для поддерева')
    output_dir = (output_dir or root / 'output/pdf').resolve()
    expected = {task['filename'] for task in tasks}
    cleanup = output_dir / scope
    if not output and cleanup.exists():
        for path in cleanup.rglob('*.pdf'):
            if path.name in {'handbook.pdf', 'chapter.pdf', 'paragraph.pdf'} and path.relative_to(output_dir).as_posix() not in expected:
                path.unlink()
    if not tasks:
        print('Нет материалов для PDF-сборки.')
        return
    tools, env = environment()
    with tempfile.TemporaryDirectory(prefix='handbook-pdf-') as temp:
        builder = Builder(root, Path(temp), site_url, tools, env)
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
              jobs=args.jobs, site_url=args.site_url)
    except (ValueError, OSError, importlib.metadata.PackageNotFoundError) as error:
        parser.exit(1, f'Ошибка PDF-сборки: {error}\n')
