"""Проверяемый кэш файлов сборки; удаление кэша всегда безопасно."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'.aux', '.log', '.out', '.toc', '.nav', '.snm', '.vrb', '.bbl', '.blg',
             '.bcf', '.fls', '.fdb_latexmk', '.xdv', '.lof', '.lot'}


def source_files(folder: Path):
    if not folder.exists():
        return []
    return [p for p in sorted(folder.rglob('*')) if p.is_file()
            and p.name != 'main.pdf' and p.suffix not in GENERATED
            and not p.name.endswith(('.synctex.gz', '.run.xml', '-blx.bib'))
            and not any(part in {'__pycache__', 'node_modules', '.cache', '.git'}
                        for part in p.relative_to(folder).parts)]


def fingerprint(paths, context=''):
    digest = hashlib.sha256()
    environment = (os.environ.get('BUILD_ENV_ID', ''), sys.version, platform.platform(),
                   sorted((d.metadata['Name'], d.version) for d in importlib.metadata.distributions()))
    digest.update(json.dumps(['v1', context, environment], sort_keys=True).encode())
    for path in sorted(set(map(Path, [*paths, Path(__file__)]))):
        digest.update(str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).encode())
        if path.is_symlink():
            digest.update(str(path.resolve()).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b'missing')
    for tool in ('pdflatex', 'pdfinfo', 'pdftoppm', 'jupyter'):
        binary = shutil.which(tool)
        digest.update((tool + str(binary)).encode())
        if binary:
            digest.update(hashlib.sha256(Path(binary).read_bytes()).digest())
    return digest.hexdigest()


class Cache:
    def __init__(self, namespace, key):
        self.path = Path(os.environ.get('BUILD_CACHE_DIR', str(ROOT / '.cache/build'))) / namespace / key
        self.disabled = os.environ.get('BUILD_CACHE_DISABLE') == '1'

    def restore(self, output: Path):
        if self.disabled:
            return False
        try:
            manifest_bytes = (self.path / 'manifest.json').read_bytes()
            if hashlib.sha256(manifest_bytes).hexdigest() != (self.path / 'manifest.sha256').read_text():
                raise ValueError('manifest checksum')
            manifest = json.loads(manifest_bytes)
            if not isinstance(manifest, dict):
                raise ValueError('manifest')
            for name, checksum in manifest.items():
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts or name == '.':
                    raise ValueError('path')
                data = (self.path / 'files' / relative).read_bytes()
                if hashlib.sha256(data).hexdigest() != checksum:
                    raise ValueError('checksum')
            for name in manifest:
                dest = output / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.path / 'files' / name, dest)
        except (OSError, ValueError, TypeError):
            print(f'CACHE MISS {self.path.parent.name}/{self.path.name[:12]}', flush=True)
            return False
        print(f'CACHE HIT {self.path.parent.name}/{self.path.name[:12]}', flush=True)
        return True

    def save(self, output: Path, paths):
        if self.disabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=self.path.parent) as folder:
            temp = Path(folder) / 'entry'
            temp.mkdir()
            manifest = {}
            for path in sorted(set(paths)):
                if not path.is_file():
                    continue
                name = str(path.relative_to(output))
                dest = temp / 'files' / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, dest)
                manifest[name] = hashlib.sha256(dest.read_bytes()).hexdigest()
            manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
            (temp / 'manifest.json').write_bytes(manifest_bytes)
            (temp / 'manifest.sha256').write_text(hashlib.sha256(manifest_bytes).hexdigest())
            # Два процесса могут получить один ключ; готовая запись уже проверяема.
            if self.path.exists():
                shutil.rmtree(self.path, ignore_errors=True)
            try:
                temp.rename(self.path)
            except OSError:
                if not self.path.is_dir():
                    raise
