"""Общие метаданные учебников; без зависимости от HTML и инструментов сборки."""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from authorship import normalize_authors

SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
FOLDER = re.compile(r'[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*')
STATUSES = {'planned', 'draft', 'reviewed'}


class MetadataLoader(yaml.SafeLoader):
    """Не позволять YAML молча перезаписывать повторяющийся ключ."""


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise ValueError(f'Повтор или неверный ключ YAML: {key!r}')
        result[key] = loader.construct_object(value_node)
    return result


MetadataLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def local_file(base: Path, value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f'Ожидается относительный путь: {value!r}')
    path = (base / value).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f'Файл отсутствует или выходит за пределы папки: {value}')
    return path


def read_metadata(folder):
    path = local_file(folder, 'meta.yaml')
    try:
        item = yaml.load(path.read_text(encoding='utf-8'), Loader=MetadataLoader)
        if (not isinstance(item, dict) or not isinstance(item.get('slug'), str)
                or not SLUG.fullmatch(item['slug']) or item['slug'] in {'data', 'media', 'start'}
                or not all(nonempty(item.get(k)) for k in ('title', 'description'))
                or item.get('status') not in STATUSES):
            raise ValueError('Необходимы slug, title, description, status и authors')
        item['authors'] = normalize_authors(item.get('authors'))
        if item['status'] != 'planned' and not item['authors']:
            raise ValueError('Для текста необходимо указать авторов')
        if item['status'] != 'planned' and not isinstance(item.get('build'), bool):
            raise ValueError('Для текста необходимо build: true')
        if not isinstance(item.get('references', []), list):
            raise ValueError('Неверные внешние ссылки')
        for ref in item.get('references', []):
            if (not isinstance(ref, dict) or not nonempty(ref.get('label'))
                    or not isinstance(ref.get('url'), str)
                    or urlsplit(ref['url']).scheme not in {'http', 'https'}
                    or not urlsplit(ref['url']).netloc):
                raise ValueError('Неверная внешняя ссылка')
        return item
    except (yaml.YAMLError, ValueError) as error:
        raise ValueError(f'{path}: {error}') from error


def ordered_folders(base, names):
    if (not isinstance(names, list) or len(set(n for n in names if isinstance(n, str))) != len(names)
            or any(not isinstance(n, str) or (not n.startswith('_') and not FOLDER.fullmatch(n)) for n in names)):
        raise ValueError(f'{base}: ожидается список уникальных папок NN-slug')
    for name in names:
        if name.startswith('_'):
            continue
        folder = base / name
        local_file(folder, 'README.md')
        # Проверка resolve защищает также от символьных ссылок наружу.
        local_file(base, name + '/meta.yaml')
        yield folder


def validate_resources(folder, item, allow_missing_synced=False):
    resources = item.get('resources', [])
    if not isinstance(resources, list):
        raise ValueError(f'{folder}: неверные resources')
    seen = set()
    for resource in resources:
        if (not isinstance(resource, dict) or not nonempty(resource.get('label'))
                or not nonempty(resource.get('path')) or resource['path'] in seen):
            raise ValueError(f'{folder}: неверный или повторный ресурс')
        path = resource['path']
        if path in {'index.html', 'content.md', 'meta.yaml', 'README.md'} or any(p.startswith(('_', '.')) for p in Path(path).parts):
            raise ValueError(f'{folder}: служебный ресурс {path}')
        if not (allow_missing_synced and item.get('sync_notebook') and path == 'notebook.ipynb' and not (folder / path).exists()):
            local_file(folder, path)
        seen.add(path)


def load_catalog(source: Path, *, allow_missing_synced=False) -> dict:
    base = source / 'handbooks'
    book = json.loads(local_file(base, 'handbooks.json').read_text(encoding='utf-8'))
    if not isinstance(book, dict) or not all(nonempty(book.get(k)) for k in ('title', 'description')):
        raise ValueError('Необходимы название и описание каталога')
    if not isinstance(book.get('handbooks'), list):
        raise ValueError('Ожидается список учебников')
    book['_lessons'], book['_chapters'], book['_excluded'] = {}, {}, []
    seen = set()
    book['handbooks'] = [h for h in book['handbooks'] if not (
        isinstance(h, dict) and isinstance(h.get('slug'), str) and h['slug'].startswith('_')
    )]
    for handbook in book['handbooks']:
        if (not isinstance(handbook, dict) or not isinstance(handbook.get('slug'), str)
                or not SLUG.fullmatch(handbook['slug']) or handbook['slug'] in seen
                or not all(nonempty(handbook.get(k)) for k in ('title', 'description'))):
            raise ValueError('Некорректный или повторный учебник')
        seen.add(handbook['slug'])
        slug = handbook['slug']
        folder = base / slug
        if not folder.resolve().is_relative_to(base.resolve()):
            raise ValueError(f'Учебник вне handbooks: {slug}')
        handbook.update(id=slug, _folder=folder)
        if handbook.get('build') is False or handbook.get('status') == 'planned':
            handbook['sections'] = []
            continue
        if (folder / 'content.md').is_file():
            handbook['_content'] = local_file(base, slug + '/content.md')
        handbook['authors'] = normalize_authors(handbook.get('authors'))
        _load_sections(handbook, book, allow_missing_synced)
    return book


def _load_sections(handbook, book, allow_missing_synced):
    slug, base = handbook['slug'], handbook['_folder']
    sections, paragraphs, identifiers = [], {}, set()
    for folder in ordered_folders(base, handbook.get('chapters')):
        chapter = read_metadata(folder)
        if chapter.get('build') is False:
            book['_excluded'].append(dict(id=slug + '/' + chapter['slug'], _folder=folder))
            continue
        identifier = slug + '/' + chapter['slug']
        if identifier in identifiers:
            raise ValueError(f'{folder}: повтор или зарезервированный slug')
        identifiers.add(identifier)
        chapter.update(id=identifier, _folder=folder, lessons=[])
        para_folders = list(ordered_folders(folder, chapter.get('paragraphs')))
        if chapter['status'] == 'planned' and (chapter.get('paragraphs') or (folder / 'content.md').exists()):
            raise ValueError(f'{folder}: planned не должен содержать текст или параграфы')
        if chapter['status'] != 'planned' and not para_folders and not (folder / 'content.md').is_file():
            raise ValueError(f'{folder}: глава должна содержать текст или параграфы')
        if (folder / 'content.md').exists():
            chapter['_content'] = local_file(folder, 'content.md')
        validate_resources(folder, chapter)
        for para_folder in para_folders:
            item = read_metadata(para_folder)
            if item.get('build') is False:
                book['_excluded'].append(dict(id=identifier + '/' + item['slug'], _folder=para_folder))
                continue
            para_id = identifier + '/' + item['slug']
            if para_id in identifiers:
                raise ValueError(f'{para_folder}: повтор slug')
            identifiers.add(para_id)
            item.update(id=para_id, _folder=para_folder)
            if item['status'] != 'planned':
                item['_content'] = local_file(para_folder, 'content.md')
            validate_resources(para_folder, item, allow_missing_synced)
            chapter['lessons'].append(item['id'])
            paragraphs[item['id']] = item
        sections.append(chapter)
    handbook['sections'] = sections
    book['_lessons'].update(paragraphs)
    book['_chapters'].update({s['id']: s for s in sections})
