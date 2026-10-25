// Запуск через playwright-cli run-code; сначала откройте собранный сайт.
async (page) => {
  const base = new URL(await page.locator('body').getAttribute('data-root'), page.url()).href;
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const visibleCount = () => page.locator('.catalog-list > .material:visible').count();
  const errors = [];
  const socialLinks = [
    ['GitHub', 'https://github.com/BelOAI'],
    ['Instagram', 'https://instagram.com/beloaiby'],
    ['TikTok', 'https://tiktok.com/@beloaiby'],
    ['Telegram', 'https://t.me/beloaiby'],
  ];
  const checkSidebar = async (currentPage) => {
    for (const [name, href] of socialLinks) {
      const icon = currentPage.getByRole('link', { name: name + ' BelOAI', exact: true });
      assert(await icon.getAttribute('href') === href, 'Social icon URL: ' + name);
      assert(await icon.getAttribute('title') === name + ' BelOAI', 'Social icon title: ' + name);
      assert(await icon.getAttribute('target') === null, 'Social opens in current tab');
      assert(await icon.isVisible(), 'Social visible outside menu');
      assert(await currentPage.locator('.community-links').getByRole('link', { name, exact: true, includeHidden: true }).getAttribute('href') === href, 'Community URL: ' + name);
    }
    assert(await currentPage.locator('.workspace footer').count() === 0, 'No duplicate content footer');
    assert(await currentPage.locator('.course-menu nav a').last().textContent() === 'Лицензия', 'License finishes navigation');
    assert(await currentPage.getByRole('link', { name: 'Исходники на GitHub', exact: true, includeHidden: true }).getAttribute('href') === 'https://github.com/BelOAI/materials', 'Source repository URL');
  };
  const localResources = new Set();
  const checkPreviewRatio = async () => {
    await page.locator('.preview-surface').waitFor({ state: 'visible' });
    assert(await page.locator('.preview-surface img').evaluate(image => {
      const box = image.parentElement.getBoundingClientRect();
      return image.naturalWidth > 0 && Math.abs((box.width - 2) / (box.height - 2) - image.naturalWidth / image.naturalHeight) < .01;
    }), 'Preview frame follows natural image ratio');
  };
  page.on('pageerror', error => errors.push(error.message));
  await page.emulateMedia({ colorScheme: 'light' });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base + 'weeks/intro-ml/');
  await page.reload();
  assert(await page.locator('.week-resources > li').count() === 3, 'Three resource groups');
  assert(await page.locator('.week-resources > li > ul > .material').count() === 3, 'Three nested materials');
  assert(await page.locator('.sidebar a[aria-current="page"]').textContent().then(t => t.includes('Неделя 1')), 'Active week');
  const geometry = await page.evaluate(() => ({
    sidebar: document.querySelector('.sidebar').getBoundingClientRect().toJSON(),
    workspace: document.querySelector('.workspace').getBoundingClientRect().toJSON(),
    font: getComputedStyle(document.body).fontFamily,
    background: getComputedStyle(document.querySelector('.sidebar')).backgroundColor,
    padding: getComputedStyle(document.querySelector('.workspace')).padding,
    link: getComputedStyle(document.querySelector('.material-title')).color,
  }));
  assert(geometry.sidebar.x === 0 && geometry.sidebar.width === 320, 'Sidebar at left edge, 320px');
  assert(geometry.workspace.x === 320, 'Workspace directly beside sidebar');
  assert(geometry.background === 'rgb(92, 74, 36)', 'Dark golden sidebar');
  assert(await page.locator('.brand').evaluate(el => getComputedStyle(el).fontFamily.includes('Unbounded')), 'Unbounded brand');
  assert(geometry.font.includes('PT Sans'), 'PT Sans');
  assert(geometry.link === 'rgb(165, 28, 48)', 'CS50 link color');
  await page.screenshot({ path: 'output/playwright/beloai-1440.png', fullPage: true });
  const title = page.locator('.material-title').first();
  await title.hover();
  await page.locator('.preview-surface').waitFor({ state: 'visible' });
  await checkPreviewRatio();
  const anchorBox = await title.boundingBox();
  const previewBox = await page.locator('.preview-surface').boundingBox();
  assert(previewBox.x >= 0 && previewBox.y >= 0 && previewBox.x + previewBox.width <= 1440 && previewBox.y + previewBox.height <= 1000, 'Preview fits viewport');
  assert(previewBox.x >= anchorBox.x + anchorBox.width || previewBox.x + previewBox.width <= anchorBox.x || previewBox.y >= anchorBox.y + anchorBox.height || previewBox.y + previewBox.height <= anchorBox.y, 'Preview does not cover title');
  await page.locator('.preview-surface').hover();
  assert(await page.locator('.preview-surface').isVisible(), 'Preview remains hoverable');
  await page.keyboard.press('Escape');
  assert(await page.locator('.preview-surface').count() === 0, 'Escape hides preview');
  await page.mouse.move(1400, 950);
  await title.focus();
  await page.locator('.preview-surface').waitFor({ state: 'visible' });
  await page.keyboard.press('Escape');
  await page.keyboard.press('Tab');
  assert(await page.evaluate(() => document.activeElement.textContent === 'PDF'), 'Keyboard reaches PDF');
  await title.focus();
  await title.hover();
  await page.mouse.move(1400, 950);
  await page.waitForTimeout(220);
  assert(await page.locator('.preview-surface').isVisible(), 'Pointer exit preserves focused preview');
  const secondTitle = page.locator('.material-title').nth(1);
  await secondTitle.focus();
  assert(await page.locator('.preview-surface img').getAttribute('src') === await secondTitle.getAttribute('data-preview'), 'Focus changes preview source');
  await checkPreviewRatio();
  await page.keyboard.press('Escape');
  await page.waitForTimeout(220);
  assert(await page.locator('.preview-surface').count() === 0, 'Escape stays closed while focused');
  await secondTitle.hover();
  await page.locator('.preview-surface').waitFor({ state: 'visible' });
  await page.keyboard.press('Escape');
  await page.mouse.move(1400, 950);
  await page.keyboard.press('Tab');
  await secondTitle.focus();
  await page.locator('.preview-surface').waitFor({ state: 'visible' });
  await page.keyboard.press('Escape');
  await page.setViewportSize({ width: 1024, height: 400 });
  await page.locator('.material-title').nth(2).focus();
  await checkPreviewRatio();
  await page.keyboard.press('Escape');
  await title.focus();
  await page.locator('.preview-surface').waitFor({ state: 'visible' });
  const shortBox = await page.locator('.preview-surface').boundingBox();
  await checkPreviewRatio();
  assert(shortBox.x >= 16 && shortBox.y >= 16 && shortBox.x + shortBox.width <= 1008 && shortBox.y + shortBox.height <= 384, 'Preview including border fits short window');
  await page.keyboard.press('Escape');
  const legal = page.locator('.legal-link a');
  await legal.focus();
  assert(await legal.evaluate(el => {
    const box = el.getBoundingClientRect();
    const sidebar = document.querySelector('.sidebar');
    return box.top >= 0 && box.bottom <= innerHeight && sidebar.scrollTop > 0;
  }), 'Short sidebar scrolls to license by keyboard');
  await page.setViewportSize({ width: 1440, height: 1000 });
  const links = await page.locator('a[href]').evaluateAll(nodes => nodes.map(a => a.href));
  for (const href of new Set(links.filter(href => href.startsWith(base) && !href.includes('#')))) {
    const response = await page.request.get(href);
    assert(response.ok(), 'Resource accessible: ' + href);
  }
  for (const [hash, count] of [['lectures', 1], ['assignments', 3]]) {
    await page.goto(base + '#' + hash);
    await page.waitForURL(base + 'materials/#' + hash);
    await page.getByRole('searchbox').waitFor();
    assert(await visibleCount() === count, 'Legacy hash redirects and filters: ' + hash);
  }
  await page.goto(base + '#practices');
  await page.waitForURL(base + 'materials/#practices');
  await page.getByRole('searchbox').waitFor();
  assert(await visibleCount() === 1, 'Legacy practice hash redirects and filters');
  await page.getByRole('searchbox').fill('numpy');
  const catalogURL = await page.evaluate(() => location.href);
  await page.locator('.skip-link').focus();
  await page.keyboard.press('Enter');
  assert(await page.evaluate(() => location.href) === catalogURL, 'Skip link preserves URL');
  assert(await visibleCount() === 1, 'Skip link preserves filtered results');
  assert(await page.getByRole('searchbox').inputValue() === 'numpy', 'Skip link preserves query');
  assert(await page.getByRole('button', { name: 'Практики', exact: true }).getAttribute('aria-pressed') === 'true', 'Skip link preserves filter');
  assert(await page.evaluate(() => document.activeElement.id === 'content'), 'Skip link focuses main');
  await page.emulateMedia({ colorScheme: 'dark' });
  assert(await page.evaluate(() => location.href) === catalogURL && await visibleCount() === 1, 'Theme change preserves catalog state');
  await page.emulateMedia({ colorScheme: 'light' });
  const search = page.getByRole('searchbox');
  await search.fill('МАТРИЦЫ');
  assert(await visibleCount() === 0, 'Combined search and practice filter');
  await page.getByRole('button', { name: 'Все', exact: true }).click();
  assert(await visibleCount() === 1, 'Search finds matrices');
  await page.goBack();
  assert(await visibleCount() === 0, 'Back restores practice filter');
  assert(await search.inputValue() === 'МАТРИЦЫ', 'Back restores query');
  await page.goForward();
  assert(await visibleCount() === 1, 'Forward restores all filter');
  await search.fill('нет такой темы');
  await page.getByRole('button', { name: 'Сбросить поиск' }).click();
  assert(await visibleCount() === 5, 'Reset returns all five materials');
  await page.goto(base + 'materials/?q=NumPy#practices');
  await page.getByRole('searchbox').waitFor();
  assert(await visibleCount() === 1, 'Direct query URL');
  await page.reload();
  await page.getByRole('searchbox').waitFor();
  assert(await visibleCount() === 1, 'Query persists on reload');
  await page.route('**/materials.json', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.reload();
  await page.getByRole('button', { name: 'Попробовать ещё раз' }).waitFor();
  assert(await visibleCount() === 5, 'Fetch failure leaves static list');
  await page.unroute('**/materials.json');
  await page.getByRole('button', { name: 'Попробовать ещё раз' }).click();
  await page.getByRole('searchbox').waitFor();
  assert(await visibleCount() === 1, 'Retry restores query');
  await page.route('**/materials.json', route => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ version: 1, materials: [] }),
  }));
  await page.reload();
  await page.getByRole('button', { name: 'Попробовать ещё раз' }).waitFor();
  assert(await visibleCount() === 5, 'Invalid manifest leaves static list');
  await page.unroute('**/materials.json');
  await page.getByRole('button', { name: 'Попробовать ещё раз' }).click();
  await page.getByRole('searchbox').waitFor();
  assert(await visibleCount() === 1, 'Retry recovers from invalid manifest');
  // Жизненный цикл компонентов и изоляция статических списков.
  await page.evaluate(async () => {
    const assert = (condition, message) => { if (!condition) throw new Error(message); };
    const settle = async () => { await new Promise(resolve => setTimeout(resolve, 30)); };
    const catalog = document.querySelector('materials-catalog');
    const copy = catalog.cloneNode(true);
    catalog.after(copy);
    while (copy.status !== 'ready') await settle();
    const originalVisibility = [...catalog.rows()].map(row => row.hidden).join();
    copy.controls.emit('query-change', { query: 'нет такой темы' });
    await settle();
    assert([...copy.rows()].every(row => row.hidden), 'Second catalog filters its own rows');
    assert([...catalog.rows()].map(row => row.hidden).join() === originalVisibility, 'Original catalog remains untouched');
    assert(copy.controls.query === copy.query, 'Controls receive query property');
    assert(copy.controls.searchId !== catalog.controls.searchId, 'Search labels have unique targets');
    copy.remove();
    assert([...copy.rows()].every(row => !row.hidden), 'Disconnect restores static list');
    catalog.after(copy);
    while (copy.status !== 'ready') await settle();
    copy.controls.emit('catalog-reset');
    await settle();
    assert([...copy.rows()].every(row => !row.hidden), 'Reconnected controls work');

    const fetchOriginal = window.fetch;
    const manifest = await (await fetchOriginal(new URL('../materials.json', location.href))).json();
    const requests = [];
    try {
      window.fetch = (_url, options) => new Promise(resolve => requests.push({ resolve, signal: options.signal }));
      copy.load();
      copy.load();
      assert(requests[0].signal.aborted, 'Retry aborts previous request');
      requests[1].resolve({ ok: true, json: async () => manifest });
      await settle();
      assert(copy.status === 'ready', 'Latest request succeeds');
      requests[0].resolve({ ok: false });
      await settle();
      assert(copy.status === 'ready', 'Stale failure cannot replace latest result');
      copy.load();
      copy.remove();
      assert(requests[2].signal.aborted, 'Disconnect aborts pending fetch');
      requests[2].resolve({ ok: true, json: async () => manifest });
      await settle();
      assert(copy.status === 'loading', 'Late response cannot update detached catalog');
    } finally { window.fetch = fetchOriginal; copy.remove(); }

    const shell = document.querySelector('course-shell');
    shell.remove();
    document.body.append(shell);
    const previousURL = location.href;
    shell.querySelector('.skip-link').click();
    assert(location.href === previousURL && document.activeElement.id === 'content', 'Reconnected shell preserves skip behavior');
  });
  await page.reload();
  await page.getByRole('searchbox').waitFor();
  await page.setViewportSize({ width: 768, height: 1000 });
  await page.locator('.course-menu summary').click();
  await page.setViewportSize({ width: 800, height: 1000 });
  assert(await page.locator('.course-menu').evaluate(el => el.open), 'Manual menu state survives resize within mobile range');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.waitForFunction(() => document.querySelector('.course-menu').open);
  await page.setViewportSize({ width: 768, height: 1000 });
  await page.waitForFunction(() => !document.querySelector('.course-menu').open);
  assert(!await page.locator('.course-menu').evaluate(el => el.open), 'Crossing breakpoint resets menu');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(async () => {
    const preview = document.querySelector('material-preview');
    preview.remove();
    document.querySelector('course-shell').append(preview);
    const outside = document.createElement('a');
    outside.href = '#';
    outside.dataset.preview = document.querySelector('a[data-preview]').dataset.preview;
    outside.textContent = 'Outside preview scope';
    document.querySelector('.sidebar').prepend(outside);
    outside.focus();
    outside.dispatchEvent(new PointerEvent('pointerover', { bubbles: true }));
    await preview.updateComplete;
    if (preview.source) throw new Error('Preview ignores sources outside main');
    outside.remove();
  });
  await page.locator('.material-title[data-preview]').first().focus();
  await checkPreviewRatio();
  await page.keyboard.press('Escape');
  const paths = [
    ['', 'home'], ['weeks/math-foundations/', 'week-0'],
    ['weeks/intro-ml/', 'week-1'], ['materials/', 'catalog'], ['license/', 'license'],
  ];
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme });
    const prefix = colorScheme === 'dark' ? 'dark-' : '';
    for (const width of [360, 768, 991, 992, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const [path, name] of paths) {
        await page.goto(base + path);
        if (name === 'license') await page.reload();
        if (name === 'catalog') await page.getByRole('searchbox').waitFor();
        await page.evaluate(() => document.fonts.ready);
        await checkSidebar(page);
        await page.getByRole('link', { name: 'GitHub BelOAI', exact: true }).focus();
        assert(await page.getByRole('link', { name: 'GitHub BelOAI', exact: true }).evaluate(el => getComputedStyle(el).outlineOffset === '-2px'), 'Social icon focus stays inside');
        if (name === 'license') {
          assert(await page.locator('.legal-link a').getAttribute('aria-current') === 'page', 'License active in sidebar');
          assert(await page.locator('main').textContent().then(text => text.includes('Авторы BelOAI') && text.includes('BSD-3-Clause')), 'Collective attribution and dependencies');
          assert(await page.getByRole('link', { name: 'Участники проекта', exact: true }).getAttribute('href') === 'https://github.com/BelOAI/materials/blob/main/CONTRIBUTORS.md', 'Contributors stay in repository');
        }
        const colors = await page.evaluate(() => ({
          background: getComputedStyle(document.documentElement).backgroundColor,
          text: getComputedStyle(document.body).color,
          link: getComputedStyle(document.querySelector('main a')).color,
        }));
        assert(colors.background === (colorScheme === 'dark' ? 'rgb(33, 37, 41)' : 'rgb(255, 255, 255)'), 'CS50 page background: ' + colorScheme);
        assert(colors.text === (colorScheme === 'dark' ? 'rgb(222, 226, 230)' : 'rgb(33, 37, 41)'), 'CS50 text: ' + colorScheme);
        assert(colors.link === (colorScheme === 'dark' ? 'rgb(239, 154, 164)' : 'rgb(165, 28, 48)'), 'CS50 links: ' + colorScheme);
        if (name === 'catalog') {
          assert(await page.getByRole('searchbox').evaluate(el => getComputedStyle(el).backgroundColor) === colors.background, 'Search surface follows theme');
        }
        if (name.startsWith('week')) {
          assert(await page.locator('.resource-links a').first().evaluate(el => getComputedStyle(el).paddingTop === '0px'), 'Dense nested links at every width');
        }
        const resources = await page.locator('a[href], link[rel="stylesheet"], script[src], .sidebar img[src]').evaluateAll(nodes => nodes.map(node => node.href || node.src));
        resources.filter(url => url.startsWith(base) && !url.includes('#')).forEach(url => localResources.add(url));
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No overflow: ' + name + ' at ' + width);
        const desktop = width >= 992;
        assert(await page.locator('.course-menu').evaluate(el => el.open) === desktop, 'Menu breakpoint: ' + name + ' at ' + width);
        const weekLink = page.locator('.week-navigation a').first();
        assert((await weekLink.getAttribute('title')).includes('Математическая подготовка'), 'Full week title');
        assert(await weekLink.textContent().then(t => t.includes('Математическая подготовка')), 'Full accessible link text');
        if (!desktop) {
          await page.locator('.course-menu summary').focus();
          await page.keyboard.press('Enter');
          assert(await page.locator('.course-menu').evaluate(el => el.open), 'Menu opens by keyboard');
          assert(await weekLink.evaluate(el => getComputedStyle(el).paddingTop === '0px' && getComputedStyle(el).paddingBottom === '0px'), 'Dense CS50 mobile navigation');
        }
        await weekLink.focus();
        assert(await weekLink.evaluate(el => getComputedStyle(el).outlineOffset === '-2px'), 'Focus outline stays inside clipped link');
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: `output/playwright/${prefix}${name}-${width}-menu-open.png`, fullPage: true });
        if (!desktop) {
          await page.locator('.course-menu summary').focus();
          await page.keyboard.press('Enter');
          assert(!await page.locator('.course-menu').evaluate(el => el.open), 'Menu closes by keyboard');
        }
        await page.locator('main').focus();
        await page.locator('main').evaluate(el => el.blur());
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: `output/playwright/${prefix}${name}-${width}.png`, fullPage: true });
        if (width === 360 && name === 'week-1') {
          await page.locator('.material-title').first().focus();
          assert(await page.locator('.preview-surface').count() === 0, 'No phone preview');
        }
      }
    }
  }
  for (const url of localResources) {
    assert((await page.request.get(url)).ok(), 'Local resource accessible: ' + url);
  }
  const noJS = await page.context().browser().newContext({ javaScriptEnabled: false, colorScheme: 'dark', viewport: { width: 360, height: 1000 } });
  const staticPage = await noJS.newPage();
  await staticPage.goto(base);
  await checkSidebar(staticPage);
  assert(await staticPage.locator('.week-list li').count() === 2, 'Two weeks without JS');
  assert(await staticPage.evaluate(() => getComputedStyle(document.documentElement).backgroundColor) === 'rgb(33, 37, 41)', 'Dark theme without JS');
  await staticPage.goto(base + 'weeks/math-foundations/');
  assert(await staticPage.locator('.material').count() === 2, 'Week resources without JS');
  assert(await staticPage.locator('.sidebar nav').isVisible(), 'Navigation without JS');
  await staticPage.locator('.skip-link').focus();
  await staticPage.keyboard.press('Enter');
  assert(new URL(staticPage.url()).hash === '#content', 'Native skip anchor without JS');
  await staticPage.goto(base + 'weeks/intro-ml/');
  assert(await staticPage.locator('.material').count() === 3, 'Intro week resources without JS');
  await staticPage.goto(base + 'materials/');
  assert(await staticPage.locator('.material').count() === 5, 'Catalog without JS');
  await staticPage.goto(base + 'license/');
  await checkSidebar(staticPage);
  assert(await staticPage.getByRole('heading', { name: 'Лицензия', exact: true }).isVisible(), 'License page without JS');
  await noJS.close();
  await page.emulateMedia({ colorScheme: 'light' });
  assert(await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor) === 'rgb(255, 255, 255)', 'Live return to light theme');
  assert(errors.length === 0, 'No browser errors: ' + errors.join('; '));
  return { result: 'All browser checks passed', localResources: localResources.size, colorSchemes: ['light', 'dark'], widths: [360, 768, 991, 992, 1440], geometry };
}
