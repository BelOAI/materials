#!/usr/bin/env python3
"""Объединение main, dev и активных PR без исполнения кода артефактов."""
import io
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlsplit
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


def api(path, binary=False, *, method=None, data=None):
    command = ['gh', 'api', path]
    if method:
        command += ['--method', method]
    if data is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(data).encode() if data is not None else None,
                            capture_output=True, check=True)
    return result.stdout if binary else json.loads(result.stdout)


def pages(path, key):
    page = 1
    while True:
        result = api(f'{path}{"&" if "?" in path else "?"}per_page=100&page={page}')
        result = result[key] if key else result
        yield from result
        if len(result) < 100:
            return
        page += 1


def latest_artifact(repo, branch):
    runs = pages(f'repos/{repo}/actions/workflows/presentations.yml/runs?branch={quote(branch, safe="")}&status=success', 'workflow_runs')
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


def mark_preview(root, label="dev"):
    for path in root.rglob('*.html'):
        html = path.read_text(encoding='utf-8')
        html = html.replace('</head>', '<meta name="robots" content="noindex, nofollow" /></head>')
        # Встроенные стили нужны и для standalone HTML nbconvert.
        banner = ('<aside aria-label="Тестовая версия" style="padding:12px;background:#fff3cd;'
                  f'color:#332701;text-align:center">Тестовая версия {escape(label)} · '
                  '<a href="https://materials.beloai.by/">Основной сайт</a></aside>')
        html = re.sub(r'(<body\b[^>]*>)', lambda m: m[1] + banner, html, count=1)
        path.write_text(html, encoding='utf-8')


def preview_artifacts(repo):
    """Reconcile live PRs rather than trusting the event that woke the publisher."""
    branches = {b['name'] for b in pages(f'repos/{repo}/branches', None)}
    pulls = [pr for pr in pages(f'repos/{repo}/pulls?state=open', None)
             if pr['head']['repo'] and pr['head']['repo']['full_name'] == repo
             and pr['head']['ref'] in branches - {'main', 'dev'}
             and pr['base']['ref'] in {'main', 'dev'}]
    if not pulls:
        return {}
    runs = list(pages(f'repos/{repo}/actions/workflows/presentations.yml/runs?event=pull_request&status=success', 'workflow_runs'))
    selected = {}
    for pr in pulls:
        number = pr['number']
        for run in runs:
            if run['head_repository']['full_name'] != repo or run['head_branch'] != pr['head']['ref']:
                continue
            # GitHub may return an empty pull_requests array (also after force
            # pushes). The PR-specific artifact name and provenance still bind
            # that successful run to this PR and its internal source branch.
            if run.get('pull_requests') and not any(p['number'] == number for p in run['pull_requests']):
                continue
            expected = f'site-pr-{number}-{run["head_sha"]}'
            artifact = next((a for a in pages(f'repos/{repo}/actions/runs/{run["id"]}/artifacts', 'artifacts')
                             if a['name'] == expected and not a['expired']), None)
            if artifact:
                selected[f'pr-{number}'] = (run, artifact)
                break
    return selected


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if value and name in {'href', 'src', 'poster'}:
                self.links.append(value)


def validate_site(root, max_bytes=1_000_000_000, *, environment_roots=()):
    """Validate the actual generated links; no hardcoded course contents."""
    size = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if size > max_bytes:
        raise ValueError(f'Сайт превышает лимит Pages: {size} байт')
    scopes = sorted(((root / relative).resolve() for relative in environment_roots if relative),
                    key=lambda path: len(path.parts), reverse=True)
    for source in root.rglob('*.html'):
        scope = next((path for path in scopes if source.resolve().is_relative_to(path)), root.resolve())
        parser = Links()
        parser.feed(source.read_text(encoding='utf-8'))
        for href in parser.links:
            url = urlsplit(href)
            if url.scheme or url.netloc or not url.path:
                continue
            target = (root / unquote(url.path).lstrip('/') if url.path.startswith('/')
                      else source.parent / unquote(url.path)).resolve()
            if target.is_dir():
                target /= 'index.html'
            if not target.is_relative_to(scope) or not target.is_file():
                raise ValueError(f'Нерабочая ссылка: {source.relative_to(root)} → {href}')


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
    selected.update(preview_artifacts(repo))
    output = Path('_pages')
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / 'staging'
        root.mkdir()
        metadata = {}
        for branch, selection in selected.items():
            if selection is None:
                continue
            run, artifact = selection
            relative = '' if branch == 'main' else ('dev/' if branch == 'dev' else f'test/{branch}/')
            destination = root / relative
            if branch != 'main' and destination.exists():
                raise ValueError(f'Путь {relative} зарезервирован для тестовой версии')
            destination.mkdir(parents=True, exist_ok=True)
            extract(api(f'repos/{repo}/actions/artifacts/{artifact["id"]}/zip', binary=True), destination)
            if branch == 'main' and any((root / name).exists() for name in ('dev', 'test')):
                raise ValueError('Пути dev/ и test/ зарезервированы для тестовых версий')
            metadata[branch] = {'sha': run['head_sha'], 'run': run['html_url'],
                                'run_id': run.get('id'), 'source': run.get('head_branch', branch), 'root': relative}
            if branch.startswith('pr-'):
                provenance = json.loads((destination / 'build-source.json').read_text())
                if (provenance['head_sha'] != run['head_sha'] or provenance['run_id'] != run['id']
                        or provenance['pr'] != int(branch[3:])):
                    raise ValueError('Артефакт PR не соответствует сборке')
                merge = api(f'repos/{repo}/commits/{provenance["merge_sha"]}')
                if run['head_sha'] not in [p['sha'] for p in merge['parents']]:
                    raise ValueError('Merge commit не содержит исходный commit PR')
                metadata[branch].update(pr=int(branch[3:]), merge_sha=provenance['merge_sha'])
            if branch != 'main':
                mark_preview(destination, branch)
        (root / 'build-info.json').write_text(json.dumps(metadata, indent=2) + '\n')
        validate_site(root, environment_roots=[item['root'] for item in metadata.values()])
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(root, output)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as stream:
            for branch, item in metadata.items():
                stream.write(f'- [{branch}](https://materials.beloai.by/{item["root"]}): [{item["sha"][:12]}]({item["run"]})\n')


if __name__ == '__main__':
    main()
