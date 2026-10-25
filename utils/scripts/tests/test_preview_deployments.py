"""Preview lifecycle with synthetic GitHub responses and site archives."""
from contextlib import chdir
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).parents[1] / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


site = load('assemble-pages')
deploy = load('preview-deployments')


class SelectionTests(unittest.TestCase):
    def select(self, *, open=True, branch=True, fork=False, expired=False, associated=True):
        pr = {'number': 7, 'head': {'ref': 'topic/a', 'repo': {'full_name': 'fork/repo' if fork else 'org/repo'}},
              'base': {'ref': 'dev'}}
        run = {'id': 9, 'event': 'pull_request', 'head_sha': 'sha', 'head_branch': 'topic/a',
               'head_repository': {'full_name': 'org/repo'}, 'pull_requests': [] if associated else [{'number': 8}]}
        def responses(path, key):
            if '/branches' in path:
                return iter([{'name': 'topic/a'}] if branch else [])
            if '/pulls?state=open' in path:
                return iter([pr] if open else [])
            if '/runs?' in path:
                return iter([run])
            if '/artifacts' in path:
                return iter([{'id': 1, 'name': 'site-pr-7-sha', 'expired': expired}])
            raise AssertionError(path)
        with patch.object(site, 'pages', side_effect=responses):
            return site.preview_artifacts('org/repo')

    def test_live_pr_and_reopen(self):
        self.assertIn('pr-7', self.select())
        self.assertEqual(self.select(open=False), {})
        self.assertIn('pr-7', self.select(open=True))

    def test_deleted_branch_fork_expired_unassociated_run(self):
        for changes in [dict(branch=False), dict(fork=True), dict(expired=True), dict(associated=False)]:
            with self.subTest(changes=changes):
                self.assertEqual(self.select(**changes), {})

    def test_preview_links_cannot_escape_into_production(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'index.html').write_text('<body>Main</body>')
            (root / 'dev').mkdir()
            (root / 'dev/index.html').write_text('<a href="../index.html">Wrong root</a>')
            with self.assertRaisesRegex(ValueError, 'Нерабочая ссылка'):
                site.validate_site(root, environment_roots=['dev/'])
            (root / 'dev/index.html').write_text('<a href="./">Correct root</a>')
            site.validate_site(root, environment_roots=['dev/'])

    def test_site_size_broken_links_and_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'index.html').write_text('<a href="resource.pdf">PDF</a>')
            with self.assertRaisesRegex(ValueError, 'Нерабочая ссылка'):
                site.validate_site(root)
            (root / 'resource.pdf').write_bytes(b'%PDF')
            site.validate_site(root)
            with self.assertRaisesRegex(ValueError, 'лимит'):
                site.validate_site(root, max_bytes=1)
            (root / 'index.html').write_text('<a href="../outside">escape</a>')
            with self.assertRaises(ValueError):
                site.validate_site(root)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        state = patch.object(deploy, 'STATE', Path(temp.name) / 'state.json')
        state.start()
        self.addCleanup(state.stop)
        env = patch.dict(os.environ, GITHUB_RUN_ID='100')
        env.start()
        self.addCleanup(env.stop)
        self.item = {'pr': 7, 'sha': 'head', 'merge_sha': 'merge', 'run_id': 9, 'root': 'test/pr-7/'}

    def existing(self, id, pr=7, run=8):
        return {'id': id, 'environment': f'preview-pr-{pr}', 'sha': 'head',
                'payload': {'owner': deploy.OWNER, 'pr': pr, 'merge_sha': 'merge', 'run_id': run}}

    def test_success_then_cleanup_and_idempotent_prepare(self):
        current, old, other = self.existing(2, run=9), self.existing(1), {'id': 99, 'payload': {}}
        with patch.object(deploy, 'pages', side_effect=[iter([current, old, other]), iter([{'state': 'success'}])]), \
                patch.object(deploy, 'api') as api:
            deploy.prepare('org/repo', {'pr-7': self.item})
            api.assert_not_called()  # same run does not create a duplicate or hide a good version
            deploy.finish('org/repo', 'success')
            states = [(c.args[0], c.kwargs['data']['state']) for c in api.call_args_list]
            self.assertEqual(states, [('repos/org/repo/deployments/2/statuses', 'success'),
                                      ('repos/org/repo/deployments/1/statuses', 'inactive')])
            self.assertEqual(api.call_args_list[0].kwargs['data']['environment_url'],
                             'https://materials.beloai.by/test/pr-7/')
        with patch.object(deploy, 'pages', return_value=iter([current])), patch.object(deploy, 'api') as api:
            deploy.prepare('org/repo', {})
            deploy.finish('org/repo', 'success')
            self.assertEqual(api.call_args.kwargs['data']['state'], 'inactive')

    def test_failed_publish_preserves_previous_success(self):
        with patch.object(deploy, 'pages', side_effect=[iter([self.existing(1)]), iter([])]), \
                patch.object(deploy, 'api', return_value={'id': 2}) as api:
            deploy.prepare('org/repo', {'pr-7': self.item})
            self.assertTrue(api.call_args_list[0].kwargs['data']['transient_environment'])
            deploy.finish('org/repo', 'failure')
            states = [c.kwargs['data'].get('state') for c in api.call_args_list]
            self.assertEqual(states, [None, 'in_progress', 'failure'])
            self.assertNotIn('inactive', states)
            self.assertTrue(all(not c.kwargs['data'].get('environment_url') for c in api.call_args_list))

    def test_update_does_not_deactivate_other_active_pr(self):
        old, other = self.existing(1), self.existing(3, pr=8)
        item8 = dict(self.item, pr=8, root='test/pr-8/')
        other['payload']['run_id'] = 9
        with patch.object(deploy, 'pages', side_effect=[iter([old, other]), iter([]), iter([{'state': 'success'}])]), \
                patch.object(deploy, 'api', return_value={'id': 2}) as api:
            deploy.prepare('org/repo', {'pr-7': self.item, 'pr-8': item8})
            deploy.finish('org/repo', 'success')
            inactive = [c.args[0] for c in api.call_args_list if c.kwargs['data'].get('state') == 'inactive']
            self.assertEqual(inactive, ['repos/org/repo/deployments/1/statuses'])


if __name__ == '__main__':
    unittest.main()
