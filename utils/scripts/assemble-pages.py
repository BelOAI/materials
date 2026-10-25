#!/usr/bin/env python3
"""Объединение последних успешных сборок main/dev без исполнения их кода."""
import io
import json
import os
import re
import urllib.error
import urllib.request
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path


def api(path, binary=False):
    result = subprocess.run(['gh', 'api', path], capture_output=True, check=True)
    return result.stdout if binary else json.loads(result.stdout)


def pages(path, key):
    page = 1
    while True:
        result = api(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')[key]
        yield from result
        if len(result) < 100:
            return
        page += 1


def latest_artifact(repo, branch):
    runs = pages(f'repos/{repo}/actions/workflows/presentations.yml/runs?branch={branch}&status=success', 'workflow_runs')
    run = next((r for r in runs if r['event'] in ('push', 'workflow_dispatch')
                and r['head_branch'] == branch and r['head_repository']['full_name'] == repo), None)
    if run is None:
        if branch == 'dev':
            return None
        raise ValueError('Нет успешной сборки main. Запустите Presentations для main вручную.')
    expected = f'site-{branch}-{run["head_sha"]}'
    artifacts = list(pages(f'repos/{repo}/actions/runs/{run["id"]}/artifacts', 'artifacts'))
    artifact = next((a for a in artifacts if a['name'] == expected and not a['expired']), None)
    if artifact is None:
        raise ValueError(f'Артефакт {branch} отсутствует или истёк. Запустите Presentations для {branch} вручную.')
    return run, artifact


def extract(data, output):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            path = Path(entry.filename)
            mode = entry.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(mode):
                raise ValueError(f'Небезопасный путь в артефакте: {entry.filename}')
        archive.extractall(output)
    if not (output / 'index.html').is_file() or not (output / 'materials.json').is_file():
        raise ValueError('Неполный артефакт сайта')


def mark_preview(root):
    for path in root.rglob('*.html'):
        html = path.read_text(encoding='utf-8')
        html = html.replace('</head>', '<meta name="robots" content="noindex, nofollow" /></head>')
        # Встроенные стили нужны и для standalone HTML nbconvert.
        banner = ('<aside aria-label="Тестовая версия" style="padding:12px;background:#fff3cd;'
                  'color:#332701;text-align:center">Тестовая версия dev · '
                  '<a href="https://materials.beloai.by/">Основной сайт</a></aside>')
        html = re.sub(r'(<body\b[^>]*>)', lambda m: m[1] + banner, html, count=1)
        path.write_text(html, encoding='utf-8')


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    selected = {branch: latest_artifact(repo, branch) for branch in ('main', 'dev')}
    if selected['dev'] is None:
        # Сайт хранит факт публикации dev даже после удаления истории Actions.
        try:
            with urllib.request.urlopen('https://materials.beloai.by/build-info.json', timeout=30) as response:
                previous = json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            error.close()
            previous = {}
        if 'dev' in previous:
            raise ValueError('Опубликованный dev нельзя восстановить. Запустите Presentations для dev.')
    output = Path('_pages')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / 'staging'
        root.mkdir()
        metadata = {}
        for branch, selection in selected.items():
            if selection is None:
                continue
            run, artifact = selection
            destination = root if branch == 'main' else root / 'dev'
            if branch == 'dev' and destination.exists():
                raise ValueError('Путь dev/ зарезервирован для тестовой версии')
            destination.mkdir(parents=True, exist_ok=True)
            extract(api(f'repos/{repo}/actions/artifacts/{artifact["id"]}/zip', binary=True), destination)
            metadata[branch] = {'sha': run['head_sha'], 'run': run['html_url']}
            if branch == 'dev':
                mark_preview(destination)
        (root / 'build-info.json').write_text(json.dumps(metadata, indent=2) + '\n')
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(root, output)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            for branch, item in metadata.items():
                stream.write(f'- {branch}: [{item["sha"][:12]}]({item["run"]})\n')


if __name__ == '__main__':
    main()
