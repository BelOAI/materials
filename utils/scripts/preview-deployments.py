#!/usr/bin/env python3
"""Синхронизация нативных dev/PR deployments с опубликованным Pages-сайтом."""
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('assemble_pages', Path(__file__).with_name('assemble-pages.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
api, pages = module.api, module.pages
STATE = Path('.cache/preview-deployments.json')
OWNER = 'materials-preview-v1'


def status(repo, deployment, state, *, root='', description=''):
    return api(f'repos/{repo}/deployments/{deployment}/statuses', method='POST', data={
        'state': state, 'auto_inactive': False, 'description': description,
        'environment_url': f'https://materials.beloai.by/{root}' if root else '',
        'log_url': f'{os.environ.get("GITHUB_SERVER_URL", "https://github.com")}/{repo}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
    })


def owned(deployment):
    payload = deployment.get('payload') or {}
    return isinstance(payload, dict) and payload.get('owner') == OWNER


def prepare(repo, metadata):
    existing = list(pages(f'repos/{repo}/deployments', None))
    state = {'previews': {}, 'previous': [d for d in existing if owned(d)]}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state))
    for key, item in metadata.items():
        if key != 'dev' and not key.startswith('pr-'):
            continue
        is_dev = key == 'dev'
        environment = 'dev' if is_dev else f'preview-{key}'
        payload = ({'owner': OWNER, 'branch': 'dev', 'run_id': item['run_id']} if is_dev else
                   {'owner': OWNER, 'pr': item['pr'], 'merge_sha': item['merge_sha'], 'run_id': item['run_id']})
        deployment = next((d for d in existing if owned(d) and d['environment'] == environment
                           and d['sha'] == item['sha'] and d['payload'] == payload), None)
        if deployment is None:
            deployment = api(f'repos/{repo}/deployments', method='POST', data={
                'ref': item['sha'], 'environment': environment, 'auto_merge': False,
                'required_contexts': [], 'transient_environment': not is_dev,
                'production_environment': False, 'payload': payload,
                'description': 'Тестовый сайт ветки dev' if is_dev else f'Тестовый сайт PR #{item["pr"]}',
            })
        statuses = list(pages(f'repos/{repo}/deployments/{deployment["id"]}/statuses', None))
        already_successful = bool(statuses and statuses[0]['state'] == 'success')
        state['previews'][key] = {'id': deployment['id'], 'root': item['root'], 'successful': already_successful}
        STATE.write_text(json.dumps(state))
        if not already_successful:
            status(repo, deployment['id'], 'in_progress', description='Публикуется тестовый сайт')
    return state


def finish(repo, result):
    if not STATE.exists():
        return
    state = json.loads(STATE.read_text())
    current = state['previews']
    if result != 'success':
        for item in current.values():
            if not item['successful']:
                status(repo, item['id'], 'failure', description='Публикация Pages не завершилась')
        return
    # Statuses are reconciled from the exact manifest shipped in this Pages deployment.
    for item in current.values():
        status(repo, item['id'], 'success', root=item['root'], description='Тестовый сайт опубликован')
    active = {item['id'] for item in current.values()}
    for old in state['previous']:
        if old['id'] not in active:
            status(repo, old['id'], 'inactive', description='Версия заменена или тестовый сайт удалён')


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    if sys.argv[1] == 'prepare':
        prepare(repo, json.loads(Path('_pages/build-info.json').read_text()))
    elif sys.argv[1] == 'finish':
        finish(repo, os.environ['DEPLOY_RESULT'])
    else:
        raise SystemExit('Используйте prepare или finish')


if __name__ == '__main__':
    main()
