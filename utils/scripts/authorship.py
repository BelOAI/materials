"""Общие подписи авторов в метаданных, HTML и ноутбуках."""
from html import escape
import re

CONTRIBUTORS_MARKER = '<!-- handbook-contributors -->'


def expand_contributors(source, root):
    """Общий список авторов внутри Markdown учебника для HTML и PDF."""
    if CONTRIBUTORS_MARKER not in source:
        return source
    contributors = (root / 'CONTRIBUTORS.md').read_text(encoding='utf-8')
    contributors = re.sub(r'\A\s*# [^\n]*\n+', '', contributors).strip()
    return source.replace(CONTRIBUTORS_MARKER, contributors)


def normalize_authors(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError('authors должен быть списком имён или объектов name/role')
    result = []
    for entry in value:
        item = {'name': entry} if isinstance(entry, str) else entry
        if (not isinstance(item, dict) or not isinstance(item.get('name'), str)
                or not item['name'].strip()
                or ('role' in item and (not isinstance(item['role'], str) or not item['role'].strip()))):
            raise ValueError('Автор должен иметь непустое имя и необязательную роль')
        result.append({'name': item['name'].strip(), **({'role': item['role'].strip()} if 'role' in item else {})})
    return result


def authors_text(value):
    authors = normalize_authors(value)
    if not authors:
        return ''
    if any(a.get('role') for a in authors):
        return 'Авторство: ' + '; '.join((a['role'] + ' — ' if a.get('role') else '') + a['name'] for a in authors)
    return ('Автор: ' if len(authors) == 1 else 'Авторы: ') + ', '.join(a['name'] for a in authors)


def authors_html(value):
    text = authors_text(value)
    return '<p class="authors">' + escape(text) + '</p>' if text else ''


def authors_markdown(value):
    # Имена и роли являются текстом, а не Markdown/HTML автора материала.
    return authors_text(value).translate(str.maketrans({c: '\\' + c for c in '\\`*_{}[]<>()#!|'}))
