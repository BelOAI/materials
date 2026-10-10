#!/usr/bin/env python3
"""Выбор, проверка и публикация основного PDF занятия."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from meta_parser import get_flat, parse_meta

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_session(session: Path) -> None:
    session = session.resolve()
    if not session.is_dir():
        raise ValueError('Папка занятия не найдена.')
    if session.parent not in [REPO_ROOT / kind for kind in ('lectures', 'practices', 'assignments')]:
        raise ValueError('Папка занятия должна находиться в lectures/, practices/ или assignments/.')
    slug = f'{session.parent.name}/{session.name}'
    site = REPO_ROOT / '_site'
    target = site / 'pdfs' / f'{slug}.pdf'
    thumb = site / 'thumbs' / f'{slug}.png'
    # Старые результаты не должны маскировать удалённый или неверный источник.
    target.unlink(missing_ok=True)
    thumb.unlink(missing_ok=True)
    for folder in (site / 'materials' / slug, site / 'thumbs' / slug):
        if folder.is_dir():
            shutil.rmtree(folder)
    meta_path = session / 'meta.yaml'
    meta = parse_meta(meta_path) if meta_path.is_file() else {}
    source = None
    if 'pdf' in meta:
        value = get_flat(meta, 'pdf').strip()
        if not value or Path(value).is_absolute():
            raise ValueError('Поле pdf должно содержать относительный путь к PDF внутри занятия.')
        source = (session / value).resolve()
        if not source.is_relative_to(session):
            raise ValueError('Путь pdf выходит за пределы папки занятия.')
        if Path(value).name.lower() == 'main.pdf' or source.name.lower() == 'main.pdf':
            raise ValueError('Имя main.pdf зарезервировано для TeX; переименуйте исходный PDF.')
        if source.suffix.lower() != '.pdf' or not source.is_file():
            raise ValueError(f'Не найден исходный PDF: {value}')
        if not shutil.which('pdfinfo'):
            raise ValueError('Для проверки готового PDF требуется pdfinfo из Poppler.')
        check = subprocess.run(['pdfinfo', str(source)], capture_output=True, text=True)
        info = dict(line.split(':', 1) for line in check.stdout.splitlines() if ':' in line)
        if check.returncode or int(info.get('Pages', '0').strip()) < 1:
            raise ValueError(f'Не удалось прочитать PDF: {value}')
        if info.get('Encrypted', '').strip().startswith('yes'):
            raise ValueError(f'PDF защищён шифрованием; сохраните незашифрованную копию: {value}')
    elif (session / 'main.tex').is_file():
        subprocess.run([str(REPO_ROOT / 'scripts/build-presentation.sh'), str(session), '--local'], check=True)
        source = session / 'main.pdf'
    if source:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        print(f'Опубликован PDF: {target}', flush=True)
        if shutil.which('pdftoppm'):
            thumb.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(['pdftoppm', '-scale-to', '1280', '-png', '-f', '1', '-l', '1', '-singlefile', str(target), str(thumb.with_suffix(''))])
            if result.returncode:
                thumb.unlink(missing_ok=True)
                print(f'Предупреждение: не удалось создать превью {slug}', file=sys.stderr)
        else:
            print(f'Предупреждение: pdftoppm не найден, PDF {slug} опубликован без превью.', file=sys.stderr)
    subprocess.run([str(REPO_ROOT / 'scripts/build-materials.sh'), str(session)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        build_session(args.directory)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'Ошибка сборки {args.directory}: {error}', file=sys.stderr)
        sys.exit(1)
