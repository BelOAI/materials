"""Выходные сведения издательского макета; пользовательский текст остаётся в AST Pandoc."""
from pathlib import Path
import re
from urllib.parse import urlsplit

from handbook_catalog import local_file, nonempty, read_yaml


CLASSIFIERS = {'udk': 'УДК', 'bbk': 'ББК', 'author_mark': 'Авторский знак'}
OPTIONAL = {'publisher': 'Издатель', 'place': 'Место издания', 'year': 'Год издания',
            'isbn': 'ISBN', 'reviewers': 'Рецензенты', 'approval': 'Сведения об утверждении',
            'production': 'Выпускные сведения'}


def read_publication(folder: Path) -> dict:
    path = local_file(folder, 'publication.yml')
    try:
        data = read_yaml(path)
        required = {'kind', 'status', 'audience', 'annotation', 'edition', 'classification'}
        if not isinstance(data, dict) or required - data.keys() or data.keys() - required - OPTIONAL.keys():
            raise ValueError('Необходимы kind, status, audience, annotation, edition, classification; неизвестные поля запрещены')
        if any(not nonempty(data[key]) for key in required - {'classification'}):
            raise ValueError('Вид, статус, аудитория, аннотация и редакция должны быть непустыми строками')
        if data['status'] != 'Издательский макет':
            raise ValueError('Профиль поддерживает статус «Издательский макет»')
        indices = data['classification']
        if not isinstance(indices, dict) or indices.keys() != CLASSIFIERS.keys():
            raise ValueError('classification: необходимы udk, bbk, author_mark')
        for key, entry in indices.items():
            if (not isinstance(entry, dict) or set(entry) != {'value', 'status', 'rationale', 'sources'}
                    or not all(nonempty(entry.get(field)) for field in ('value', 'rationale'))
                    or not isinstance(entry.get('status'), str) or entry['status'] not in {'preliminary', 'verified'}
                    or not isinstance(entry.get('sources'), list) or not entry['sources']
                    or any(not isinstance(url, str) or urlsplit(url).scheme not in {'https', 'http'}
                           or not urlsplit(url).netloc for url in entry['sources'])):
                raise ValueError(f'classification.{key}: нужны value, status (preliminary/verified), rationale и sources (URL)')
        for key in OPTIONAL.keys() & data.keys():
            entry = data[key]
            if (not isinstance(entry, dict) or set(entry) != {'value', 'source'}
                    or not all(nonempty(entry.get(field)) for field in ('value', 'source'))):
                raise ValueError(f'{key}: нужны строки value и source с подтверждением реквизита')
        if 'year' in data and not re.fullmatch(r'[1-9][0-9]{3}', data['year']['value']):
            raise ValueError('year.value: ожидается четырёхзначный год строкой')
        if 'isbn' in data:
            isbn = data['isbn']['value'].replace('-', '').replace(' ', '')
            if (not re.fullmatch(r'97[89][0-9]{10}', isbn)
                    or sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(isbn)) % 10):
                raise ValueError('isbn.value: неверный ISBN-13')
        return data
    except ValueError as error:
        raise ValueError(f'{path}: {error}') from error


def para(value):
    return {'t': 'Para', 'c': [{'t': 'Str', 'c': value}]}


def raw(value):
    return {'t': 'RawBlock', 'c': ['latex', value]}


def titlepage(data, title):
    blocks = [raw(r'\begin{handbooktitlepage}'),
              raw(r'\begingroup\fontsize{22}{26}\selectfont\bfseries'), para(title),
              raw(r'\par\endgroup\vspace{8mm}'), para(data['kind']),
              raw(r'\vspace{3mm}'), para(data['audience']),
              raw(r'\vspace{3mm}'), para(data['status']), raw(r'\vfill')]
    for key in ('place', 'publisher', 'year'):
        if key in data:
            blocks.append(para(data[key]['value']))
    blocks.append(raw(r'\end{handbooktitlepage}'))
    return blocks


def frontmatter(data, title):
    blocks = titlepage(data, title) + [raw(r'\begin{handbooktitleback}')]
    indices = []
    for key, label in CLASSIFIERS.items():
        if indices:
            indices.append({'t': 'LineBreak'})
        indices.append({'t': 'Str', 'c': f'{label} {data["classification"][key]["value"]}'})
    blocks.append({'t': 'Para', 'c': indices})
    if any(entry['status'] == 'preliminary' for entry in data['classification'].values()):
        blocks.extend([raw(r'\begingroup\small'),
                       para('Классификационные данные предварительные; требуется проверка библиографом.'),
                       raw(r'\par\endgroup')])
    blocks.extend([raw(r'\bigskip'), para(title + '. ' + data['kind'] + '.'),
                   para(data['annotation']), para(data['edition'])])
    for key in ('reviewers', 'approval', 'isbn'):
        if key in data:
            blocks.append(para(OPTIONAL[key] + ': ' + data[key]['value']))
    blocks.extend([raw(r'\vfill\begingroup\small'), para('© Авторы BelOAI. Материалы распространяются по лицензии CC BY 4.0.'),
                   para('Имена авторов и их роли приведены при соответствующих разделах. '
                        'Список участников проекта не является реестром правообладателей.'),
                   raw(r'\par\endgroup\end{handbooktitleback}')])
    return blocks


def endmatter(data, title, revision, site_url):
    version, date = revision
    blocks = [raw(r'\begin{handbookpublicationpage}'),
              {'t': 'Header', 'c': [1, ['publication-details', ['unnumbered'], []],
                                   [{'t': 'Str', 'c': 'Сведения о макете'}]]},
              para(title), para(data['kind']), para(data['status']), para(data['edition']),
              para(data['audience'])]
    if any(key in data for key in ('place', 'publisher', 'year', 'production')):
        blocks.append(raw(r'\bigskip'))
    for key in ('place', 'publisher', 'year', 'production'):
        if key in data:
            blocks.append(para(OPTIONAL[key] + ': ' + data[key]['value']))
    blocks.extend([raw(r'\bigskip'), para('Редакция исходников: ' + version)])
    if date:
        blocks.append(para('Дата исходников: ' + date))
    for label, url in [('Онлайн-учебник', site_url), ('Лицензия CC BY 4.0', 'https://creativecommons.org/licenses/by/4.0/')]:
        blocks.append({'t': 'Para', 'c': [{'t': 'Link', 'c': [['', [], []],
                       [{'t': 'Str', 'c': label}], [url, '']]}]})
    blocks.extend([para('Формат макета: 170 × 240 мм. Электронный файл PDF. Для чтения требуется программа просмотра PDF.'),
                   para('Макет подготовлен для редакционной работы. Официальное утверждение и полное '
                        'соответствие нормативным требованиям не заявлены.'),
                   raw(r'\end{handbookpublicationpage}')])
    return blocks
