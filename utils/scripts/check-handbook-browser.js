// Проверяет опубликованные ссылки, а не состав и содержание учебника.
async (page) => {
  const base = new URL(await page.locator('body').getAttribute('data-root'), page.url()).href;
  const prefix = base + 'handbooks/';
  const assert = (value, message) => { if (!value) throw new Error(message); };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const pending = [prefix];
  const visited = new Set();
  const downloads = new Set();
  const previews = new Set();
  await page.setViewportSize({ width: 1440, height: 900 });
  while (pending.length) {
    const url = pending.shift();
    if (visited.has(url)) continue;
    visited.add(url);
    const response = await page.goto(url);
    assert(response.ok(), 'Page response: ' + url);
    assert(await page.locator('main h1').first().isVisible(), 'Rendered heading: ' + url);
    assert((await page.locator('main').innerText()).trim().length > 0, 'Rendered main: ' + url);
    assert(await page.locator('.handbook-navigation [aria-current="page"]').count() === 1, 'Active navigation: ' + url);
    for (const img of await page.locator('main img').all()) {
      assert(await img.evaluate(async el => { await el.decode(); return el.complete && el.naturalWidth > 0; }), 'Rendered image: ' + url);
    }
    const links = await page.locator('.handbook-navigation a, main a').evaluateAll(nodes => nodes.map(a => ({ href: a.href, download: a.hasAttribute('download') })));
    for (const { href, download } of links) {
      const target = new URL(href);
      if (!target.href.startsWith(prefix)) continue;
      if (download) downloads.add(href);
      else if (target.pathname.endsWith('/')) {
        target.search = '';
        target.hash = '';
        if (!visited.has(target.href)) pending.push(target.href);
      } else if (target.pathname.endsWith('.html')) {
        previews.add(target.href);
      } else if (target.pathname.endsWith('.md')) {
        throw new Error('Unresolved Markdown source link: ' + href);
      }
    }
    for (const width of [360, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No horizontal overflow: ' + url + ' at ' + width);
    }
  }
  for (const href of downloads) assert((await page.request.get(href)).ok(), 'Download: ' + href);
  for (const href of previews) {
    assert((await page.goto(href)).ok(), 'HTML preview response: ' + href);
    assert((await page.locator('body').innerText()).trim().length > 0, 'Rendered HTML preview: ' + href);
    for (const img of await page.locator('body img').all()) {
      assert(await img.evaluate(async el => { await el.decode(); return el.complete && el.naturalWidth > 0; }), 'Rendered preview image: ' + href);
    }
  }
  const target = [...visited].find(url => url !== prefix) || prefix;
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(target);
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
  const destination = menu.locator('a').filter({ visible: true }).first();
  const href = new URL(await destination.getAttribute('href'), page.url()).href;
  await destination.click();
  await page.waitForURL(href);
  const context = await page.context().browser().newContext({ javaScriptEnabled: false, viewport: { width: 360, height: 900 } });
  const staticPage = await context.newPage();
  await staticPage.goto(target);
  assert(await staticPage.locator('main h1').first().isVisible(), 'Readable without JavaScript');
  const staticMenu = staticPage.locator('.course-menu');
  if (!await staticMenu.evaluate(el => el.open)) await staticMenu.locator(':scope > summary').click();
  assert(await staticMenu.locator('a').first().isVisible(), 'Navigation without JavaScript');
  await context.close();
  assert(errors.length === 0, 'JavaScript errors: ' + errors.join('; '));
  console.log(`Rendered ${visited.size} handbook pages, ${previews.size} previews and ${downloads.size} downloads at ${base}; mobile, keyboard and no-JS passed.`);
  return { base, pages: visited.size, previews: previews.size, downloads: downloads.size };
}
