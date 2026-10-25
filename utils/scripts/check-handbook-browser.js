// Запуск через Playwright CLI на корне сайта или /dev/.
async (page) => {
  const base = new URL(await page.locator('body').getAttribute('data-root'), page.url()).href;
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const chapters = ['intro', 'classic-ml', 'dl-basics', 'nn-in-practice', 'how-nns-learn', 'math-of-ai'];
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base + 'handbooks/');
  await page.getByRole('main').getByRole('link', { name: 'Учебник машинного обучения', exact: true }).click();
  assert(page.url() === base + 'handbooks/ml/', 'ML entry point');
  for (const slug of chapters) {
    await page.goto(base + 'handbooks/ml/' + slug + '/');
    assert(await page.locator('main h1').isVisible(), slug + ': readable page');
    assert(await page.locator('meta[name="robots"]').first().getAttribute('content') === 'noindex, nofollow', slug + ': noindex');
  }
  for (const path of ['python/', 'math/', 'python/basic-constructs/input-output/notebook.ipynb', 'math/calculus/limits/', 'ml/knn/', 'ml/data-experiment/', 'ml/classical-models/linear-models/', 'ml/_paragraph-template/']) {
    for (const prefix of ['handbooks/', 'handbook/']) {
      assert((await page.request.get(base + prefix + path)).status() === 404, 'Removed URL: ' + prefix + path);
    }
  }
  for (const [old, target] of Object.entries({ start: 'intro', environment: 'intro', 'diy-nn': 'nn-in-practice', 'how-they-learn': 'how-nns-learn', 'advanced-math': 'math-of-ai' })) {
    for (const prefix of ['handbooks/', 'handbook/']) {
      await page.goto(base + prefix + 'ml/' + old + '/?from=old#content');
      await page.waitForURL(base + 'handbooks/ml/' + target + '/?from=old#content');
    }
  }
  await page.goto(base + 'handbooks/ml/intro/environment/');
  const download = page.locator('main a[download]').first();
  assert((await page.request.get(new URL(await download.getAttribute('href'), page.url()).href)).ok(), 'Environment requirements download');
  for (const scheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme: scheme });
    for (const width of [360, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(base + 'handbooks/ml/intro/');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No overflow: ' + width);
    }
  }
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(base + 'handbooks/ml/intro/');
  await page.locator('.skip-link').focus();
  await page.keyboard.press('Enter');
  assert(await page.evaluate(() => document.activeElement.id === 'content'), 'Skip navigation');
  const menu = page.locator('.course-menu');
  const toggle = menu.locator(':scope > summary');
  await toggle.click();
  await page.waitForFunction(() => document.querySelector('.workspace').inert);
  await page.keyboard.press('Escape');
  assert(!await menu.evaluate(el => el.open), 'Escape closes menu');
  await toggle.click();
  await menu.getByRole('link', { name: 'Обзор раздела', exact: true }).nth(1).click();
  await page.waitForURL(base + 'handbooks/ml/classic-ml/');
  assert(!await page.locator('.course-menu').evaluate(el => el.open), 'Navigation closes mobile menu');
  const context = await page.context().browser().newContext({ javaScriptEnabled: false, viewport: { width: 360, height: 900 } });
  const staticPage = await context.newPage();
  await staticPage.goto(base + 'handbook/ml/environment/');
  await staticPage.waitForURL(base + 'handbooks/ml/intro/');
  assert(await staticPage.locator('main h1').isVisible(), 'Legacy entry works without JS');
  const staticMenu = staticPage.locator('.course-menu');
  if (!await staticMenu.evaluate(el => el.open)) await staticMenu.locator(':scope > summary').click();
  const summary = staticPage.locator('.handbook-chapter').nth(1).locator(':scope > summary');
  await summary.focus();
  await staticPage.keyboard.press('Enter');
  await staticMenu.getByRole('link', { name: 'Обзор раздела', exact: true }).nth(1).click();
  await staticPage.waitForURL(base + 'handbooks/ml/classic-ml/');
  await context.close();
  assert(errors.length === 0, 'No JavaScript errors: ' + errors.join('; '));
  console.log('ML handbook: navigation, redirects, files, removed URLs, mobile, keyboard and no-JS passed at ' + base);
}
