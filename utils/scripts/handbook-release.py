#!/usr/bin/env python3
"""Валидация тегов и публикация PDF из доверенного workflow."""
import datetime
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location('assemble_pages', Path(__file__).with_name('assemble-pages.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
api, pages = module.api, module.pages
PDF_ASSETS = ('beloai-ml-handbook.pdf', 'beloai-ml-handbook-belarus-textbook.pdf')
ASSETS = (*PDF_ASSETS, 'SHA256SUMS')


def version(tag):
    match = re.fullmatch(r'v(\d{4})\.(\d{2})\.(\d{2})(?:\.([1-9]\d*))?', tag, flags=re.ASCII)
    if not match:
        raise ValueError(f'Недопустимый release-тег: {tag}')
    year, month, day, revision = match.groups()
    date = datetime.date(int(year), int(month), int(day))
    return date, int(revision or 0)


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def validate_ref(ref, sha):
    if ref == 'refs/heads/main':
        return 'main-preview'
    if not ref.startswith('refs/tags/'):
        raise ValueError('Выпуск возможен только из main или release-тега')
    tag = ref.removeprefix('refs/tags/')
    version(tag)
    if git('rev-parse', f'{ref}^{{commit}}') != sha:
        raise ValueError('Тег больше не указывает на собранный commit')
    subprocess.run(['git', 'merge-base', '--is-ancestor', sha, 'origin/main'], check=True)
    return tag


def verify_assets(folder):
    expected = ''
    try:
        for name in PDF_ASSETS:
            content = (folder / name).read_bytes()
            if not content.startswith(b'%PDF-'):
                raise ValueError(f'Повреждён PDF: {name}')
            expected += f'{hashlib.sha256(content).hexdigest()}  {name}\n'
        if (folder / 'SHA256SUMS').read_text() != expected:
            raise ValueError('SHA256SUMS не соответствует двум PDF')
    except OSError as error:
        raise ValueError(f'Неполный комплект PDF: {error}') from error


def release_notes(repo, sha, run_id):
    return (f'Две полные PDF-версии учебника машинного обучения BelOAI из одних исходников.\n\n'
            f'`{PDF_ASSETS[0]}` — версия для чтения, A4.\n'
            f'`{PDF_ASSETS[1]}` — издательский макет 170 × 240 мм для аудитории 15–18 лет; '
            f'классификационные данные предварительные, официальное утверждение не заявлено.\n\n'
            f'Commit: `{sha}`\n\n'
            f'[Сборка](https://github.com/{repo}/actions/runs/{run_id}) · '
            f'[Онлайн-учебник](https://materials.beloai.by/handbooks/ml/)\n')


def publish(repo, ref, sha, run_id, folder):
    tag = validate_ref(ref, sha)
    preview = tag == 'main-preview'
    if preview and api(f'repos/{repo}/git/ref/heads/main')['object']['sha'] != sha:
        print('Пропущен устаревший prerelease main')
        return
    releases = list(pages(f'repos/{repo}/releases', None))
    release = next((r for r in releases if r['tag_name'] == tag), None)
    if release and not preview and not release['draft']:
        print(f'{tag} уже опубликован; assets не изменены')
        return
    verify_assets(folder)
    title = 'Учебник ML — main preview' if preview else f'Учебник ML — {tag}'
    body = release_notes(repo, sha, run_id)
    data = {'tag_name': tag, 'name': title, 'body': body, 'draft': True,
            'prerelease': preview, 'make_latest': 'false'}
    if preview:
        # Creating the release requires its tag to exist. Updating an existing tag
        # is postponed until all assets have uploaded successfully.
        tags = {t['name'] for t in pages(f'repos/{repo}/tags', None)}
        if tag not in tags:
            api(f'repos/{repo}/git/refs', method='POST', data={'ref': f'refs/tags/{tag}', 'sha': sha})
    if release:
        release = api(f'repos/{repo}/releases/{release["id"]}', method='PATCH', data=data)
    else:
        release = api(f'repos/{repo}/releases', method='POST', data=data)
    subprocess.run(['gh', 'release', 'upload', tag, *(str(folder / a) for a in ASSETS),
                    '--clobber', '--repo', repo], check=True)
    if preview:
        # The workflow-wide release queue excludes other publishers while assets
        # upload. A newer main commit can be built meanwhile and publish next.
        api(f'repos/{repo}/git/refs/tags/{tag}', method='PATCH', data={'sha': sha, 'force': True})
    latest = False
    if not preview:
        published_versions = []
        for other in releases:
            if not other['draft'] and not other['prerelease']:
                try:
                    published_versions.append(version(other['tag_name']))
                except ValueError:
                    pass
        latest = not published_versions or version(tag) >= max(published_versions)
    api(f'repos/{repo}/releases/{release["id"]}', method='PATCH', data={
        'draft': False, 'prerelease': preview, 'make_latest': 'true' if latest else 'false',
    })


def main():
    ref = os.environ['RELEASE_REF']
    sha = os.environ.get('RELEASE_SHA') or git('rev-parse', 'HEAD')
    if sys.argv[1] == 'validate':
        validate_ref(ref, sha)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
                stream.write(f'sha={sha}\n')
    elif sys.argv[1] == 'publish':
        publish(os.environ['GITHUB_REPOSITORY'], ref, sha, os.environ['GITHUB_RUN_ID'], Path('output/release'))
    else:
        raise ValueError('Используйте validate или publish')


if __name__ == '__main__':
    main()
