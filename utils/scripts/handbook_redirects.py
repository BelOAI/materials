"""Совместимость прежних URL /handbook/ с каноническим /handbooks/."""
import json
import posixpath
import shutil
from html import escape
from pathlib import Path
from urllib.parse import quote


def publish_legacy_handbook(output: Path) -> None:
    canonical = output / 'handbooks'
    legacy = output / 'handbook'
    shutil.rmtree(legacy, ignore_errors=True)
    if not canonical.is_dir():
        return
    for source in canonical.rglob('*'):
        if not source.is_file():
            continue
        relative = source.relative_to(canonical)
        destination = legacy / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix.lower() != '.html':
            shutil.copyfile(source, destination)
            continue
        target_path = source.parent if source.name == 'index.html' else source
        target = posixpath.relpath(target_path, destination.parent)
        if source.name == 'index.html':
            target += '/'
        target = quote(target, safe='/')
        write_redirect(destination, target)


def write_redirect(destination: Path, target: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    html_target = escape(target, quote=True)
    destination.write_text(
        '<!doctype html><html lang="ru"><head><meta charset="utf-8">'
        '<meta name="robots" content="noindex, nofollow">'
        f'<link rel="canonical" href="{html_target}">'
        f'<meta http-equiv="refresh" content="0;url={html_target}">'
        '<title>Страница переехала</title>'
        '<script>const target=new URL(' + json.dumps(target) + ',location.href);'
        'target.search=location.search;target.hash=location.hash;'
        'location.replace(target.href);</script></head><body>'
        f'<p>Страница переехала. <a href="{html_target}">Открыть новый адрес</a>.</p>'
        '</body></html>\n', encoding='utf-8',
    )
