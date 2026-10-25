"""Самостоятельные учебники на общем каталоге уроков и общей оболочке."""
from __future__ import annotations
import json
import posixpath
import re
import shutil
import subprocess
from datetime import date
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urljoin, urlunsplit
from course_site import link, write_page
from notebook_export import export_notebook
from handbook_redirects import publish_legacy_handbook

STATUSES = {'planned', 'draft', 'reviewed'}
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')


def local_file(base: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f'Ожидается относительный путь: {value!r}')
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f'Файл отсутствует или выходит за пределы папки: {value}')
    return path


def identifier_ok(value, length):
    return isinstance(value, str) and len(value.split('/')) == length and all(SLUG.fullmatch(p) for p in value.split('/'))


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_resources(base, item):
    if not isinstance(item.get('resources', []), list):
        raise ValueError('Некорректные ресурсы')
    for resource in item.get('resources', []):
        if not isinstance(resource, dict) or not nonempty(resource.get('label')) or resource.get('path') == 'index.html':
            raise ValueError('Некорректный ресурс')
        local_file(base, resource.get('path'))


def load_handbook(source: Path) -> dict:
    base = source / 'handbooks'
    book = json.loads((base / 'handbooks.json').read_text(encoding='utf-8'))
    if not all(nonempty(book.get(k)) for k in ('title', 'description')):
        raise ValueError('Необходимы название и описание учебника')
    if not isinstance(book.get('tracks'), list) or not book['tracks']:
        raise ValueError('Необходимы разделы')
    lessons, chapters, owners, track_ids = {}, {}, {}, set()
    start = book.get('start')
    if not isinstance(start, dict) or start.get('id') != 'start' or start.get('status') == 'planned':
        raise ValueError('Необходимо опубликованное введение')
    items = [start]
    for track in book['tracks']:
        if not isinstance(track, dict) or not identifier_ok(track.get('slug'), 1) or track['slug'] == 'start' or track['slug'] in track_ids or not all(nonempty(track.get(k)) for k in ('title', 'description')):
            raise ValueError('Некорректный раздел')
        track_ids.add(track['slug'])
        if not isinstance(track.get('chapters'), list) or not track['chapters']:
            raise ValueError('Раздел должен содержать главы')
        for chapter in track['chapters']:
            if not isinstance(chapter, dict) or not identifier_ok(chapter.get('id'), 2) or not chapter['id'].startswith(track['slug'] + '/') or chapter['id'] in chapters or not all(nonempty(chapter.get(k)) for k in ('title', 'description')):
                raise ValueError('Некорректная глава')
            if (chapter.get('status') not in (None, 'planned')
                    or not isinstance(chapter.get('lessons'), list)
                    or (not chapter['lessons'] and chapter.get('status') != 'planned')
                    or (chapter.get('status') == 'planned' and chapter['lessons'])):
                raise ValueError('Глава должна содержать уроки')
            chapters[chapter['id']] = chapter
            for lesson in chapter['lessons']:
                if not isinstance(lesson, dict) or not identifier_ok(lesson.get('id'), 3) or not lesson['id'].startswith(chapter['id'] + '/'):
                    raise ValueError('Урок должен принадлежать своей главе')
                owners[lesson['id']] = (track, chapter)
                items.append(lesson)
    for item in items:
        identifier = item['id']
        if identifier in lessons or not nonempty(item.get('title')) or item.get('status') not in STATUSES:
            raise ValueError('Повтор или неверные метаданные урока')
        for key in ('topics', 'learning_outcomes'):
            if not isinstance(item.get(key), list) or not item[key] or not all(nonempty(v) for v in item[key]):
                raise ValueError(f'Необходимо поле {key}: {identifier}')
        if not isinstance(item.get('prerequisites', []), list) or not all(isinstance(v, str) for v in item.get('prerequisites', [])):
            raise ValueError('Неверные предварительные уроки')
        if item['status'] != 'planned':
            if item.get('build') is not True or not isinstance(item.get('date'), str):
                raise ValueError('Необходимы build и дата урока')
            date.fromisoformat(item['date'])
            local_file(base, identifier + '/index.md')
            validate_resources(base / identifier, item)
        if not isinstance(item.get('references', []), list):
            raise ValueError('Некорректные внешние ссылки')
        for ref in item.get('references', []):
            if not isinstance(ref, dict) or not nonempty(ref.get('label')) or not isinstance(ref.get('url'), str) or urlsplit(ref['url']).scheme not in ('http', 'https') or not urlsplit(ref['url']).netloc:
                raise ValueError('Некорректная внешняя ссылка')
        lessons[identifier] = item
    visiting, visited = set(), set()
    def visit(identifier):
        if identifier in visiting:
            raise ValueError('Цикл предварительных знаний')
        if identifier in visited:
            return
        visiting.add(identifier)
        for dep in lessons[identifier].get('prerequisites', []):
            if dep not in lessons or (lessons[identifier]['status'] != 'planned' and lessons[dep]['status'] == 'planned'):
                raise ValueError('Недоступный предварительный урок')
            visit(dep)
        visiting.remove(identifier)
        visited.add(identifier)
    for identifier in lessons:
        visit(identifier)
    handbooks = book.get('handbooks')
    if not isinstance(handbooks, list) or not handbooks:
        raise ValueError('Необходимы самостоятельные учебники')
    handbook_ids = set()
    for handbook in handbooks:
        slug = handbook.get('slug') if isinstance(handbook, dict) else None
        if (slug not in track_ids or slug in handbook_ids
                or not all(nonempty(handbook.get(k)) for k in ('title', 'description'))
                or handbook.get('introduction') != slug + '/start'):
            raise ValueError('Некорректный учебник')
        handbook_ids.add(slug)
        local_file(base, handbook['introduction'] + '/index.md')
        sections = handbook.get('sections')
        if not isinstance(sections, list) or not sections:
            raise ValueError('Необходимо оглавление учебника')
        seen, section_ids = set(), set()
        for section in sections:
            if (not isinstance(section, dict) or not identifier_ok(section.get('slug'), 1)
                    or section['slug'] in {'start', 'data'} | section_ids
                    or not all(nonempty(section.get(k)) for k in ('title', 'description'))
                    or section.get('status') not in (None, 'planned')
                    or not isinstance(section.get('lessons'), list)
                    or (not section['lessons'] and section.get('status') != 'planned')
                    or (section.get('status') == 'planned' and section['lessons'])):
                raise ValueError('Некорректный раздел учебника')
            section_ids.add(section['slug'])
            for identifier in section['lessons']:
                if not isinstance(identifier, str) or identifier not in owners or identifier in seen:
                    raise ValueError('Неизвестный урок или повтор включения в учебник')
                seen.add(identifier)
        if not {i for i in owners if i.startswith(slug + '/')}.issubset(seen):
            raise ValueError('Учебник должен включать все собственные уроки')
    if handbook_ids != track_ids:
        raise ValueError('Для каждого предмета необходим самостоятельный учебник')
    optional = {i for i, lesson in lessons.items() if lesson.get('optional')}
    if any(optional.intersection(lesson.get('prerequisites', []))
           for lesson in lessons.values() if not lesson.get('optional')):
        raise ValueError('Необязательная ветка не должна блокировать основной маршрут')
    if not isinstance(book.get('aliases', []), list):
        raise ValueError('Неверные старые адреса')
    aliases = set()
    for alias in book.get('aliases', []):
        if not isinstance(alias, dict) or not identifier_ok(alias.get('id'), 2) or alias['id'] in chapters or alias['id'] in aliases or not nonempty(alias.get('title')):
            raise ValueError('Повтор или неверный старый адрес')
        aliases.add(alias['id'])
        targets = alias.get('lessons')
        if not isinstance(targets, list) or not targets or any(t not in lessons or lessons[t]['status'] == 'planned' for t in targets):
            raise ValueError('Старый адрес ссылается на недоступный урок')
        if not isinstance(alias.get('anchors', []), list):
            raise ValueError('Неверные старые якоря')
        anchors = set()
        for anchor in alias.get('anchors', []):
            if not isinstance(anchor, dict) or not nonempty(anchor.get('id')) or anchor['id'] in anchors or not nonempty(anchor.get('label')) or not isinstance(anchor.get('target'), str) or anchor['target'].split('#')[0] not in targets:
                raise ValueError('Неверный старый якорь')
            anchors.add(anchor['id'])
        validate_resources(base / alias['id'], alias)
    section_paths = {h['slug'] + '/' + section['slug'] for h in handbooks for section in h['sections']}
    if (section_paths | {h['introduction'] for h in handbooks}).intersection(aliases):
        raise ValueError('Страница учебника занимает старый адрес')
    book['_lessons'], book['_chapters'], book['_owners'] = lessons, chapters, owners
    return book


