// Откройте production-корень локально собранного объединённого Pages-артефакта.
async (page) => {
  const production = new URL(await page.locator('body').getAttribute('data-root'), page.url()).href;
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const resources = new Set();
  for (const [name, base] of [['main', production], ['dev', production + 'dev/']]) {
    const manifestResponse = await page.request.get(base + 'materials.json');
    assert(manifestResponse.ok(), name + ': manifest');
    const manifest = await manifestResponse.json();
    for (const material of manifest.materials) {
      for (const href of [material.pdf, material.thumb, ...material.materials.flatMap(file => [file.open, file.download])]) {
        if (href) resources.add(new URL(href, base).href);
      }
    }
    for (const width of [360, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.goto(base);
      assert(await page.getByRole('complementary', { name: 'Тестовая версия' }).count() === (name === 'dev' ? 1 : 0), name + ': banner');
      if (name === 'dev') assert(await page.locator('meta[name="robots"]').getAttribute('content') === 'noindex, nofollow', 'dev: noindex');
      await page.locator('.skip-link').focus();
      await page.keyboard.press('Enter');
      assert(await page.evaluate(() => document.activeElement.id) === 'content', name + ': skip link');
      await page.goto(base + 'materials/');
      await page.getByRole('searchbox').waitFor();
      assert(await page.locator('.catalog-list > .material:visible').count() === manifest.materials.length, name + ': all materials');
      for (const kind of ['lectures', 'practices', 'assignments']) {
        await page.goto(base + '#' + kind);
        await page.waitForURL(base + 'materials/#' + kind);
        const expected = manifest.materials.filter(item => item.kind === kind.slice(0, -1)).length;
        await page.waitForFunction(count => document.querySelectorAll('.catalog-list > .material:not([hidden])').length === count, expected);
        assert(await page.locator('.catalog-list > .material:visible').count() === expected, name + ': hash filter ' + kind);
      }
      await page.goto(base + 'materials/');
      const search = page.getByRole('searchbox');
      await search.fill(manifest.materials[0].title);
      await page.waitForFunction(() => location.search.includes('q='));
      assert(await page.locator('.catalog-list > .material:visible').count() > 0, name + ': search');
      await page.reload();
      assert(await page.getByRole('searchbox').inputValue() === manifest.materials[0].title, name + ': persisted search');
      if (width === 360) {
        await page.locator('.course-menu summary').focus();
        await page.keyboard.press('Enter');
        assert(await page.locator('.course-menu').evaluate(el => el.open), name + ': keyboard menu');
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), name + ': no horizontal overflow');
      const localLinks = await page.locator('a[href],link[rel="stylesheet"],script[src]').evaluateAll(nodes => nodes.filter(node => !node.closest('aside[aria-label="Тестовая версия"]')).map(node => node.href || node.src));
      for (const href of localLinks) {
        const url = new URL(href);
        if (url.origin !== new URL(base).origin) continue;
        assert(url.pathname.startsWith(new URL(base).pathname), name + ': prefix ' + href);
        url.hash = '';
        resources.add(url.href);
      }
      await page.screenshot({ path: `output/playwright/pages-${name}-${width}.png`, fullPage: true });
    }
    const context = await page.context().browser().newContext({ javaScriptEnabled: false });
    try {
      const staticPage = await context.newPage();
      await staticPage.goto(base + 'materials/');
      assert(await staticPage.locator('.material').count() === manifest.materials.length, name + ': no JavaScript');
      await staticPage.goto(base + 'handbook/');
      assert(await staticPage.locator('main a').count() > 0, name + ': handbook');
    } finally { await context.close(); }
  }
  for (const href of resources) assert((await page.request.get(href)).ok(), 'Unavailable: ' + href);
  assert(errors.length === 0, errors.join('; '));
  return { result: 'Pages main/dev checks passed', resources: resources.size };
}
