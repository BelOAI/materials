"""ML-хендбук: локальные метаданные, стабильные URL и общая оболочка сайта."""
from __future__ import annotations
import json
import posixpath
import re
import shutil
import subprocess
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from course_site import link, write_page
from authorship import authors_html
from handbook_redirects import publish_legacy_handbook, write_redirect
from notebook_export import export_notebook
from handbook_catalog import load_catalog, local_file

REDIRECTS = {'start': 'intro', 'environment': 'intro', 'diy-nn': 'nn-in-practice',
             'how-they-learn': 'how-nns-learn', 'advanced-math': 'math-of-ai'}


def load_handbook(source: Path, *, allow_missing_synced=False) -> dict:
    """Совместимый адаптер текущего ML-сайта к общему каталогу."""
    book = load_catalog(source, allow_missing_synced=allow_missing_synced)
    if len(book['handbooks']) != 1 or book['handbooks'][0]['slug'] != 'ml':
        raise ValueError('Ожидается ML-хендбук')
    handbook = book['handbooks'][0]
    handbook['_content'] = local_file(source / 'handbooks/ml', 'content.md')
    sections = handbook['sections']
    if any(section['slug'] in REDIRECTS for section in sections):
        raise ValueError('Зарезервированный slug главы')
    if not sections or sections[0]['slug'] != 'intro' or '_content' not in sections[0]:
        raise ValueError('Первой главой должно быть опубликованное введение intro')
    handbook['introduction'] = 'ml/intro'
    book['_pages'] = []
    folder = source / 'handbooks/ml'
    if (folder / 'CURRICULUM.md').is_file():
        book['_pages'].append(dict(id='ml/curriculum', title='Программа учебника',
                                  _folder=folder, _content=local_file(folder, 'CURRICULUM.md')))
    return book


class PageLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids, self.urls = set(), []
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            if attrs['id'] in self.ids:
                raise ValueError(f'Повтор якоря: {attrs["id"]}')
            self.ids.add(attrs['id'])
        for key in ('href', 'src'):
            if attrs.get(key):
                self.urls.append(attrs[key])


def validate_links(output: Path) -> None:
    pages = {p.resolve(): PageLinks(p.read_text(encoding='utf-8')) for p in (output / 'handbooks').rglob('index.html')}
    for page, parsed in pages.items():
        for href in parsed.urls:
            url = urlsplit(href)
            if url.scheme in ('http', 'https', 'mailto', 'data') or url.netloc:
                continue
            if url.scheme or url.path.startswith('/'):
                raise ValueError(f'Ссылка не поддерживает префикс сайта: {href}')
            target = (page.parent / unquote(url.path)).resolve() if url.path else page
            if target.is_dir():
                target /= 'index.html'
            if not target.is_relative_to(output.resolve()) or not target.is_file():
                raise ValueError(f'{page.relative_to(output.resolve())}: недоступная ссылка {href}')
            if url.fragment and target.suffix == '.html':
                anchors = pages.get(target) or PageLinks(target.read_text(encoding='utf-8'))
                if unquote(url.fragment) not in anchors.ids:
                    raise ValueError(f'Отсутствует якорь: {href}')


def source_links(html, item, items, source):
    routes = {entry['_content'].resolve(): entry['id'] for entry in items if '_content' in entry}
    routes.update({(entry['_folder'] / 'README.md').resolve(): entry['id'] for entry in items})
    routes[(source / 'handbooks/ml/README.md').resolve()] = 'ml'
    def replace(match):
        url = urlsplit(unescape(match[3]))
        if not url.path or url.scheme or url.netloc or url.path.startswith('/'):
            return match[0]
        candidate = (item['_folder'] / unquote(url.path)).resolve()
        if candidate.is_dir():
            candidate /= 'index.md' if (candidate / 'index.md').is_file() else 'README.md'
        if candidate not in routes:
            return match[0]
        target = posixpath.relpath(routes[candidate], item['id']) + '/'
        return match[1] + '=' + match[2] + escape(urlunsplit(('', '', target, url.query, url.fragment)), quote=True) + match[2]
    return re.sub(r"\b(href|src)=([\"'])(.*?)\2", replace, html)