def lesson_path(handbook, identifier):
    """Адрес урока в контексте учебника без перемещения исходника."""
    return identifier if identifier.startswith(handbook['slug'] + '/') else handbook['slug'] + '/' + identifier


def lesson_routes(book, handbook):
    """Маршрут учебника и отдельные связанные необязательные ветки."""
    lessons = book['_lessons']
    included = {i for section in handbook['sections'] for i in section['lessons']}
    routes = [[handbook['introduction']] + [i for section in handbook['sections']
               for i in section['lessons'] if not lessons[i].get('optional')
               and lessons[i]['status'] != 'planned']]
    for chapter in book['_chapters'].values():
        branch = []
        for lesson in chapter['lessons']:
            if (lesson['id'] not in included or not lesson.get('optional')
                    or lesson['status'] == 'planned'):
                if branch:
                    routes.append(branch)
                branch = []
                continue
            if branch and branch[-1] not in lesson.get('prerequisites', []):
                routes.append(branch)
                branch = []
            branch.append(lesson['id'])
        if branch:
            routes.append(branch)
    return routes


def contextual_html(html, identifier, destination, handbook, lessons):
    """Разрешать URL относительно исходного урока, затем учитывать контекст."""
    included = {i for section in handbook['sections'] for i in section['lessons']} if handbook else set()
    def replace(match):
        href = unescape(match[3])
        url = urlsplit(href)
        if not url.path or url.scheme or url.netloc or url.path.startswith('/'):
            return match[0]
        target = urlsplit(urljoin('https://handbook.invalid/handbooks/' + identifier + '/', href))
        path = unquote(target.path)
        # Только страницы уроков меняют контекст; файлы и данные общие.
        candidate = path.removeprefix('/handbooks/').removesuffix('index.html').rstrip('/')
        if candidate in included and candidate in lessons:
            path = '/handbooks/' + lesson_path(handbook, candidate) + '/'
        relative = posixpath.relpath(path, '/handbooks/' + destination)
        if path.endswith('/'):
            relative += '/'
        return match[1] + '=' + match[2] + escape(urlunsplit(('', '', relative, url.query, url.fragment)), quote=True) + match[2]
    return re.sub(r"\b(href|src)=([\"'])(.*?)\2", replace, html)


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


