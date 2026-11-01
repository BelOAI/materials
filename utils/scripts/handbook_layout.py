"""Publishing layout, measured spacing and source-preserving object placement."""
from copy import deepcopy
import math
from pathlib import Path
import re

import yaml


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


def words(value):
    return ' '.join(n['c'] if n['t'] == 'Str' else n['c'][1] for n in nodes(value)
                    if n.get('t') in ('Str', 'Code', 'Math'))


def column_widths(table):
    """Estimate readable line lengths, giving numeric columns compact widths."""
    count = len(table['c'][2])
    rows = []
    # Pandoc rows have attributes and a list of six-field cells.
    for node in _lists(table['c'][3:]):
        if (len(node) == 2 and isinstance(node[1], list) and node[1]
                and all(isinstance(c, list) and len(c) == 5 and isinstance(c[1], dict)
                        and c[1].get('t', '').startswith('Align') for c in node[1])):
            rows.append([words(cell[4]) for cell in node[1]])
    weights = []
    for index in range(count):
        values = [row[index] for row in rows if len(row) == count]
        body = values[1:]
        numeric = bool(body) and sum(bool(re.fullmatch(r'[\d\s.,−+%–—/-]+', s)) for s in body) >= .8 * len(body)
        if numeric:
            weight = max(6, min(12, max((len(w) for w in (values[0] if values else '').split()), default=6)))
        else:
            lengths = sorted(min(42, max(6, len(s))) for s in values)
            weight = lengths[min(len(lengths) - 1, math.floor(.8 * len(lengths)))] if lengths else 12
        weights.append(weight)
    floor = min(.09, .5 / max(1, count))
    return [floor + (1 - count * floor) * weight / sum(weights) for weight in weights]


def _lists(value):
    if isinstance(value, list):
        yield value
        for child in value:
            yield from _lists(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from _lists(child)


def load_layout(path):
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict) or set(data) != {'objects'} or not isinstance(data['objects'], dict):
        raise ValueError('print-layout.yml: ожидается objects')
    for key, entry in data['objects'].items():
        if not isinstance(key, str) or not isinstance(entry, dict) or set(entry) - {'widths', 'break_before', 'space_before_pt'}:
            raise ValueError(f'Неверная настройка макета: {key}')
        if 'widths' in entry:
            widths = entry['widths']
            if not isinstance(widths, list) or not widths or any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0 for n in widths) or abs(sum(widths) - 1) > .001:
                raise ValueError(f'{key}: widths должны быть положительными и давать сумму 1')
        if 'break_before' in entry and not isinstance(entry['break_before'], bool):
            raise ValueError(f'{key}: break_before должен быть boolean')
        if 'space_before_pt' in entry and (type(entry['space_before_pt']) not in (int, float) or not 0 <= entry['space_before_pt'] <= 72):
            raise ValueError(f'{key}: space_before_pt должен быть от 0 до 72')
    return data['objects']


def layout_part(ast, identifier, folder, overrides):
    from PIL import Image
    result = deepcopy(ast)
    counters = {'table': 0, 'figure': 0}
    for node in sorted(list(nodes(result)), key=lambda n: n.get('t') != 'Image'):
        if node.get('t') == 'Header':
            node['c'][1][1].append('handbook-editorial-heading')
        kind = 'table' if node.get('t') == 'Table' else 'figure' if node.get('t') == 'Div' and 'handbook-figure' in node['c'][0][1] else None
        if kind:
            counters[kind] += 1
            key = f'{identifier}/{kind}:{counters[kind]}'
            entry = overrides.get(key, {})
            if kind == 'table':
                widths = entry.get('widths', column_widths(node))
                if len(widths) != len(node['c'][2]):
                    raise ValueError(f'{key}: число ширин не совпадает с числом колонок')
                for spec, width in zip(node['c'][2], widths):
                    spec[1] = {'t': 'ColWidth', 'c': width}
            # Break and spacing are attached to the object as a surrounding Div.
            prefix = []
            if entry.get('break_before'):
                prefix.append({'t': 'RawBlock', 'c': ['latex', r'\clearpage']})
            if entry.get('space_before_pt'):
                prefix.append({'t': 'RawBlock', 'c': ['latex', r'\par\vspace{' + str(entry['space_before_pt']) + 'pt}']})
            if prefix:
                original = deepcopy(node)
                node.clear()
                node.update(t='Div', c=[['', ['handbook-layout-object'], []], prefix + [original]])
        if node.get('t') == 'Image':
            path = (folder / node['c'][2][0]).resolve()
            if path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
                with Image.open(path) as image:
                    width_mm = min(130, image.width / 300 * 25.4)
                attrs = node['c'][0][2]
                attrs[:] = [pair for pair in attrs if pair[0] not in ('width', 'height')]
                attrs.append(['width', f'{width_mm:.4f}mm'])
    blocks, grouped, index = result.get('blocks', []), [], 0
    while index < len(blocks):
        block = blocks[index]
        following = blocks[index + 1] if index + 1 < len(blocks) else {}
        if (block.get('t') == 'Para' and words(block).rstrip().endswith(':')
                and following.get('t') in ('BulletList', 'OrderedList', 'CodeBlock', 'Table')):
            lines = min(12, math.ceil(len(words(block)) / 60) + 3)
            grouped.append({'t': 'RawBlock', 'c': ['latex', r'\Needspace{' + str(lines) + r'\baselineskip}']})
        if (block.get('t') == 'Para' and len(block['c']) == 1 and block['c'][0].get('t') == 'Strong'
                and len(words(block)) < 80 and following.get('t') == 'Para'):
            grouped.append({'t': 'RawBlock', 'c': ['latex', r'\Needspace{4\baselineskip}']})
        grouped.append(block)
        index += 1
    if 'blocks' in result:
        result['blocks'] = grouped
    return result