def publish_handbook(source: Path, output: Path, weeks: list) -> None:
    book = load_handbook(source)
    handbook = book['handbooks'][0]
    sections = handbook['sections']
    items = [handbook, *book['_pages'], *sections, *book['_lessons'].values()]
    texts = [item for item in items if '_content' in item]
    result = subprocess.run(['node', str(source / 'utils/site/render-handbook.mjs')], input=json.dumps([
        {'name': item['id'], 'source': item['_content'].read_text(encoding='utf-8')} for item in texts
    ]), text=True, capture_output=True, check=True)
    rendered = dict(zip((item['id'] for item in texts), json.loads(result.stdout)))
    shutil.rmtree(output / 'handbooks', ignore_errors=True)
    katex = source / 'utils/site/node_modules/katex'
    shutil.copytree(katex / 'dist/fonts', output / 'assets/katex/fonts', dirs_exist_ok=True)
    shutil.copyfile(katex / 'dist/katex.min.css', output / 'assets/katex/katex.min.css')
    shutil.copyfile(katex / 'LICENSE', output / 'assets/katex/LICENSE')

    def title(section):
        return f'{sections.index(section)}. {section["title"]}'

    def navlink(identifier, text, current):
        active = ' aria-current="page"' if identifier == current else ''
        href = '../' * len(Path('handbooks/' + current).parts) + 'handbooks/' + (identifier + '/' if identifier else '')
        return ('<a href="' + escape(href, quote=True) + '"' + active
                + ' data-nav-label="' + escape(text, quote=True) + '"><span class="nav-label">'
                + escape(text) + '</span></a>')

    def page(identifier, heading, description, content):
        path = 'handbooks' + ('/' + identifier if identifier else '')
        root = '../' * len(Path(path).parts)
        top = '<div class="handbook-links"><ul><li>' + link(root, '← На основной сайт') + '</li><li>' + navlink('', 'Учебники', identifier) + '</li></ul></div>'
        nav = '<div class="handbook-tree"><ul><li>' + navlink('ml', handbook['title'], identifier) + '</li></ul>'
        if book['_pages']:
            nav += '<ul>' + ''.join('<li>' + navlink(item['id'], item['title'], identifier) + '</li>'
                                    for item in book['_pages']) + '</ul>'
        if identifier.startswith('ml'):
            nav += '<section class="handbook-track" aria-label="Оглавление ML">'
            for section in sections:
                opened = ' open' if identifier == section['id'] or identifier.startswith(section['id'] + '/') else ''
                nav += '<details class="handbook-chapter"' + opened + '><summary><span class="chapter-title">' + escape(title(section)) + '</span></summary><ul><li>' + navlink(section['id'], 'Обзор раздела', identifier) + '</li>'
                for para_id in section['lessons']:
                    item = book['_lessons'][para_id]
                    nav += '<li>' + (navlink(para_id, item['title'], identifier) if item['status'] != 'planned' else escape(item['title']) + ' (ещё нет текста)') + '</li>'
                nav += '</ul></details>'
            nav += '</section>'
        nav += '</div>'
        body = content if re.search(r'<h1\b', content) else '<h1>' + escape(heading) + '</h1>' + content
        note = '<p class="draft-note"><span class="draft-badge">Черновик</span><span>Материалы дорабатываются и будут дополняться.</span></p>'
        body = re.sub(r'(</h1>)', lambda match: match[0] + note, body, count=1)
        write_page(source, output, weeks, path, heading, description,
                   '<div class="handbook-content">' + body + '</div>', 'handbook', root,
                   navigation_override=nav, navigation_top=top, brand_href=root + 'handbooks/ml/',
                   navigation_label='Оглавление учебника')
        dest = output / path / 'index.html'
        html = dest.read_text(encoding='utf-8').replace('</head>', f'<link rel="stylesheet" href="{root}assets/katex/katex.min.css" />\n<meta name="robots" content="noindex, nofollow" />\n</head>')
        dest.write_text(html, encoding='utf-8')

    def publish_files(item):
        folder = item['_folder']
        destination = output / 'handbooks' / item['id']
        # Изображения и данные публикуются вместе с параграфом; служебные файлы исключены.
        for directory in ('media', 'data'):
            resource_root = folder / directory
            if resource_root.is_dir():
                for path in resource_root.rglob('*'):
                    relative = path.relative_to(folder)
                    if path.is_file() and not any(p.startswith(('_', '.')) for p in relative.parts):
                        src = local_file(folder, relative.as_posix())
                        target = destination / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, target)
        content = ''
        for resource in item.get('resources', []):
            src = local_file(folder, resource['path'])
            target = destination / resource['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
            content += '<li>' + link(resource['path'], resource['label'], ' download')
            if target.suffix == '.ipynb':
                # Превью зависит также от текста, YAML, ресурсов и общего экспортера.
                dependencies = [item['_content'], folder / 'meta.yaml', folder.parent / 'meta.yaml',
                                source / 'handbooks/handbooks.json', source / 'utils/site/render-handbook.mjs',
                                source / 'utils/site/src/site.css', Path(__file__),
                                Path(__file__).with_name('handbook_catalog.py')]
                dependencies += [p for d in ('media', 'data') for p in (folder / d).rglob('*') if p.is_file() and not any(part.startswith(('_', '.')) for part in p.relative_to(folder).parts)]
                if export_notebook(target, dependencies=dependencies):
                    content += ' · ' + link(str(Path(resource['path']).with_suffix('.html')), 'Открыть в браузере')
            content += '</li>'
        content = '<h2>Файлы</h2><ul>' + content + '</ul>' if content else ''
        if item.get('references'):
            content += '<h2>Дополнительные материалы</h2><ul>' + ''.join(
                '<li>' + link(ref['url'], ref['label']) + '</li>' for ref in item['references']) + '</ul>'
        return content

    for item in texts:
        publish_files_html = publish_files(item)
        item['_html'] = source_links(rendered[item['id']]['html'], item, items, source) + publish_files_html
    page('', book['title'], book['description'], '<p>' + escape(book['description']) + '</p><ul><li>' + link('ml/', handbook['title']) + '</li></ul>')
    overview = handbook['_html']
    route = ['ml/intro'] + [p['id'] for p in book['_lessons'].values() if p['status'] != 'planned']
    by_id = {item['id']: item for item in texts}
    for section in sections:
        overview += '<h2>' + link(section['slug'] + '/', title(section)) + '</h2><p>' + escape(section['description']) + '</p>'
        content = '<p>' + escape(section['description']) + '</p>'
        if section['status'] == 'planned':
            note = '<p class="section-planned">Раздел запланирован. Учебные материалы ещё не опубликованы.</p>'
            overview += note
            content += note
        else:
            content += authors_html(section['authors']) + section.get('_html', '')
            if section['lessons']:
                content += '<ol>'
                for para_id in section['lessons']:
                    paragraph = book['_lessons'][para_id]
                    content += '<li>' + (link(paragraph['slug'] + '/', paragraph['title']) if paragraph['status'] != 'planned' else escape(paragraph['title']) + ' (ещё нет текста)') + '</li>'
                content += '</ol>'
        if section['id'] == 'ml/intro':
            content += pagination(section['id'], route, by_id)
        page(section['id'], title(section), section['description'], content)
    page('ml', handbook['title'], handbook['description'], overview)
    for item in book['_pages']:
        page(item['id'], item['title'], item['title'], item['_html'])
    for item in book['_lessons'].values():
        if item['status'] == 'planned':
            continue
        content = authors_html(item['authors'])
        content += '<nav class="lesson-toc" aria-label="Оглавление параграфа"><ul>' + ''.join('<li>' + link('#' + h['id'], h['text']) + '</li>' for h in rendered[item['id']]['toc'] if h['level'] == 2) + '</ul></nav>'
        content += item['_html'] + pagination(item['id'], route, by_id)
        page(item['id'], item['title'], item['description'], content)
    write_redirect(output / 'handbooks/start/index.html', '../ml/intro/')
    for old, new in REDIRECTS.items():
        write_redirect(output / 'handbooks/ml' / old / 'index.html', '../' + new + '/')
    for path in (output / 'handbooks').rglob('*.html'):
        html = path.read_text(encoding='utf-8')
        if 'name="robots"' not in html:
            path.write_text(html.replace('</head>', '<meta name="robots" content="noindex, nofollow" /></head>', 1), encoding='utf-8')
    validate_links(output)
    publish_legacy_handbook(output)


def pagination(identifier, route, items):
    if identifier not in route or len(route) == 1:
        return ''
    index = route.index(identifier)
    root = '../' * (len(identifier.split('/')) + 1)
    links = ''
    for offset, label, rel in [(-1, '← ', 'prev'), (1, 'Далее: ', 'next')]:
        if 0 <= index + offset < len(route):
            target = route[index + offset]
            links += link(root + 'handbooks/' + target + '/', label + items[target]['title'], f' rel="{rel}"')
    return '<nav class="week-pagination" aria-label="Переходы между параграфами">' + links + '</nav>'
