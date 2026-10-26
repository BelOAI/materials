"""Общие подписи авторов в метаданных, HTML и ноутбуках."""
from html import escape
import re

CONTRIBUTORS_MARKER = '<!-- handbook-contributors -->'
AUTHORS_MARKER = '<!-- handbook-authors -->'


def expand_authors(source, authors, *, html=False):
    """Вставить подпись из метаданных в указанное автором место текста."""
    if AUTHORS_MARKER not in source:
        return source
    if not normalize_authors(authors):
        raise ValueError('Для handbook-authors необходимо указать authors в метаданных')
    return source.replace(AUTHORS_MARKER, authors_html(authors) if html else authors_markdown(authors))


def normalize_contributors(value):
    people = normalize_authors(value)
    for original, person in zip(value or [], people):
        if isinstance(original, dict) and 'github' in original:
            username = original['github']
            if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', username):
                raise ValueError('github должен содержать имя пользователя без @')
            person['github'] = username
    return people


def contributors_markdown(value):
    rows = []
    for person in normalize_contributors(value):
        label = authors_markdown([person]).removeprefix('Автор: ')
        if person.get('github'):
            label = f'[{label} (@{person["github"]})](https://github.com/{person["github"]})'
        rows.append('- ' + label)
    return '\n'.join(rows)


def expand_contributors(source, contributors):
    """Общий список авторов внутри Markdown учебника для HTML и PDF."""
    if CONTRIBUTORS_MARKER not in source:
        return source
    if not normalize_contributors(contributors):
        raise ValueError('Для handbook-contributors необходимо указать contributors в метаданных')
    return source.replace(CONTRIBUTORS_MARKER, contributors_markdown(contributors))


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
    return ('Автор: ' if len(authors) == 1 else 'Авторы: ') + ', '.join(
        a['name'] + (f' ({a["role"]})' if a.get('role') else '') for a in authors)


def authors_html(value):
    text = authors_text(value)
    return '<p class="authors">' + escape(text) + '</p>' if text else ''


def authors_markdown(value):
    # Имена и роли являются текстом, а не Markdown/HTML автора материала.
    return authors_text(value).translate(str.maketrans({c: '\\' + c for c in '\\`*_{}[]<>()#!|'}))
