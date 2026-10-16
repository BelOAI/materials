"""Оглавление и страницы учебника: раздел → глава → урок."""
from __future__ import annotations
import json
import re
import shutil
import subprocess
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from course_site import link, write_page
from notebook_export import export_notebook

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
    base = source / 'handbook'
    book = json.loads((base / 'handbook.json').read_text(encoding='utf-8'))
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
            if not isinstance(chapter.get('lessons'), list) or not chapter['lessons']:
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
    route = book.get('reading_order')
    if not isinstance(route, list) or not route or len(set(route)) != len(route):
        raise ValueError('Неверный путь обучения')
    seen = set()
    for identifier in route:
        if identifier not in lessons or lessons[identifier]['status'] == 'planned' or not set(lessons[identifier].get('prerequisites', [])).issubset(seen):
            raise ValueError('Путь обучения не учитывает предварительные знания')
        seen.add(identifier)
    curriculum = book.get('curriculum')
    phases = curriculum.get('phases') if isinstance(curriculum, dict) else None
    if not isinstance(phases, list) or not phases:
        raise ValueError('Необходим общий маршрут обучения')
    seen, phase_ids = set(), set()
    for phase in phases:
        if (not isinstance(phase, dict) or not identifier_ok(phase.get('slug'), 1)
                or phase['slug'] in phase_ids or not nonempty(phase.get('title'))
                or not isinstance(phase.get('learning_outcomes'), list)
                or not phase['learning_outcomes'] or not all(nonempty(v) for v in phase['learning_outcomes'])
                or not isinstance(phase.get('lessons'), list) or not phase['lessons']):
            raise ValueError('Неверный этап общего маршрута')
        phase_ids.add(phase['slug'])
        for identifier in phase['lessons']:
            if (not isinstance(identifier, str) or identifier not in lessons or identifier in seen
                    or lessons[identifier].get('optional')
                    or not set(lessons[identifier].get('prerequisites', [])).issubset(seen)):
                raise ValueError('Общий маршрут не учитывает предварительные знания')
            seen.add(identifier)
    if seen != {i for i, lesson in lessons.items() if not lesson.get('optional')}:
        raise ValueError('Общий маршрут должен охватывать все обязательные уроки')
    if phases[0]['lessons'] != route:
        raise ValueError('Первый этап должен совпадать с путём к первому эксперименту')
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
    book['_lessons'], book['_chapters'], book['_owners'] = lessons, chapters, owners
    return book


