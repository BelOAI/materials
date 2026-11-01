"""Release validation and publishing use synthetic repositories and PDF assets."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('handbook_release', Path(__file__).parents[1] / 'handbook-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class VersionTests(unittest.TestCase):
    def test_calendar_format_and_order(self):
        versions = ['v2026.10.25', 'v2026.10.25.1', 'v2026.10.25.2', 'v2026.10.25.10', 'v2026.10.26']
        self.assertEqual(sorted(versions, key=release.version), versions)
        for tag in ['v2026.02.29', 'v2026.13.01', 'v2026.1.01', 'v2026.10.25.0', 'v2026.10.25.01',
                    '2026.10.25', 'v2026.10.25-rc1', 'main-preview']:
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.version(tag)
        release.version('v2028.02.29')

    def test_tag_commit_and_main_ancestry_in_real_temporary_git(self):
        from contextlib import chdir
        with tempfile.TemporaryDirectory() as temp, chdir(temp):
            def git(*args):
                return subprocess.check_output(['git', *args], stderr=subprocess.DEVNULL, text=True).strip()
            git('init', '-b', 'main')
            git('config', 'user.email', 'test@example.org')
            git('config', 'user.name', 'Test')
            git('commit', '--allow-empty', '-m', 'base')
            base = git('rev-parse', 'HEAD')
            git('update-ref', 'refs/remotes/origin/main', base)
            git('tag', 'v2026.10.25')
            self.assertEqual(release.validate_ref('refs/tags/v2026.10.25', base), 'v2026.10.25')
            git('checkout', '-b', 'other')
            git('commit', '--allow-empty', '-m', 'unmerged')
            other = git('rev-parse', 'HEAD')
            git('tag', 'v2026.10.25.1')
            with self.assertRaises(subprocess.CalledProcessError):
                release.validate_ref('refs/tags/v2026.10.25.1', other)
            with self.assertRaisesRegex(ValueError, 'больше не указывает'):
                release.validate_ref('refs/tags/v2026.10.25', other)
            with self.assertRaises(ValueError):
                release.validate_ref('refs/heads/dev', other)


class PublishTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        checksums = []
        for name in release.PDF_ASSETS:
            pdf = self.folder / name
            pdf.write_bytes(b'%PDF-synthetic-' + name.encode())
            checksums.append(f'{hashlib.sha256(pdf.read_bytes()).hexdigest()}  {pdf.name}\n')
        (self.folder / 'SHA256SUMS').write_text(''.join(checksums))

    def test_checksum_rejects_corruption(self):
        release.verify_assets(self.folder)
        (self.folder / release.ASSETS[0]).write_bytes(b'%PDF-corrupt')
        with self.assertRaises(ValueError):
            release.verify_assets(self.folder)

    def test_both_pdfs_are_required_and_checked(self):
        pdf = self.folder / release.PDF_ASSETS[1]
        for content in (b'%PDF-corrupt', b'not a pdf'):
            pdf.write_bytes(content)
            with self.assertRaises(ValueError):
                release.verify_assets(self.folder)
        pdf.unlink()
        with self.assertRaises(ValueError):
            release.verify_assets(self.folder)

    def publish(self, tag, releases, upload_error=None):
        requests = []
        def api(path, **kwargs):
            requests.append((path, kwargs))
            if '/git/ref/heads/main' in path:
                return {'object': {'sha': 'head'}}
            return {'id': 7}
        def pages(path, key):
            return iter([{'name': 'main-preview'}] if path.endswith('/tags') else releases)
        with patch.object(release, 'validate_ref', return_value=tag), patch.object(release, 'api', side_effect=api), \
                patch.object(release, 'pages', side_effect=pages), \
                patch.object(release.subprocess, 'run', side_effect=upload_error) as upload:
            if upload_error:
                with self.assertRaises(RuntimeError):
                    release.publish('org/repo', 'ref', 'head', '123', self.folder)
            else:
                release.publish('org/repo', 'ref', 'head', '123', self.folder)
        return requests, upload

    def test_new_release_uploads_draft_then_publishes_latest(self):
        calls, upload = self.publish('v2026.10.25', [])
        self.assertTrue(calls[0][1]['data']['draft'])
        upload.assert_called_once()
        self.assertEqual(calls[-1][1]['data'], {'draft': False, 'prerelease': False, 'make_latest': 'true'})

    def test_historical_tag_does_not_take_latest(self):
        calls, _ = self.publish('v2026.10.25', [{'tag_name': 'v2026.10.25.2', 'draft': False, 'prerelease': False}])
        self.assertEqual(calls[-1][1]['data']['make_latest'], 'false')

    def test_stable_rerun_never_replaces_published_assets(self):
        # Older releases may contain only the reader PDF. They remain immutable.
        (self.folder / release.PDF_ASSETS[1]).unlink()
        calls, upload = self.publish('v2026.10.25', [{'tag_name': 'v2026.10.25', 'draft': False, 'prerelease': False}])
        self.assertEqual(calls, [])
        upload.assert_not_called()

    def test_failed_upload_stays_draft_and_retry_resumes(self):
        calls, _ = self.publish('v2026.10.25', [], upload_error=RuntimeError('upload failed'))
        self.assertTrue(calls[-1][1]['data']['draft'])
        calls, _ = self.publish('v2026.10.25', [{'tag_name': 'v2026.10.25', 'id': 7, 'draft': True, 'prerelease': False}])
        self.assertEqual(calls[0][1]['method'], 'PATCH')
        self.assertFalse(calls[-1][1]['data']['draft'])

    def test_preview_moves_tag_and_never_becomes_latest(self):
        calls, _ = self.publish('main-preview', [])
        self.assertTrue(any('/git/refs/tags/main-preview' in path for path, _ in calls))
        self.assertEqual(calls[-1][1]['data'], {'draft': False, 'prerelease': True, 'make_latest': 'false'})

    def test_stale_main_does_not_touch_release(self):
        with patch.object(release, 'validate_ref', return_value='main-preview'), \
                patch.object(release, 'api', return_value={'object': {'sha': 'newer'}}) as api, \
                patch.object(release, 'pages') as pages:
            release.publish('org/repo', 'refs/heads/main', 'old', '123', self.folder)
            pages.assert_not_called()
            api.assert_called_once()


if __name__ == '__main__':
    unittest.main()
