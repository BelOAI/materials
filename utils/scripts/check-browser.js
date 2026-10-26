// Запуск: playwright-cli run-code --filename utils/scripts/check-browser.js
async (page) => {
  const base = new URL(await page.locator('body').getAttribute('data-root'), page.url()).href;
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const response = await page.request.get(base + 'materials.json');
  assert(response.ok(), 'Манифест доступен');
  const manifest = await response.json();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(base);
  const weeks = await page.locator('.week-list a').evaluateAll(links => links.map(link => link.href));
  assert(weeks.length === manifest.course.weeks.length, 'Навигация соответствует опубликованным неделям');
  const resources = new Set();
  let capturedFullscreen = false;
  for (const href of weeks) {
    await page.goto(href);
    assert(await page.locator('.week-navigation [aria-current="page"]').count() === 1, 'Активная неделя');
    const sections = await page.locator('.week-resources > li > h2').evaluateAll(headings => headings.map(node => node.id));
    const week = manifest.course.weeks.find(week => href.endsWith(`/weeks/${week.slug}/`));
    const lecture = week.materials.map(id => manifest.materials.find(material => material.id === id)).find(material => material.kind === 'lecture');
    if (week.number !== 0) assert(lecture?.pdf, 'Лекция с PDF после нулевой недели');
    if (lecture?.pdf) {
      assert(sections[0] === 'lecture', 'Лекция предшествует практике и заданиям');
      const viewer = page.locator('lecture-viewer');
      assert(await viewer.evaluate(node => Boolean(node.compareDocumentPosition(node.parentElement.querySelector('[data-kind="lecture"]')) & Node.DOCUMENT_POSITION_FOLLOWING)), 'Слайды выше ссылок на лекцию');
      assert(await page.locator('[data-kind="lecture"] [data-preview]').count() === 0, 'У ссылки на лекцию нет всплывающего превью');
      await viewer.locator('canvas').waitFor();
      assert(await viewer.locator('canvas').getAttribute('aria-label') === 'Слайд 1 из ' + await viewer.locator('input').getAttribute('max'), 'Первая страница отрисована');
      assert(await viewer.locator('.slide-fallback').isHidden(), 'Превью заменено слайдом');
      const checkSlideFrame = async () => {
        const geometry = await viewer.evaluate(node => {
          const frame = node.querySelector('.slide-surface').getBoundingClientRect();
          const canvas = node.querySelector('canvas');
          return { width: frame.width, height: frame.height, fit: getComputedStyle(canvas).objectFit, canvasWidth: canvas.width, canvasHeight: canvas.height, viewportHeight: innerHeight };
        });
        assert(Math.abs(geometry.width / geometry.height - 16 / 9) < .01, 'Область слайдов имеет пропорции 16:9');
        assert(geometry.width <= 961, 'Ширина слайдов ограничена на большом экране');
        assert(geometry.height + 100 <= geometry.viewportHeight, 'Есть место для слайда и управления по высоте окна');
        assert(geometry.fit === 'contain', 'Слайд целиком помещается без обрезки');
        assert(geometry.canvasWidth > 0 && geometry.canvasHeight > 0, 'Слайд отрисован');
      };
      await checkSlideFrame();
      const total = Number(await viewer.locator('input').getAttribute('max'));
      if (total > 1) {
        await viewer.getByRole('button', { name: 'Следующий слайд' }).click();
        await viewer.locator('canvas[aria-label^="Слайд 2 из"]').waitFor();
        await viewer.focus();
        await page.keyboard.press('ArrowLeft');
        await viewer.locator('canvas[aria-label^="Слайд 1 из"]').waitFor();
        await page.keyboard.press('End');
        await viewer.locator(`canvas[aria-label="Слайд ${total} из ${total}"]`).waitFor();
        assert(await viewer.getByRole('button', { name: 'Следующий слайд' }).isDisabled(), 'Граница последнего слайда');
        await viewer.getByRole('spinbutton').fill('1');
        await viewer.getByRole('spinbutton').press('Enter');
        await viewer.getByRole('spinbutton').blur();
        await viewer.locator('canvas[aria-label^="Слайд 1 из"]').waitFor();
      }
      const fullscreenButton = viewer.getByRole('button', { name: 'На весь экран', exact: true });
      await fullscreenButton.click();
      await page.waitForFunction(() => Boolean(document.fullscreenElement || document.querySelector('lecture-viewer.is-fullscreen')));
      assert(await viewer.getByRole('button', { name: 'Выйти из полноэкранного режима' }).getAttribute('aria-pressed') === 'true', 'Состояние полноэкранной кнопки');
      await page.waitForFunction(() => {
        const viewer = document.querySelector('lecture-viewer');
        const frame = viewer.querySelector('.slide-surface').getBoundingClientRect();
        const controls = viewer.querySelector('.slide-controls').getBoundingClientRect();
        return frame.width > 0 && frame.height > 0 && frame.top >= 0 && frame.bottom <= innerHeight && controls.bottom <= innerHeight;
      });
      if (total > 1) {
        await page.keyboard.press('ArrowRight');
        await viewer.locator('canvas[aria-label^="Слайд 2 из"]').waitFor();
        await page.keyboard.press('Home');
        await viewer.locator('canvas[aria-label^="Слайд 1 из"]').waitFor();
      }
      assert(await viewer.locator('.slide-surface').evaluate(node => {
        const box = node.getBoundingClientRect();
        return Math.abs(box.width / box.height - 16 / 9) < .01 && getComputedStyle(node.querySelector('canvas')).objectFit === 'contain';
      }), 'Полноэкранный слайд сохраняет 16:9 и вписывается целиком');
      if (!capturedFullscreen) {
        await page.screenshot({ path: 'output/playwright/course-fullscreen.png' });
        capturedFullscreen = true;
      }
      const exitButton = viewer.getByRole('button', { name: 'Выйти из полноэкранного режима' });
      await exitButton.focus();
      await page.keyboard.press('Tab');
      assert(await viewer.evaluate(node => node.contains(document.activeElement)), 'Tab остаётся в полноэкранном просмотрщике');
      await exitButton.click();
      await page.waitForFunction(() => !document.fullscreenElement && !document.querySelector('lecture-viewer.is-fullscreen'));
      assert(await fullscreenButton.evaluate(node => node === document.activeElement), 'После выхода фокус возвращён на кнопку');
      await fullscreenButton.click();
      await page.waitForFunction(() => Boolean(document.fullscreenElement || document.querySelector('lecture-viewer.is-fullscreen')));
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => !document.fullscreenElement && !document.querySelector('lecture-viewer.is-fullscreen'));
      await checkSlideFrame();
      const widthBefore = await viewer.locator('canvas').getAttribute('width');
      await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForFunction(previous => document.querySelector('lecture-viewer canvas').getAttribute('width') !== previous, widthBefore);
      await checkSlideFrame();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Мобильная страница без горизонтальной прокрутки');
      await page.screenshot({ path: 'output/playwright/course-mobile.png', fullPage: true });
      await page.setViewportSize({ width: 1440, height: 1000 });
    }
    for (const url of await page.locator('.week-resources a').evaluateAll(links => links.map(link => link.href))) {
      if (url.startsWith(base)) resources.add(url);
    }
    for (const relation of ['prev', 'next']) {
      const link = page.locator(`.week-pagination a[rel="${relation}"]`);
      if (await link.count()) assert(weeks.includes(await link.getAttribute('href').then(href => new URL(href, page.url()).href)), 'Соседняя неделя существует');
    }
  }
  for (const url of resources) assert((await page.request.get(url)).ok(), 'Файл доступен: ' + url);
  const lectureWeek = manifest.course.weeks.find(week => week.materials.some(id => manifest.materials.find(material => material.id === id)?.kind === 'lecture'));
  if (lectureWeek) {
    const failurePage = await page.context().newPage();
    await failurePage.route('**/pdfs/**', route => route.fulfill({ status: 404, body: 'Missing PDF' }));
    await failurePage.goto(base + `weeks/${lectureWeek.slug}/`);
    await failurePage.getByRole('status').filter({ hasText: 'Не удалось показать слайды' }).waitFor();
    assert(await failurePage.locator('.slide-fallback').isVisible(), 'Превью сохраняется при ошибке PDF');
    await failurePage.close();
  }

  await page.goto(base + 'materials/');
  await page.locator('catalog-controls input').waitFor();
  const materialCount = await page.locator('.catalog-list > .material').count();
  assert(await page.locator('[data-kind="lecture"] [data-preview]').count() === 0, 'В каталоге у лекций нет всплывающих превью');
  assert(materialCount === manifest.materials.length, 'Все материалы присутствуют в каталоге');
  for (const hash of ['lectures', 'practices', 'assignments']) {
    await page.goto(base + 'materials/#' + hash);
    const kind = { lectures: 'lecture', practices: 'practice', assignments: 'assignment' }[hash];
    await page.waitForFunction(kind => Array.from(document.querySelectorAll('.catalog-list > .material')).every(node => node.hidden || node.dataset.kind === kind), kind);
    assert(await page.locator('.catalog-list > .material:visible').count() === manifest.materials.filter(item => item.kind === kind).length, 'Фильтр ' + hash);
  }
  await page.goto(base + 'materials/?q=unlikely-search-no-matches');
  await page.waitForFunction(() => !Array.from(document.querySelectorAll('.catalog-list > .material')).some(node => !node.hidden));
  await page.goto(base + 'materials/');
  const previewTitle = page.locator('.material-title[data-preview]').first();
  if (await previewTitle.count()) {
    await previewTitle.focus();
    await page.locator('.preview-surface img').waitFor({ state: 'visible' });
    await page.keyboard.press('Escape');
    await page.locator('.preview-surface').waitFor({ state: 'detached' });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'Мобильный каталог без горизонтальной прокрутки');
  if (lectureWeek) {
    for (const rejectRequest of [false, true]) {
      const fallbackContext = await page.context().browser().newContext({ viewport: { width: 390, height: 320 } });
      await fallbackContext.addInitScript(rejectRequest => {
        Object.defineProperty(document, 'fullscreenEnabled', { configurable: true, value: rejectRequest });
        if (rejectRequest) HTMLElement.prototype.requestFullscreen = () => Promise.reject(new DOMException('Fullscreen unavailable', 'NotAllowedError'));
      }, rejectRequest);
      const fallbackPage = await fallbackContext.newPage();
      await fallbackPage.goto(base + `weeks/${lectureWeek.slug}/`);
      await fallbackPage.locator('lecture-viewer canvas').waitFor();
      await fallbackPage.getByRole('button', { name: 'На весь экран', exact: true }).click();
      await fallbackPage.locator('lecture-viewer.is-fullscreen').waitFor();
      assert(await fallbackPage.locator('lecture-viewer').evaluate(viewer => {
        const frame = viewer.querySelector('.slide-surface').getBoundingClientRect();
        const controls = viewer.querySelector('.slide-controls').getBoundingClientRect();
        return Math.abs(frame.width / frame.height - 16 / 9) < .01 && frame.top >= 0 && frame.bottom <= innerHeight && controls.bottom <= innerHeight && getComputedStyle(viewer.querySelector('canvas')).objectFit === 'contain';
      }), 'Разворачивание без Fullscreen API вписывает слайд и управление в короткое окно');
      const total = Number(await fallbackPage.getByRole('spinbutton', { name: 'Номер слайда' }).getAttribute('max'));
      if (total > 1) {
        await fallbackPage.keyboard.press('ArrowRight');
        await fallbackPage.locator('canvas[aria-label^="Слайд 2 из"]').waitFor();
        await fallbackPage.keyboard.press('Home');
        await fallbackPage.locator('canvas[aria-label^="Слайд 1 из"]').waitFor();
      }
      await fallbackPage.keyboard.press('Escape');
      await fallbackPage.locator('lecture-viewer.is-fullscreen').waitFor({ state: 'detached' });
      assert(await fallbackPage.locator('body.slides-fullscreen-open').count() === 0, 'После выхода прокрутка восстановлена');
      await fallbackContext.close();
    }
  }
  const staticContext = await page.context().browser().newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  const staticPage = await staticContext.newPage();
  for (const href of weeks) {
    await staticPage.goto(href);
    assert(await staticPage.locator('.material-title').count() > 0, 'Материалы доступны без JS');
    const fallback = staticPage.locator('.slide-fallback img');
    if (await fallback.count()) assert(await fallback.evaluate(image => image.complete && image.naturalWidth > 0), 'Статическое превью доступно без JS');
  }
  await staticContext.close();
  assert(errors.length === 0, errors.join('\n'));
  return `Проверены ${weeks.length} недель и ${resources.size} ресурсов, слайды, фильтры, клавиатура, мобильная версия и страницы без JS.`;
}
