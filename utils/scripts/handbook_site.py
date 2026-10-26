"""Каталог учебников, стабильные URL и общая оболочка сайта."""
from __future__ import annotations
import json
import posixpath
import re
import shutil
import subprocess
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from course_site import link, write_page
from authorship import authors_html, expand_authors, expand_contributors
from handbook_redirects import publish_legacy_handbook, write_redirect
from notebook_export import export_notebook
from handbook_notebooks import notebook_authors
from handbook_catalog import load_catalog, local_file

REDIRECTS = {'start': 'intro', 'environment': 'intro', 'diy-nn': 'nn-in-practice',
             'how-they-learn': 'how-nns-learn', 'advanced-math': 'math-of-ai'}


def load_handbook(source: Path, *, allow_missing_synced=False) -> dict:
    """Подготовить каталог и дополнительные страницы каждого учебника."""
    book = load_catalog(source, allow_missing_synced=allow_missing_synced)
    book['handbooks'] = [h for h in book['handbooks']
                         if h.get('build') is not False and h.get('status') != 'planned']
    book['_pages'] = []
    for handbook in book['handbooks']:
        sections = handbook['sections']
        if handbook['slug'] == 'ml':
            handbook['_content'] = local_file(handbook['_folder'], 'content.md')
            if any(section['slug'] in REDIRECTS for section in sections):
                raise ValueError('Зарезервированный slug главы')
            if not sections or sections[0]['slug'] != 'intro' or '_content' not in sections[0]:
                raise ValueError('Первой главой должно быть опубликованное введение intro')
        handbook['_pages'] = []
        folder = handbook['_folder']
        if (folder / 'CURRICULUM.md').is_file():
            if any(section['slug'] == 'curriculum' for section in sections):
                raise ValueError('Зарезервированный slug главы: curriculum')
            handbook['_pages'].append(dict(id=handbook['id'] + '/curriculum', title='Программа учебника',
                                          _content_authors=handbook['_text_authors'].get('curriculum', []),
                                          _folder=folder, _content=local_file(folder, 'CURRICULUM.md')))
        book['_pages'].extend(handbook['_pages'])
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
    # Дополнительные страницы делят папку с учебником, но не заменяют его README.
    routes.update({(entry['_folder'] / 'README.md').resolve(): entry['id']
                   for entry in items if 'sections' in entry})
    resources = {}
    for entry in items:
        if '_content' not in entry:
            continue
        folder = entry['_folder']
        paths = {Path(resource['path']) for resource in entry.get('resources', [])}
        # Индекс файлов совпадает с правилами публикации publish_files.
        paths.update(path.relative_to(folder)
                     for directory in ('media', 'data')
                     for path in (folder / directory).rglob('*')
                     if path.is_file() and not any(part.startswith(('_', '.'))
                                                  for part in path.relative_to(folder).parts))
        for path in paths:
            resources[local_file(folder, path.as_posix())] = posixpath.join(entry['id'], path.as_posix())
    def replace(match):
        url = urlsplit(unescape(match[3]))
        if not url.path or url.scheme or url.netloc or url.path.startswith('/'):
            return match[0]
        candidate = (item['_folder'] / unquote(url.path)).resolve()
        if candidate.is_dir():
            candidate /= 'index.md' if (candidate / 'index.md').is_file() else 'README.md'
        if candidate in routes:
            target = posixpath.relpath(routes[candidate], item['id']) + '/'
        elif candidate in resources:
            target = quote(posixpath.relpath(resources[candidate], item['id']), safe='/')
        else:
            return match[0]
        return match[1] + '=' + match[2] + escape(urlunsplit(('', '', target, url.query, url.fragment)), quote=True) + match[2]
    return re.sub(r"\b(href|src)=([\"'])(.*?)\2", replace, html)


def handbook_contents(handbook: dict, lessons: dict) -> str:
    """Оглавление книги по фактически включённым главам и параграфам."""
    if not handbook['sections']:
        return ''
    html = '<nav class="handbook-toc" aria-label="Содержание учебника"><h2>Содержание</h2><ol class="handbook-chapter-list">'
    for index, section in enumerate(handbook['sections']):
        html += '<li><h3>' + link(section['slug'] + '/', f'Глава {index}. {section["title"]}')
        if section['status'] == 'planned':
            html += ' <span class="section-planned">Готовится</span>'
        html += '</h3>'
        if section['lessons']:
            html += '<ol class="handbook-paragraph-list">'
            for identifier in section['lessons']:
                item = lessons[identifier]
                html += '<li>'
                if item['status'] == 'planned':
                    html += '<span class="chapter-unavailable">' + escape(item['title']) + ' (готовится)</span>'
                else:
                    html += link(section['slug'] + '/' + item['slug'] + '/', item['title'])
                html += '</li>'
            html += '</ol>'
        html += '</li>'
    return html + '</ol></nav>'


