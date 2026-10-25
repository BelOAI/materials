"""Синхронизация учебных ноутбуков с Markdown уроков: --write или --check."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from repo_paths import REPO_ROOT as ROOT


def render_notebook(title: str, text: str, assets: Path | None = None,
                    authors: list[str] | None = None) -> dict:
    solutions = []
    def move(match):
        solutions.append(match.group(1).strip())
        return ''
    text = re.sub(r'<details>\s*<summary>Решение</summary>\s*(.*?)\s*</details>', move, text, flags=re.S)
    text += '\n\n## Решения задач\n\n' + ''.join(f'### Задача {i}\n\n{solution}\n\n' for i, solution in enumerate(solutions, 1))
    cells = []
    def markdown(value):
        if value.strip():
            attachments = {}
            def embed(match):
                if assets is None:
                    return match[0]
                path = (assets / match[2]).resolve()
                if not path.is_relative_to(assets.resolve()) or not path.is_file() or path.suffix != '.svg':
                    return match[0]
                name = path.name
                attachments[name] = {'image/svg+xml': path.read_text(encoding='utf-8')}
                return f'![{match[1]}](attachment:{name})'
            value = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', embed, value)
            cell = {'cell_type': 'markdown', 'metadata': {}, 'source': value.strip().splitlines(keepends=True)}
            if attachments:
                cell['attachments'] = attachments
            cells.append(cell)
    author_line = ', '.join(authors or ['Авторы BelOAI'])
    if authors and author_line != 'Авторы BelOAI':
        author_line = ('Автор: ' if len(authors) == 1 else 'Авторы: ') + author_line
    markdown(f'# {title}\n\n{author_line}. CC BY 4.0.\n\nВыполняйте ячейки сверху вниз. Сначала решите задачи, затем обратитесь к решениям.')
    cursor = 0
    for match in re.finditer(r'^```python\n(.*?)^```\s*$', text, re.M | re.S):
        markdown(text[cursor:match.start()])
        cells.append({'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': (match.group(1).rstrip() + '\n').splitlines(keepends=True)})
        cursor = match.end()
    markdown(text[cursor:])
    for index, cell in enumerate(cells):
        cell['id'] = f'cell-{index:03}'
    return {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}, 'language_info': {'name': 'python', 'version': '3.14'}}, 'nbformat': 4, 'nbformat_minor': 5}


def synchronize(root: Path, write: bool = False) -> list[str]:
    from handbook_site import load_handbook
    book = load_handbook(root, allow_missing_synced=True)
    stale = []
    for item in book['_lessons'].values():
        if item['status'] == 'planned' or not item.get('sync_notebook'):
            continue
        resources = [r for r in item.get('resources', []) if r['path'] == 'notebook.ipynb']
        if not resources:
            raise ValueError(f"{item['id']}: sync_notebook требует ресурс notebook.ipynb")
        expected = render_notebook(item['title'], item['_content'].read_text(), assets=item['_folder'],
                                   authors=item['authors'])
        destination = item['_folder'] / 'notebook.ipynb'
        if not destination.is_file() or json.loads(destination.read_text()) != expected:
            stale.append(item['id'])
            if write:
                destination.write_text(json.dumps(expected, ensure_ascii=False, indent=1) + '\n')
    return stale


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    stale = synchronize(ROOT, write=args.write)
    if args.check and stale:
        parser.exit(1, 'Не синхронизированы ноутбуки: ' + ', '.join(stale) + '\n')