def publish_handbook(source: Path, output: Path, weeks: list) -> None:
    book = load_handbook(source)
    lessons = book['_lessons']
    published = [item for item in lessons.values() if item['status'] != 'planned']
    handbooks = {h['slug']: h for h in book['handbooks']}
    introductions = {h['introduction']: {'id': h['introduction'], 'title': 'Как пользоваться учебником'}
                     for h in handbooks.values()}
    texts = published + list(introductions.values())
    result = subprocess.run(['node', str(source / 'utils/site/render-handbook.mjs')], input=json.dumps([
        {'name': item['id'], 'source': (source / 'handbooks' / item['id'] / 'index.md').read_text(encoding='utf-8')}
        for item in texts
    ]), text=True, capture_output=True, check=True)
    rendered = dict(zip((item['id'] for item in texts), json.loads(result.stdout)))
    shutil.rmtree(output / 'handbooks', ignore_errors=True)
    data = source / 'handbooks/data'
    if data.is_dir():
        for path in data.rglob('*'):
            if path.is_file():
                local_file(source / 'handbooks', str(path.relative_to(source / 'handbooks')))
        shutil.copytree(data, output / 'handbooks/data')
    katex = source / 'utils/site/node_modules/katex'
    shutil.copytree(katex / 'dist/fonts', output / 'assets/katex/fonts', dirs_exist_ok=True)
    shutil.copyfile(katex / 'dist/katex.min.css', output / 'assets/katex/katex.min.css')
    shutil.copyfile(katex / 'LICENSE', output / 'assets/katex/LICENSE')

    def navigation_link(href, text, current=False):
        active = ' aria-current="page"' if current else ''
        return ('<a href="' + escape(href, quote=True) + '"' + active
                + ' data-nav-label="' + escape(text, quote=True) + '"><span class="nav-label">'
                + escape(text) + '</span></a>')

    def label(item, root, handbook=None, current='', navigation=False):
        text = item['title'] + (' (дополнительно)' if item.get('optional') else '')
        if item.get('status') == 'planned':
            return escape(text) + ' <span class="chapter-unavailable">(ещё нет текста)</span>'
        included = handbook and any(item['id'] in section['lessons'] for section in handbook['sections'])
        path = lesson_path(handbook, item['id']) if included else item['id']
        if handbook and item['id'] == 'start':
            path = handbook['introduction']
        if navigation:
            return navigation_link(root + 'handbooks/' + path + '/', text, path == current)
        return link(root + 'handbooks/' + path + '/', text)

    def listing(items, root, handbook=None):
        return '<ol>' + ''.join('<li>' + label(item, root, handbook) + '</li>' for item in items) + '</ol>'

    def section_title(handbook, section):
        number = handbook['sections'].index(section) + (0 if handbook['slug'] == 'ml' else 1)
        return f'{number}. {section["title"]}'

    def navigation(root, current, handbook=None, owner=None):
        def navlink(identifier, title):
            return navigation_link(root + 'handbooks/' + (identifier + '/' if identifier else ''), title, identifier == current)
        top = '<div class="handbook-links"><ul><li>' + link(root, '← На основной сайт') + '</li><li>' + navlink('', 'Учебники') + '</li></ul></div>'
        nav = '<div class="handbook-tree"><ul>'
        for h in handbooks.values():
            nav += '<li>' + navlink(h['slug'], h['title']) + '</li>'
        nav += '</ul>'
        if current == 'start':
            nav += '<ul><li>' + navlink('start', 'Как пользоваться учебниками') + '</li></ul>'
        if handbook:
            nav += '<section class="handbook-track" aria-label="' + escape(handbook['title'], quote=True) + '"><div class="track-title">' + navlink(handbook['introduction'], 'Как пользоваться учебником') + '</div>'
            for section in handbook['sections']:
                identifier = handbook['slug'] + '/' + section['slug']
                opened = ' open' if section is owner or identifier == current else ''
                nav += '<details class="handbook-chapter"' + opened + '><summary><span class="chapter-title">' + escape(section_title(handbook, section)) + '</span></summary><ul><li>' + navlink(identifier, 'Обзор раздела') + '</li>'
                nav += ''.join('<li>' + label(lessons[i], root, handbook, current, navigation=True) + '</li>' for i in section['lessons']) + '</ul></details>'
            nav += '</section>'
        return top, nav + '</div>'

    draft_note = '<p class="draft-note"><span class="draft-badge">Черновик</span><span>Материалы дорабатываются и будут дополняться.</span></p>'

    def page(identifier, title, description, content, handbook=None, owner=None):
        path = 'handbooks' + ('/' + identifier if identifier else '')
        root = '../' * len(Path(path).parts)
        content = content.replace('</h1>', '</h1>' + draft_note, 1)
        navigation_top, navigation_body = navigation(root, identifier, handbook, owner)
        write_page(source, output, weeks, path, title, description,
                   '<div class="handbook-content">' + content + '</div>', 'handbook', root,
                   navigation_override=navigation_body, navigation_top=navigation_top,
                   brand_href=root + 'handbooks/' + (handbook['slug'] + '/' if handbook else ''),
                   navigation_label='Оглавление учебника')
        dest = output / path / 'index.html'
        html = dest.read_text(encoding='utf-8').replace('</head>', f'<link rel="stylesheet" href="{root}assets/katex/katex.min.css" />\n</head>')
        dest.write_text(html, encoding='utf-8')

    def resources(item):
        # Каждый исходный ресурс и HTML-превью публикуются один раз.
        content = ''
        if item.get('resources'):
            content = '<h2>Файлы урока</h2><ul>'
            for resource in item['resources']:
                src = local_file(source / 'handbooks' / item['id'], resource['path'])
                dest = output / 'handbooks' / item['id'] / resource['path']
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                content += '<li>' + link(resource['path'], resource['label'], ' download')
                if src.suffix == '.ipynb' and export_notebook(dest):
                    content += ' · ' + link(str(Path(resource['path']).with_suffix('.html')), 'Открыть в браузере')
                content += '</li>'
            content += '</ul>'
        if item.get('references'):
            content += '<h2>Дополнительные материалы</h2><ul>' + ''.join('<li>' + link(ref['url'], ref['label']) + '</li>' for ref in item['references']) + '</ul>'
        return content

    resource_html = {item['id']: resources(item) for item in [*published, *book.get('aliases', [])]}

    def crumbs(root, handbook, title, section=None):
        content = '<nav class="breadcrumbs" aria-label="Путь к уроку"><ol><li>' + link(root + 'handbooks/', 'Учебники') + '</li><li>' + link(root + 'handbooks/' + handbook['slug'] + '/', handbook['title']) + '</li>'
        if section:
            content += '<li>' + link(root + 'handbooks/' + handbook['slug'] + '/' + section['slug'] + '/', section['title']) + '</li>'
        return content + '<li aria-current="page">' + escape(title) + '</li></ol></nav>'

    overview = '<h1>Учебники BelOAI</h1><p>' + escape(book['description']) + '</p><ul>'
    for handbook in handbooks.values():
        overview += '<li>' + link(handbook['slug'] + '/', handbook['title']) + ' — ' + escape(handbook['description']) + '</li>'
    page('', book['title'], book['description'], overview + '</ul>')

    for handbook in handbooks.values():
        slug = handbook['slug']
        routes = lesson_routes(book, handbook)
        route_by_lesson = {i: route for route in routes for i in route}
        section_by_lesson = {i: section for section in handbook['sections'] for i in section['lessons']}

        def pagination(identifier, root):
            if identifier not in route_by_lesson:
                return ''
            route = route_by_lesson[identifier]
            index = route.index(identifier)
            content = '<nav class="week-pagination" aria-label="Переходы между уроками">'
            for offset, text, rel in [(-1, '← ', 'prev'), (1, 'Далее: ', 'next')]:
                if 0 <= index + offset < len(route):
                    neighbor = route[index + offset]
                    title = (lessons.get(neighbor) or introductions[neighbor])['title']
                    content += link(root + 'handbooks/' + lesson_path(handbook, neighbor) + '/', text + title, f' rel="{rel}"')
            return content + '</nav>'

        content = '<h1>' + escape(handbook['title']) + '</h1><p>' + escape(handbook['description']) + '</p><p>' + link('../../handbooks/' + handbook['introduction'] + '/', 'Начать: как пользоваться учебником →') + '</p>'
        for section in handbook['sections']:
            identifier = slug + '/' + section['slug']
            content += '<h2>' + link('../../handbooks/' + identifier + '/', section_title(handbook, section)) + '</h2><p>' + escape(section['description']) + '</p>'
            if section.get('status') == 'planned':
                content += '<p class="section-planned">Раздел запланирован.</p>'
            root = '../../../'
            section_content = crumbs(root, handbook, section['title']) + '<h1>' + escape(section_title(handbook, section)) + '</h1><p>' + escape(section['description']) + '</p>'
            if section.get('status') == 'planned':
                section_content += '<p class="section-planned">Раздел запланирован. Учебные материалы ещё не опубликованы.</p>'
            else:
                section_content += listing([lessons[i] for i in section['lessons']], root, handbook)
            page(identifier, section['title'], section['description'], section_content, handbook, section)
        page(slug, handbook['title'], handbook['description'], content, handbook)

        for identifier in [handbook['introduction'], *section_by_lesson]:
            item = lessons.get(identifier) or introductions[identifier]
            if item.get('status') == 'planned':
                continue
            destination = lesson_path(handbook, identifier)
            root = '../' * (len(destination.split('/')) + 1)
            section = section_by_lesson.get(identifier)
            content = crumbs(root, handbook, item['title'], section) + '<h1>' + escape(item['title']) + '</h1>'
            if item.get('prerequisites'):
                content += '<h2>Перед началом</h2>' + listing([lessons[i] for i in item['prerequisites']], root, handbook)
            content += '<nav class="lesson-toc" aria-label="Оглавление урока"><h2>В этом уроке</h2><ul>' + ''.join('<li>' + link('#' + heading['id'], heading['text']) + '</li>' for heading in rendered[identifier]['toc'] if heading['level'] == 2) + '</ul></nav>'
            content += contextual_html(rendered[identifier]['html'] + resource_html.get(identifier, ''), identifier, destination, handbook, lessons)
            content += pagination(identifier, root)
            page(destination, item['title'], item.get('description', item['title']), content, handbook, section)

    # Главы, не совпадающие с разделами оглавления, получают отдельные обзоры.
    section_paths = {h['slug'] + '/' + s['slug'] for h in handbooks.values() for s in h['sections']}
    for identifier, chapter in book['_chapters'].items():
        if identifier not in section_paths:
            handbook = handbooks[identifier.split('/')[0]]
            content = '<h1>' + escape(chapter['title']) + '</h1><p>' + escape(chapter['description']) + '</p>' + listing(chapter['lessons'], '../../../', handbook)
            page(identifier, chapter['title'], chapter['description'], content, handbook)

    start = lessons['start']
    page('start', start['title'], start['title'], '<h1>' + escape(start['title']) + '</h1>' + rendered['start']['html'] + resource_html['start'])
    for alias in book.get('aliases', []):
        root = '../../../'
        content = '<h1>' + escape(alias['title']) + '</h1><p>Выберите урок:</p>' + listing([lessons[i] for i in alias['lessons']], root)
        content += '<ul class="lesson-transition">' + ''.join('<li id="' + escape(a['id'], quote=True) + '">' + link(root + 'handbooks/' + a['target'].split('#')[0] + '/' + ('#' + a['target'].split('#', 1)[1] if '#' in a['target'] else ''), a['label']) + '</li>' for a in alias.get('anchors', [])) + '</ul>'
        content += resource_html[alias['id']]
        page(alias['id'], alias['title'], alias['title'], content, handbooks[alias['id'].split('/')[0]])
    # Keep the draft out of search results, including notebook HTML previews.
    for path in (output / 'handbooks').rglob('*.html'):
        html = path.read_text(encoding='utf-8')
        html = html.replace('</head>', '<meta name="robots" content="noindex, nofollow" />\n</head>', 1)
        path.write_text(html, encoding='utf-8')
    validate_links(output)
    publish_legacy_handbook(output)
