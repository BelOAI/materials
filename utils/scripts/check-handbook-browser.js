// Запуск: playwright-cli run-code --filename utils/scripts/check-handbook-browser.js
async (page) => {
  const base = new URL(await page.locator('body').getAttribute('data-root'), page.url()).href;
  await page.setViewportSize({ width: 1440, height: 900 });
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const origin = new URL(base).origin;
  await page.goto(base + 'handbooks/');
  assert(await page.locator('main').getByRole('link', { name: /^Учебник/ }).count() === 3, 'Three independent handbooks');
  assert(await page.locator('.handbook-content details').count() === 0, 'Homepage has no long route lists');
  const pages = new Set();
  for (const slug of ['python', 'math', 'ml']) {
    await page.goto(base + 'handbooks/' + slug + '/');
    assert(await page.locator('.handbook-track').count() === 1, slug + ': only current handbook tree');
    if (slug === 'ml') {
      const headings = await page.locator('.handbook-chapter > summary').allTextContents();
      const titles = ['Environment', 'Classic ML', 'DL basics', 'DIY with NN', 'How they learn!', 'Advanced math of AI'];
      assert(JSON.stringify(headings) === JSON.stringify(titles.map((title, i) => `${i}. ${title}`)), 'Exact six ML sections');
      assert(await page.locator('.section-planned').count() === 6, 'Six planned sections');
      assert(await page.locator('.handbook-chapter a').count() === 6, 'No ML lesson links');
    }
    for (const url of await page.locator('.handbook-navigation a').evaluateAll(links => links.map(a => a.href))) {
      if (url.startsWith(base + 'handbooks/')) pages.add(url);
    }
  }
  for (const url of pages) {
    await page.goto(url);
    assert(await page.locator('h1').count() === 1, url + ': one heading');
    assert(await page.locator('.handbook-notice, .chapter-status').count() === 0, url + ': no editorial notices');
    const sidebar = page.locator('.sidebar');
    assert(await sidebar.getByRole('link', { name: '← На основной сайт', exact: true }).getAttribute('href') === await page.locator('body').getAttribute('data-root'), url + ': return to site');
    assert(await sidebar.locator('.week-navigation').count() === 0, url + ': dedicated navigation');
    assert(await sidebar.getByRole('link', { name: 'Все материалы', exact: true }).count() === 0, url + ': no catalog in handbook tree');
    assert(await sidebar.locator('a[aria-current="page"]').count() === 1, url + ': exact active page');
    if (await page.evaluate(() => innerWidth >= 992)) {
      await page.waitForFunction(() => {
        const active = document.querySelector('.handbook-navigation a[aria-current="page"]');
        const sidebar = document.querySelector('.sidebar');
        const a = active.getBoundingClientRect();
        const b = sidebar.getBoundingClientRect();
        return a.top >= b.top && a.bottom <= b.bottom;
      });
    }
    if (await page.locator('.week-pagination').count() && !url.endsWith('/start/')) {
      const current = sidebar.locator('a[aria-current="page"]');
      assert(await current.evaluate(el => el.closest('details').open), url + ': current section open');
      assert(await page.locator('nav[aria-label="Путь к уроку"]').count() === 1, url + ': breadcrumbs');
    }
    for (const img of await page.locator('.handbook-content img').all()) {
      await img.scrollIntoViewIfNeeded();
      await img.waitFor({ state: 'visible' });
      assert(await img.evaluate(async el => { await el.decode(); return el.complete && el.naturalWidth > 0; }), url + ': lesson illustration loaded');
    }
    for (const href of await page.locator('a[download]').evaluateAll(links => links.map(a => a.href))) {
      assert((await page.request.get(href)).ok(), url + ': downloadable resource');
    }
    for (const href of await page.locator('a[href], link[href], img[src], script[src]').evaluateAll(els => els.map(el => el.href || el.src))) {
      const target = new URL(href);
      if (target.origin === origin) assert(target.pathname.startsWith(new URL(base).pathname), 'Prefix preserved: ' + href);
    }
  }
  for (const [from, to] of [
    ['python/functions-files/functions-arguments', 'python/functions-files/scope'],
    ['math/linear-algebra/projections', 'math/linear-algebra/linear-decompositions'],
  ]) {
    await page.goto(base + 'handbooks/' + from + '/');
    const next = page.locator('.week-pagination a[rel="next"]');
    assert(await next.count() === 1, from + ': one learning continuation');
    await next.click();
    assert(page.url() === base + 'handbooks/' + to + '/', from + ': current handbook route');
  }
  await page.goto(base + 'handbooks/python/numerical-data/numpy-arrays/');
  assert(new URL(await page.locator('a[download]').first().getAttribute('href'), page.url()).href === base + 'handbooks/python/numerical-data/numpy-arrays/notebook.ipynb', 'Python notebook remains downloadable');
  await page.locator('.handbook-tree').getByRole('link', { name: 'Учебник математики', exact: true }).click();
  assert(page.url() === base + 'handbooks/math/', 'Switch handbooks');
  for (const slug of ['environment', 'classic-ml', 'dl-basics', 'diy-nn', 'how-they-learn', 'advanced-math']) {
    await page.goto(base + 'handbooks/ml/' + slug + '/');
    assert(await page.locator('.section-planned').textContent().then(text => text.includes('Раздел запланирован')), 'ML section is planned: ' + slug);
    assert(await page.locator('.week-pagination a, a[download]').count() === 0, 'No fake ML lessons or downloads');
  }
  for (const path of ['ml/data-experiment/', 'ml/knn/', 'ml/knn/notebook.ipynb', 'ml/classical-models/linear-models/', 'ml/python/numerical-data/numpy-arrays/']) {
    assert((await page.request.get(base + 'handbooks/' + path)).status() === 404, 'Removed ML URL: ' + path);
  }
  await page.goto(base + 'handbooks/ml/start/');
  assert(await page.locator('.week-pagination a').count() === 0, 'ML introduction has no lesson continuation');
  // Старые HTML-адреса сохраняют параметры и якорь, скачивания — байты.
  const legacyLesson = 'python/basic-constructs/input-output/';
  await page.goto(base + 'handbook/' + legacyLesson + '?legacy=1#content');
  await page.waitForURL(base + 'handbooks/' + legacyLesson + '?legacy=1#content');
  for (const resource of ['python/basic-constructs/input-output/notebook.ipynb', 'data/gliders.csv']) {
    const oldFile = await page.request.get(base + 'handbook/' + resource);
    const newFile = await page.request.get(base + 'handbooks/' + resource);
    assert(oldFile.ok() && newFile.ok(), 'Legacy download exists: ' + resource);
    assert(await oldFile.text() === await newFile.text(), 'Legacy download matches: ' + resource);
  }
  await page.goto(base + 'handbook/python/basic-constructs/input-output/notebook.html?legacy=1#content');
  await page.waitForURL(base + 'handbooks/python/basic-constructs/input-output/notebook.html?legacy=1#content');
  assert((await page.request.get(base + 'handbook/ml/knn/')).status() === 404, 'Compatibility does not revive removed ML');
  const lesson = base + 'handbooks/math/linear-algebra/matrices-products/';
  await page.goto(lesson);
  assert(await page.locator('.katex math').count() > 0, 'MathML rendered');
  const solution = page.locator('.handbook-content details summary').filter({ hasText: /^Решение$/ }).first();
  await solution.focus();
  await page.keyboard.press('Enter');
  assert(await solution.evaluate(el => el.parentElement.open), 'Keyboard solution disclosure');
  const heading = page.locator('nav[aria-label="Оглавление урока"] a').first();
  await heading.click();
  assert(new URL(page.url()).hash.length > 1, 'Lesson heading anchor');
  for (const path of ['python/first-programs/', 'python/numpy/', 'math/vectors-distances/']) {
    await page.goto(base + 'handbooks/' + path);
    const transition = page.locator('.lesson-transition a').first();
    assert(await transition.count() === 1, 'Old address: ' + path);
    await transition.click();
    assert(new URL(page.url()).pathname.split('/').filter(Boolean).length === new URL(base + 'handbooks/').pathname.split('/').filter(Boolean).length + 3, 'Legacy target is lesson');
  }
  await page.goto(base + 'handbooks/python/first-programs/#списки-и-циклы');
  assert(await page.locator('#списки-и-циклы a').count() === 1, 'Old fragment has a lesson link');
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme });
    for (const width of [360, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const path of ['python/basic-constructs/input-output/', 'python/numerical-data/numpy-indexing/', 'python/pytorch-tools/datasets-loaders/', 'math/calculus/jacobian-check/', 'math/probability-statistics/density-normal/', 'ml/environment/', 'ml/classic-ml/', 'ml/advanced-math/']) {
        await page.goto(base + 'handbooks/' + path);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), path + ': no page overflow at ' + width);
        if (width < 992) {
          const menu = page.locator('.course-menu');
          assert(!await menu.evaluate(el => el.open), 'Mobile menu initially closed');
          await page.locator('.course-menu > summary').focus();
          await page.keyboard.press('Enter');
          assert(await menu.evaluate(el => el.open), 'Keyboard opens mobile menu');
        }
        const chapter = page.locator('.handbook-chapter').filter({ has: page.locator('a[aria-current="page"]') }).first();
        await chapter.locator(':scope > summary').focus();
        await page.keyboard.press('Enter');
        assert(!await chapter.evaluate(el => el.open), 'Keyboard closes chapter');
        await page.keyboard.press('Enter');
        assert(await chapter.evaluate(el => el.open), 'Keyboard reopens chapter');
      }
      await page.screenshot({ path: `output/playwright/handbook-tree-${colorScheme}-${width}.png`, fullPage: true });
    }
  }
  // Плотность, независимая прокрутка и переносы в обеих темах.
  const inspectNavigation = async (target, width, minimum) => {
    await target.goto(base + 'handbooks/math/probability-statistics/hypotheses/');
    if (width < 992) await target.locator('.course-menu > summary').click();
    await target.waitForFunction(() => {
      const a = document.querySelector('.handbook-tree [aria-current="page"]');
      const b = document.querySelector('.navigation-body').getBoundingClientRect();
      const r = a.getBoundingClientRect();
      return r.top >= b.top && r.bottom <= b.bottom;
    });
    const metrics = await target.evaluate(() => {
      const body = document.querySelector('.navigation-body');
      const top = document.querySelector('.handbook-links');
      const active = document.querySelector('.handbook-tree [aria-current="page"]');
      const heading = active.closest('details').querySelector('summary');
      const before = top.getBoundingClientRect().toJSON();
      const row = active.getBoundingClientRect().toJSON();
      active.removeAttribute('aria-current');
      const unselected = active.getBoundingClientRect().toJSON();
      active.setAttribute('aria-current', 'page');
      body.scrollTop = body.scrollHeight;
      const after = top.getBoundingClientRect().toJSON();
      return {
        pageWidth: document.documentElement.scrollWidth, width: innerWidth,
        topStable: before.top === after.top && before.bottom === after.bottom,
        scrolls: body.scrollHeight > body.clientHeight && getComputedStyle(body).overflowY === 'auto',
        dividers: body.querySelectorAll(':scope > hr').length,
        topBorder: getComputedStyle(top).borderBottomWidth,
        rowStable: row.height === unselected.height && row.width === unselected.width,
        lessonFont: getComputedStyle(active).fontSize,
        titleFont: getComputedStyle(heading).fontSize,
        columns: getComputedStyle(heading).gridTemplateColumns,
        gap: getComputedStyle(heading).columnGap,
        minLink: Math.min(...[...document.querySelectorAll('.handbook-tree a, .handbook-links a')].filter(el => el.getClientRects().length).map(el => el.getBoundingClientRect().height)),
        communityFont: getComputedStyle(document.querySelector('.community-links')).fontSize,
        breadcrumbItems: [...document.querySelectorAll('.breadcrumbs li')].every(el => getComputedStyle(el).display === 'flex'),
      };
    });
    assert(metrics.pageWidth <= metrics.width, 'No horizontal overflow at ' + width);
    assert(metrics.topStable && metrics.scrolls, 'Upper links stay outside tree scroll at ' + width);
    assert(metrics.dividers === 2 && metrics.topBorder === '1px', 'One divider at each navigation boundary');
    assert(metrics.rowStable, 'Current selection does not change row dimensions');
    assert(metrics.lessonFont === '15px' && metrics.titleFont === '16px', 'Explicit tree typography');
    assert(metrics.columns.startsWith('16px ') && metrics.gap === '8px', 'Separate arrow column');
    assert(metrics.minLink >= minimum, 'Clickable row sizes at ' + width);
    assert(metrics.communityFont === '18px', 'Community retains existing typography');
    assert(metrics.breadcrumbItems, 'Breadcrumb separator stays with its item');
  };
  for (const colorScheme of ['light', 'dark']) {
    await page.emulateMedia({ colorScheme });
    for (const width of [360, 390, 768, 992, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await inspectNavigation(page, width, width < 992 ? 44 : 32);
      if ([360, 992, 1440].includes(width)) await page.screenshot({ path: `output/playwright/compact-nav-${colorScheme}-${width}.png` });
    }
  }
  // 200%: та же физическая область, вдвое меньший CSS viewport и DPR=2.
  for (const width of [180, 720]) {
    const zoomContext = await page.context().browser().newContext({ viewport: { width, height: 450 }, deviceScaleFactor: 2 });
    const zoomPage = await zoomContext.newPage();
    await inspectNavigation(zoomPage, width, 44);
    await zoomPage.screenshot({ path: `output/playwright/compact-nav-zoom-${width}.png` });
    await zoomContext.close();
  }
  // Регрессии мобильного оверлея: прокрутка, фокус, Escape и смена ширины.
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto(base + 'handbooks/math/probability-statistics/hypotheses/');
  const overlay = page.locator('.course-menu');
  const toggle = overlay.locator(':scope > summary');
  await toggle.click();
  await page.waitForFunction(() => document.querySelector('.workspace').inert);
  assert(await page.evaluate(() => document.body.style.overflow === 'hidden'), 'Background scroll locked');
  const panel = await overlay.boundingBox();
  assert(panel.y === 0 && panel.height <= 800, 'Overlay fits viewport');
  assert(await overlay.locator('.navigation-body').evaluate(el => el.scrollHeight > el.clientHeight && getComputedStyle(el).overflowY === 'auto'), 'Tree has its own scroll');
  await toggle.focus();
  await page.keyboard.press('Shift+Tab');
  assert(await overlay.evaluate(el => el.contains(document.activeElement) && document.activeElement !== el.querySelector(':scope > summary')), 'Focus wraps to last menu link');
  await page.keyboard.press('Tab');
  assert(await toggle.evaluate(el => el === document.activeElement), 'Focus wraps to close control');
  await page.keyboard.press('Escape');
  assert(!await overlay.evaluate(el => el.open), 'Escape closes overlay');
  assert(!await page.locator('.workspace').evaluate(el => el.inert), 'Content enabled after close');
  assert(await page.evaluate(() => document.body.style.overflow !== 'hidden'), 'Background scroll restored');
  await toggle.click();
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForFunction(() => !document.querySelector('.workspace').inert);
  assert(await overlay.evaluate(el => el.open && getComputedStyle(el).position !== 'fixed'), 'Desktop menu exits overlay mode');
  await page.setViewportSize({ width: 360, height: 800 });
  await page.waitForFunction(() => !document.querySelector('.course-menu').open);
  await toggle.click();
  await overlay.getByRole('link', { name: 'Как пользоваться учебником', exact: true }).click();
  assert(page.url() === base + 'handbooks/math/start/', 'Link navigates to current handbook introduction');
  assert(!await page.locator('.course-menu').evaluate(el => el.open), 'Menu closes on navigation');
  const context = await page.context().browser().newContext({ javaScriptEnabled: false, viewport: { width: 360, height: 900 } });
  const staticPage = await context.newPage();
  await staticPage.goto(base + 'handbook/ml/');
  await staticPage.waitForURL(base + 'handbooks/ml/');
  assert(await staticPage.locator('main h2').count() === 6, 'Legacy ML redirect works without JavaScript');
  await staticPage.goto(base + 'handbooks/python/basic-constructs/input-output/');
  assert(await staticPage.locator('h1').isVisible(), 'Readable without JS');
  const menu = staticPage.locator('.course-menu');
  if (!await menu.evaluate(el => el.open)) await staticPage.locator('.course-menu > summary').click();
  const chapterSummary = staticPage.locator('.handbook-chapter').first().locator(':scope > summary');
  await chapterSummary.focus();
  await staticPage.keyboard.press('Enter');
  await staticPage.keyboard.press('Enter');
  await staticPage.getByRole('link', { name: 'Условия и логические выражения', exact: true }).first().click();
  assert(staticPage.url().includes('/basic-constructs/conditions/'), 'Lesson navigation without JS');
  await staticPage.goto(base + 'handbooks/math/probability-statistics/density-normal/');
  const mathSolution = staticPage.locator('.handbook-content details summary').filter({ hasText: /^Решение$/ }).first();
  await mathSolution.focus();
  await staticPage.keyboard.press('Enter');
  assert(await mathSolution.evaluate(el => el.parentElement.open), 'New mathematics solution works without JS');
  assert(await staticPage.locator('.handbook-content img').evaluate(el => el.complete && el.naturalWidth > 0), 'Mathematics illustration works without JS');
  const mathMenu = staticPage.locator('.course-menu');
  if (!await mathMenu.evaluate(el => el.open)) await staticPage.locator('.course-menu > summary').click();
  await staticPage.getByRole('link', { name: '← На основной сайт', exact: true }).click();
  assert(staticPage.url() === base, 'Return to main site without JS');
  assert(await staticPage.locator('.week-navigation').count() === 1, 'Main site retains week menu');
  await context.close();
  // Проверка каталога после возврата из учебника.
  await page.goto(base + 'materials/');
  await page.locator('input[type="search"]').waitFor();
  const total = await page.locator('.catalog-list > .material:visible').count();
  await page.locator('input[type="search"]').fill('KNN');
  await page.waitForTimeout(250);
  const filtered = await page.locator('.catalog-list > .material:visible').count();
  assert(filtered > 0 && filtered < total, 'Catalog search');
  await page.getByRole('button', { name: 'Лекции', exact: true }).click();
  assert(new URL(page.url()).hash === '#lectures', 'Catalog filter hash');
  await page.goBack();
  assert(new URL(page.url()).hash !== '#lectures', 'Filter history');
  assert(errors.length === 0, 'No page errors: ' + errors.join('; '));
  console.log('Handbook tree, lesson pages and catalog checks passed');
}