def publish_handbook(source: Path, output: Path, weeks: list) -> None:
    book = load_handbook(source)
    handbooks = book['handbooks']
    landing = dict(id='', _folder=source / 'handbooks',
                   _content=local_file(source / 'handbooks', 'README.md'))
    items = [landing, *handbooks, *book['_pages'], *book['_chapters'].values(), *book['_lessons'].values()]
    texts = [item for item in items if '_content' in item]
    result = subprocess.run(['node', str(source / 'utils/site/render-handbook.mjs')], input=json.dumps([
        {'name': item['id'], 'source': expand_contributors(expand_authors(
            item['_content'].read_text(encoding='utf-8'), item.get('_content_authors', item.get('authors')), html=True), item.get('_contributors', []))} for item in texts
    ]), text=True, capture_output=True, check=True)
    rendered = dict(zip((item['id'] for item in texts), json.loads(result.stdout)))
    shutil.rmtree(output / 'handbooks', ignore_errors=True)
    katex = source / 'utils/site/node_modules/katex'
    shutil.copytree(katex / 'dist/fonts', output / 'assets/katex/fonts', dirs_exist_ok=True)
    shutil.copyfile(katex / 'dist/katex.min.css', output / 'assets/katex/katex.min.css')
    shutil.copyfile(katex / 'LICENSE', output / 'assets/katex/LICENSE')

    def title(section):
        handbook = next(h for h in handbooks if section['id'].startswith(h['id'] + '/'))
        return f'{handbook["sections"].index(section)}. {section["title"]}'

    def navlink(identifier, text, current):
        active = ' aria-current="page"' if identifier == current else ''
        href = '../' * len(Path('handbooks/' + current).parts) + 'handbooks/' + (identifier + '/' if identifier else '')
        return ('<a href="' + escape(href, quote=True) + '"' + active
                + ' data-nav-label="' + escape(text, quote=True) + '"><span class="nav-label">'
                + escape(text) + '</span></a>')

    def page(identifier, heading, description, content):
        path = 'handbooks' + ('/' + identifier if identifier else '')
        root = '../' * len(Path(path).parts)
        handbook = next((h for h in handbooks if identifier == h['id']
                         or identifier.startswith(h['id'] + '/')), None)
        top = ''
        breadcrumbs = ''
        if handbook is None:
            nav = '<ul><li>' + navlink('', 'Об учебниках', identifier) + '</li></ul><hr>'
            nav += '<ul class="handbook-list">' + ''.join(
                '<li>' + navlink(h['id'], h['title'], identifier) + '</li>' for h in handbooks) + '</ul>'
        else:
            top = '<div class="handbook-links"><ul><li>' + navlink('', '← Все учебники', identifier) + '</li></ul></div>'
            nav = '<div class="handbook-tree"><ul><li>' + navlink(handbook['id'], handbook['title'], identifier) + '</li></ul><hr>'
            nav += '<ul class="handbook-chapters">'
            for index, section in enumerate(handbook['sections']):
                nav += '<li>' + navlink(section['id'], f'Глава {index}. {section["title"]}', identifier)
                if identifier == section['id'] or identifier.startswith(section['id'] + '/'):
                    nav += '<ul class="handbook-lessons">'
                    for para_id in section['lessons']:
                        item = book['_lessons'][para_id]
                        nav += '<li>' + (navlink(para_id, item['title'], identifier) if item['status'] != 'planned'
                                        else '<span class="chapter-unavailable">' + escape(item['title']) + ' (готовится)</span>') + '</li>'
                    nav += '</ul>'
                nav += '</li>'
            nav += '</ul>'
            if handbook['_pages']:
                nav += '<hr><ul>' + ''.join('<li>' + navlink(item['id'], item['title'], identifier) + '</li>'
                                            for item in handbook['_pages']) + '</ul>'
            nav += '</div>'
            trail = [('', 'Все учебники'), (handbook['id'], handbook['title'])]
            section = next((s for s in handbook['sections'] if identifier == s['id']
                            or identifier.startswith(s['id'] + '/')), None)
            if section:
                trail.append((section['id'], section['title']))
            if trail[-1][0] != identifier:
                trail.append((identifier, heading))
            breadcrumbs = '<nav class="breadcrumbs" aria-label="Путь к странице"><ol>' + ''.join(
                '<li>' + (escape(label) if target == identifier else navlink(target, label, identifier)) + '</li>'
                for target, label in trail) + '</ol></nav>'
        nav += '<hr><ul><li>' + link(root, 'Занятия курса') + '</li><li>' + link(root + 'materials/', 'Все материалы') + '</li>'
        nav += '<li><a href="https://github.com/BelOAI/materials">Исходники на GitHub</a></li></ul>'
        body = content if re.search(r'<h1\b', content) else '<h1>' + escape(heading) + '</h1>' + content
        note = '<p class="draft-note"><span class="draft-badge">Черновик</span><span>Материалы дорабатываются и будут дополняться.</span></p>'
        body = re.sub(r'(</h1>)', lambda match: match[0] + note, body, count=1)
        write_page(source, output, weeks, path, heading, description,
                   '<div class="handbook-content">' + breadcrumbs + body + '</div>', 'handbook' if handbook else 'handbooks', root,
                   navigation_override=nav, navigation_top=top,
                   navigation_label='Оглавление учебника' if handbook else 'Навигация по учебникам')
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
                notebook = notebook_authors(json.loads(src.read_text(encoding='utf-8')), item.get('authors'), include_credit=True)
                target.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
                # Превью зависит также от текста, YAML, ресурсов и общего экспортера.
                dependencies = [item['_content'], folder / 'meta.yaml', folder.parent / 'meta.yaml',
                                source / 'handbooks/handbooks.json', source / 'utils/site/render-handbook.mjs',
                                source / 'utils/site/src/site.css', Path(__file__),
                                Path(__file__).with_name('handbook_catalog.py')]
                dependencies += [Path(__file__).with_name('handbook_notebooks.py'),
                                 Path(__file__).with_name('authorship.py')]
                dependencies += [p for d in ('media', 'data') for p in (folder / d).rglob('*') if p.is_file() and not any(part.startswith(('_', '.')) for part in p.relative_to(folder).parts)]
                if export_notebook(target, dependencies=dependencies):
                    preview = target.with_suffix('.html')
                    notebook_item = item | {
                        '_folder': src.parent,
                        'id': posixpath.normpath(posixpath.join(item['id'], str(Path(resource['path']).parent))),
                    }
                    preview.write_text(source_links(preview.read_text(encoding='utf-8'), notebook_item, items, source),
                                       encoding='utf-8')
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
    page('', book['title'], book['description'], landing['_html'])
    by_id = {item['id']: item for item in texts}
    for handbook in handbooks:
        sections = handbook['sections']
        overview = handbook_contents(handbook, book['_lessons'])
        overview += handbook.get('_html', '')
        lessons = [book['_lessons'][identifier] for section in sections for identifier in section['lessons']]
        route = [s['id'] for s in sections if s['slug'] == 'intro' and '_content' in s]
        route += [p['id'] for p in lessons if p['status'] != 'planned']
        for section in sections:
            content = ''
            if section['status'] == 'planned':
                note = '<p class="section-planned">Раздел запланирован. Учебные материалы ещё не опубликованы.</p>'
                content += note
            else:
                content += authors_html(section['authors']) + section.get('_html', '')
                if section['lessons']:
                    content += '<h2>Содержание</h2><ol>'
                    for para_id in section['lessons']:
                        paragraph = book['_lessons'][para_id]
                        content += '<li>' + (link(paragraph['slug'] + '/', paragraph['title']) if paragraph['status'] != 'planned' else escape(paragraph['title']) + ' (ещё нет текста)') + '</li>'
                    content += '</ol>'
            if section['id'] in route:
                content += pagination(section['id'], route, by_id)
            page(section['id'], title(section), section['description'], content)
        page(handbook['id'], handbook['title'], handbook['description'], overview)
        for item in lessons:
            if item['status'] == 'planned':
                continue
            content = authors_html(item['authors'])
            content += '<nav class="lesson-toc" aria-label="Оглавление параграфа"><ul>' + ''.join('<li>' + link('#' + h['id'], h['text']) + '</li>' for h in rendered[item['id']]['toc'] if h['level'] == 2) + '</ul></nav>'
            content += item['_html'] + pagination(item['id'], route, by_id)
            page(item['id'], item['title'], item['description'], content)
    for item in book['_pages']:
        page(item['id'], item['title'], item['title'], item['_html'])
    if any(h['id'] == 'ml' for h in handbooks):
        write_redirect(output / 'handbooks/start/index.html', '../ml/intro/')
        for old, new in REDIRECTS.items():
            if 'ml/' + new in book['_chapters']:
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
