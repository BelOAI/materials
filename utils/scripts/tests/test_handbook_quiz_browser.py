"""Real browser interaction on synthetic quizzes, independent of handbook contents."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from handbook_blocks import parse
from repo_paths import REPO_ROOT


def question(qid, correct):
    return f''':::: {{.question #{qid} correct="{correct}"}}

Compare **two** expressions: $x+1$ and $x+2$.

::: {{.choices}}

A. The first expression.
B. The second expression.
C. Both expressions.
D. Neither expression.

:::

::: {{.hint}}

A useful hint.

:::

::: {{.solution}}

**{correct}.** Explanation with $x$.

:::

::::
'''


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(os.environ.get('HANDBOOK_BROWSER_TESTS') == '1' or os.environ.get('PDF_RENDER_TESTS') == '1',
                     'Set HANDBOOK_BROWSER_TESTS=1 and install Chromium from utils/pdf')
class HandbookQuizBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        folder = Path(cls.temp.name)
        source = ('::::: {.self-check}\n\n' + question('first', 'B') + question('other', 'C') + '\n:::::\n\n'
                  + '::::: {.self-check}\n\n' + question('independent', 'A') + '\n:::::\n')
        request = [dict(name='fixture/chapter/lesson', source=source, blocks=parse(source))]
        content = json.loads(subprocess.check_output(['node', str(REPO_ROOT / 'utils/site/render-handbook.mjs')],
                              input=json.dumps(request), text=True))[0]['html']
        (folder / 'index.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="stylesheet" href="site.css"><title>Fixture</title>'
            '<script type="module" src="handbook-quiz.js"></script>'
            '<article class="handbook-content" style="max-width:760px;margin:24px auto;padding:0 16px">'
            + content + '</article></html>')
        for name in ('handbook-quiz.js', 'quiz-progress.js', 'site.css'):
            shutil.copyfile(REPO_ROOT / 'utils/site/src' / name, folder / name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(folder)))
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = cls.playwright.chromium.launch(channel='chromium', headless=True)
        cls.addClassCleanup(cls.browser.close)

    def test_attempts_summary_retry_restart_and_independent_groups_in_both_themes(self):
        for width in (360, 1280):
            for theme in ('light', 'dark'):
                with self.subTest(width=width, theme=theme):
                    context = self.browser.new_context(viewport={'width': width, 'height': 900}, color_scheme=theme,
                                                       reduced_motion='reduce')
                    try:
                        page = context.new_page()
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.goto(self.url)
                        page.wait_for_selector('.handbook-self-check[data-enhanced]')
                        page.evaluate("async () => { const {enhanceQuizzes} = await import('./handbook-quiz.js'); enhanceQuizzes(); }")
                        self.assertEqual(page.locator('.quiz-choice-status').count(), 12)
                        group = page.locator('.handbook-self-check').first
                        other_group = page.locator('.handbook-self-check').nth(1)
                        first, second = group.locator('.handbook-question').all()
                        self.assertTrue(first.locator('.quiz-check').is_disabled())
                        self.assertTrue(first.locator('.quiz-solution').is_hidden())
                        first.locator('label').first.click()
                        first.locator('.quiz-check').click()
                        self.assertEqual(first.locator('input:disabled').count(), 4)
                        self.assertEqual(first.locator('[data-state="incorrect"]').count(), 2)  # option and status
                        self.assertIn('Правильный ответ', first.locator('[data-state="correct"]').inner_text())
                        self.assertIn('Проверено 1 из 2', group.locator('.quiz-progress-text').inner_text())
                        first.locator('.quiz-check').dispatch_event('click')
                        self.assertEqual(group.locator('progress').get_attribute('value'), '1')
                        first.locator('.quiz-next').click()
                        self.assertTrue(second.evaluate('(node) => document.activeElement === node'))
                        second.locator('input[value="C"]').check()
                        second.locator('.quiz-check').click()
                        summary = group.locator('.quiz-summary')
                        self.assertTrue(summary.is_visible())
                        self.assertIn('1 из 2', summary.locator('.quiz-score').inner_text())
                        self.assertEqual(other_group.locator('progress').get_attribute('value'), '0')
                        summary.locator('.quiz-review').click()
                        self.assertTrue(first.evaluate('(node) => document.activeElement === node'))
                        first.locator('.quiz-retry').click()
                        self.assertEqual(first.locator('input:checked').count(), 0)
                        self.assertTrue(first.locator('.quiz-solution').is_hidden())
                        first.locator('input[value="B"]').check()
                        first.locator('.quiz-check').click()
                        self.assertIn('1 из 2', summary.locator('.quiz-score').inner_text())
                        self.assertTrue(summary.locator('.quiz-review').is_hidden())
                        self.assertIn('✓', group.locator('.quiz-nav a').first.inner_text())
                        first.locator('.quiz-next').click()
                        self.assertTrue(summary.evaluate('(node) => document.activeElement === node'))
                        summary.locator('.quiz-restart').click()
                        self.assertTrue(summary.is_hidden())
                        self.assertEqual(group.locator('progress').get_attribute('value'), '0')
                        self.assertEqual(group.locator('input:checked').count(), 0)
                        self.assertEqual(group.locator('input:disabled').count(), 0)
                        self.assertTrue(first.evaluate('(node) => document.activeElement === node'))
                        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
                        self.assertFalse(errors)
                    finally:
                        context.close()

    def test_keyboard_accessible_names_and_reload_reset(self):
        context = self.browser.new_context(reduced_motion='reduce')
        try:
            page = context.new_page()
            page.goto(self.url)
            page.wait_for_selector('.handbook-self-check[data-enhanced]')
            first = page.locator('.handbook-question').first
            group = page.get_by_role('group', name='Вопрос 1', exact=True)
            self.assertEqual(group.count(), 1)
            first.locator('input').first.focus()
            page.keyboard.press('ArrowDown')
            self.assertTrue(first.locator('input[value="B"]').is_checked())
            self.assertTrue(first.locator('.quiz-choice:focus-within label').evaluate('(node) => getComputedStyle(node).outlineStyle === "solid"'))
            first.locator('.quiz-check').focus()
            page.keyboard.press('Enter')
            self.assertTrue(first.locator('.quiz-result').inner_text().startswith('Верно.'))
            self.assertTrue(first.locator('.quiz-check').evaluate('(node) => document.activeElement === node'))
            page.keyboard.press('Tab')
            self.assertTrue(first.locator('.quiz-retry').evaluate('(node) => document.activeElement === node'))
            page.reload()
            page.wait_for_selector('.handbook-self-check[data-enhanced]')
            self.assertEqual(page.locator('input:checked').count(), 0)
            self.assertEqual(page.locator('progress').first.get_attribute('value'), '0')
        finally:
            context.close()

    def test_no_javascript_keeps_questions_hints_and_solutions_readable(self):
        context = self.browser.new_context(java_script_enabled=False, viewport={'width': 360, 'height': 900})
        try:
            page = context.new_page()
            page.goto(self.url)
            self.assertEqual(page.locator('input[type="radio"]').count(), 12)
            self.assertEqual(page.locator('.quiz-overview:visible').count(), 0)
            self.assertEqual(page.locator('.quiz-actions button:visible').count(), 0)
            self.assertEqual(page.locator('.quiz-summary:visible').count(), 0)
            first = page.locator('.handbook-question').first
            first.locator('.quiz-hint summary').click()
            self.assertIsNotNone(first.locator('.quiz-hint').get_attribute('open'))
            first.locator('.quiz-solution summary').click()
            self.assertIn('Explanation', first.locator('.quiz-solution').inner_text())
        finally:
            context.close()