def lesson_routes(book):
    """Основной маршрут и отдельные связанные необязательные ветки."""
    lessons = book['_lessons']
    routes = [[identifier for phase in book['curriculum']['phases']
               for identifier in phase['lessons'] if lessons[identifier]['status'] != 'planned']]
    for chapter in book['_chapters'].values():
        branch = []
        for lesson in chapter['lessons']:
            if not lesson.get('optional') or lesson['status'] == 'planned':
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
    pages = {p.resolve(): PageLinks(p.read_text(encoding='utf-8')) for p in (output / 'handbook').rglob('index.html')}
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
    result = subprocess.run(['node', str(source / 'site/render-handbook.mjs')], input=json.dumps([
        {'name': item['id'], 'source': (source / 'handbook' / item['id'] / 'index.md').read_text(encoding='utf-8')}
        for item in published
    ]), text=True, capture_output=True, check=True)
    rendered = dict(zip((item['id'] for item in published), json.loads(result.stdout)))
    shutil.rmtree(output / 'handbook', ignore_errors=True)
    data = source / 'handbook/data'
    if data.is_dir():
        for path in data.rglob('*'):
            if path.is_file():
                local_file(source / 'handbook', str(path.relative_to(source / 'handbook')))
        shutil.copytree(data, output / 'handbook/data')
    katex = source / 'site/node_modules/katex'
    shutil.copytree(katex / 'dist/fonts', output / 'assets/katex/fonts', dirs_exist_ok=True)
    shutil.copyfile(katex / 'dist/katex.min.css', output / 'assets/katex/katex.min.css')
    shutil.copyfile(katex / 'LICENSE', output / 'assets/katex/LICENSE')

    def navigation_link(href, text, current=False):
        active = ' aria-current="page"' if current else ''
        return ('<a href="' + escape(href, quote=True) + '"' + active
                + ' data-nav-label="' + escape(text, quote=True) + '"><span class="nav-label">'
                + escape(text) + '</span></a>')

    def label(item, root, current='', navigation=False):
        text = item['title'] + (' (дополнительно)' if item.get('optional') else '')
        if item.get('status') == 'planned':
            return escape(text) + ' <span class="chapter-unavailable">(ещё нет текста)</span>'
        if navigation:
            return navigation_link(root + 'handbook/' + item['id'] + '/', text, item['id'] == current)
        return link(root + 'handbook/' + item['id'] + '/', text, ' aria-current="page"' if item['id'] == current else '')

    def listing(items, root):
        return '<ol>' + ''.join('<li>' + label(item, root) + '</li>' for item in items) + '</ol>'

    def navigation(root, current, owner=None):
        def navlink(identifier, title):
            return navigation_link(root + 'handbook/' + (identifier + '/' if identifier else ''), title, identifier == current)
        top = '<div class="handbook-links"><ul><li>' + link(root, '← На основной сайт') + '</li><li>' + navlink('', 'Учебник') + '</li><li>' + navlink('start', 'Как пользоваться учебником') + '</li></ul></div>'
        nav = '<div class="handbook-tree">'
        for track in book['tracks']:
            nav += '<section class="handbook-track" aria-label="' + escape(track['title'], quote=True) + '"><div class="track-title">' + navlink(track['slug'], track['title']) + '</div>'
            for number, chapter in enumerate(track['chapters'], 1):
                opened = ' open' if chapter['id'] == current or (owner and owner['id'] == chapter['id']) else ''
                nav += '<details class="handbook-chapter"' + opened + '><summary><span class="chapter-title">' + escape(f'{number}. {chapter["title"]}') + '</span></summary><ul><li>' + navlink(chapter['id'], 'Обзор главы') + '</li>'
                nav += ''.join('<li>' + label(item, root, current, navigation=True) + '</li>' for item in chapter['lessons']) + '</ul></details>'
            nav += '</section>'
        return top, nav + '</div>'

    def page(identifier, title, description, content, owner=None):
        path = 'handbook' + ('/' + identifier if identifier else '')
        root = '../' * len(Path(path).parts)
        content = content.replace('</h1>', '</h1>' + draft_note, 1)
        navigation_top, navigation_body = navigation(root, identifier, owner)
        write_page(source, output, weeks, path, title, description,
                   '<div class="handbook-content">' + content + '</div>', 'handbook', root,
                   navigation_override=navigation_body, navigation_top=navigation_top, brand_href=root + 'handbook/',
                   navigation_label='Оглавление учебника')
        dest = output / path / 'index.html'
        html = dest.read_text(encoding='utf-8').replace('</head>', f'<link rel="stylesheet" href="{root}assets/katex/katex.min.css" />\n</head>')
        dest.write_text(html, encoding='utf-8')

    def resources(item, destination):
        content = ''
        if item.get('resources'):
            content = '<h2>Файлы урока</h2><ul>'
            for resource in item['resources']:
                src = local_file(source / 'handbook' / item['id'], resource['path'])
                dest = output / 'handbook' / destination / resource['path']
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

    def crumbs(root, track, chapter, title):
        return '<nav class="breadcrumbs" aria-label="Путь к уроку"><ol><li>' + link(root + 'handbook/', 'Учебник') + '</li><li>' + link(root + 'handbook/' + track['slug'] + '/', track['title']) + '</li><li>' + link(root + 'handbook/' + chapter['id'] + '/', chapter['title']) + '</li><li aria-current="page">' + escape(title) + '</li></ol></nav>'

    draft_note = '<p class="draft-note"><span class="draft-badge">Черновик</span><span>Материалы дорабатываются и будут дополняться.</span></p>'

    overview = '<h1>Учебник BelOAI</h1><p>' + escape(book['description']) + '</p><p>Достаточно школьной арифметики; опыт программирования не нужен.</p><p>' + link('python/basic-constructs/input-output/', 'Начать первый урок →') + ' · ' + link('start/', 'Как пользоваться учебником') + '</p>'
    overview += '<ul>'
    for track in book['tracks']:
        overview += '<li>' + link(track['slug'] + '/', track['title']) + ' — ' + escape(track['description']) + '</li>'
        track_content = '<h1>' + escape(track['title']) + '</h1><p>' + escape(track['description']) + '</p>'
        for chapter in track['chapters']:
            track_content += '<h2>' + link('../../handbook/' + chapter['id'] + '/', chapter['title']) + '</h2>' + listing(chapter['lessons'], '../../')
            chapter_root = '../../../'
            content = '<nav class="breadcrumbs" aria-label="Путь к главе"><ol><li>' + link(chapter_root + 'handbook/', 'Учебник') + '</li><li>' + link(chapter_root + 'handbook/' + track['slug'] + '/', track['title']) + '</li></ol></nav>'
            content += '<h1>' + escape(chapter['title']) + '</h1><p>' + escape(chapter['description']) + '</p>' + listing(chapter['lessons'], chapter_root)
            page(chapter['id'], chapter['title'], chapter['description'], content, chapter)
        page(track['slug'], track['title'], track['description'], track_content)
    page('', book['title'], book['description'], overview + '</ul>')
    routes = lesson_routes(book)
    route_by_lesson = {identifier: route for route in routes for identifier in route}
    for item in published:
        identifier = item['id']
        root = '../' * (len(identifier.split('/')) + 1)
        owner = book['_owners'].get(identifier)
        content = crumbs(root, owner[0], owner[1], item['title']) if owner else ''
        content += '<h1>' + escape(item['title']) + '</h1>'
        if item.get('prerequisites'):
            content += '<h2>Перед началом</h2>' + listing([lessons[i] for i in item['prerequisites']], root)
        content += '<nav class="lesson-toc" aria-label="Оглавление урока"><h2>В этом уроке</h2><ul>' + ''.join('<li>' + link('#' + heading['id'], heading['text']) + '</li>' for heading in rendered[identifier]['toc'] if heading['level'] == 2) + '</ul></nav>'
        content += rendered[identifier]['html'] + resources(item, identifier)
        if identifier in route_by_lesson:
            available = route_by_lesson[identifier]
            index = available.index(identifier)
            title = 'Переходы между уроками'
            content += '<nav class="week-pagination" aria-label="' + title + '">'
            for offset, text, rel in [(-1, '← ', 'prev'), (1, 'Далее: ', 'next')]:
                if 0 <= index + offset < len(available):
                    neighbor = lessons[available[index + offset]]
                    content += link(root + 'handbook/' + neighbor['id'] + '/', text + neighbor['title'], f' rel="{rel}"')
            content += '</nav>'
        page(identifier, item['title'], item.get('description', item['title']), content, owner[1] if owner else None)
    for alias in book.get('aliases', []):
        root = '../../../'
        content = '<h1>' + escape(alias['title']) + '</h1><p>Выберите урок:</p>' + listing([lessons[i] for i in alias['lessons']], root)
        content += '<ul class="lesson-transition">' + ''.join('<li id="' + escape(a['id'], quote=True) + '">' + link(root + 'handbook/' + a['target'].split('#')[0] + '/' + ('#' + a['target'].split('#', 1)[1] if '#' in a['target'] else ''), a['label']) + '</li>' for a in alias.get('anchors', [])) + '</ul>'
        content += resources(alias, alias['id'])
        owner = book['_owners'][alias['lessons'][0]][1]
        page(alias['id'], alias['title'], alias['title'], content, owner)
    # Keep the draft out of search results, including notebook HTML previews.
    for path in (output / 'handbook').rglob('*.html'):
        html = path.read_text(encoding='utf-8')
        html = html.replace('</head>', '<meta name="robots" content="noindex, nofollow" />\n</head>', 1)
        path.write_text(html, encoding='utf-8')
    validate_links(output)
