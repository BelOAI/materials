#!/usr/bin/env python3
"""Обновить или проверить встроенное оформление SVG и автономных генераторов."""
import argparse
from pathlib import Path
import sys

from repo_paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / 'utils/illustrations'))
from style import BEGIN, STYLE_ID, normalize_generator, normalize_svg


def synchronize(root, write=False):
    changed = []
    for path in sorted((root / 'handbooks').rglob('*')):
        if path.suffix not in ('.svg', '.py') or any(part.startswith(('.', '_')) for part in path.relative_to(root / 'handbooks').parts):
            continue
        source = path.read_text(encoding='utf-8')
        if path.suffix == '.svg':
            if f'id="{STYLE_ID}"' not in source:
                raise ValueError(f'{path}: нет отмеченного блока оформления')
            result = normalize_svg(source)
        elif BEGIN in source:
            result = normalize_generator(source)
        else:
            continue
        if result != source:
            changed.append(path.relative_to(root).as_posix())
            if write:
                path.write_text(result, encoding='utf-8')
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        changed = synchronize(REPO_ROOT, write=args.write)
    except ValueError as error:
        parser.exit(1, str(error) + '\n')
    if args.check and changed:
        parser.exit(1, 'Нужно обновить оформление:\n' + '\n'.join(changed) + '\n')
    print(f'Оформление: {len(changed)} обновлений' if args.write else 'Оформление актуально')
