// PDF.js загружается только на страницах с лекцией.
export class LectureViewer extends HTMLElement {
  connectedCallback() {
    if (this.started) return;
    this.started = true;
    this.pageNumber = 1;
    this.events = new AbortController();
    const { signal } = this.events;
    this.fullscreenActive = false;
    this.pseudoFullscreen = false;
    this.generation = 0;
    this.tabIndex = 0;
    this.setAttribute('role', 'region');
    this.setAttribute('aria-label', 'Слайды лекции');
    this.controls = document.createElement('div');
    this.controls.className = 'slide-controls';
    this.controls.hidden = true;
    this.controls.innerHTML = `<button type="button" data-step="-1" aria-label="Предыдущий слайд">←</button>
      <label>Слайд <input type="number" min="1" value="1" aria-label="Номер слайда"></label>
      <span class="slide-count"></span>
      <button type="button" data-step="1" aria-label="Следующий слайд">→</button>
      <button type="button" class="slide-fullscreen" aria-pressed="false">На весь экран</button>`;
    this.status = document.createElement('p');
    this.status.className = 'slide-status';
    this.status.setAttribute('role', 'status');
    this.status.textContent = 'Загрузка слайдов…';
    this.surface = document.createElement('div');
    this.surface.className = 'slide-surface';
    this.stage = document.createElement('div');
    this.stage.className = 'slide-stage';
    const fallback = this.querySelector('.slide-fallback');
    if (fallback) {
      fallback.hidden = false;
      this.stage.append(fallback);
    }
    this.stage.append(this.surface);
    this.transcript = document.createElement('p');
    this.transcript.className = 'sr-only';
    this.append(this.stage, this.controls, this.status, this.transcript);
    this.controls.addEventListener('click', event => {
      const button = event.target.closest('button[data-step]');
      if (button) this.goTo(this.pageNumber + Number(button.dataset.step));
    });
    this.fullscreenButton = this.controls.querySelector('.slide-fullscreen');
    this.fullscreenButton.addEventListener('click', () => this.toggleFullscreen());
    document.addEventListener('fullscreenchange', () => this.syncFullscreen(), { signal });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && this.isFullscreen) {
        event.preventDefault();
        this.toggleFullscreen();
      }
    }, { signal });
    this.input = this.controls.querySelector('input');
    this.input.addEventListener('change', () => this.goTo(Number(this.input.value)));
    this.addEventListener('keydown', event => {
      if (event.key === 'Tab' && this.isFullscreen && !event.altKey && !event.ctrlKey && !event.metaKey) {
        const controls = [...this.controls.querySelectorAll('button:not(:disabled), input:not(:disabled)')];
        const first = controls[0], last = controls.at(-1);
        const active = document.activeElement;
        if (event.shiftKey && (active === first || !controls.includes(active))) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && (active === last || !controls.includes(active))) {
          event.preventDefault();
          first?.focus();
        }
        return;
      }
      if (event.target instanceof HTMLInputElement || event.altKey || event.ctrlKey || event.metaKey) return;
      const destination = { ArrowLeft: this.pageNumber - 1, ArrowRight: this.pageNumber + 1, Home: 1, End: this.pdf?.numPages }[event.key];
      if (destination === undefined) return;
      event.preventDefault();
      this.goTo(destination);
    }, { signal });
    this.observer = new ResizeObserver(() => {
      if (this.pdf && this.renderWidth !== this.lastWidth) this.goTo(this.pageNumber);
    });
    this.observer.observe(this);
    this.observer.observe(this.surface);
    this.load();
  }

  get renderWidth() {
    return this.surface.clientWidth || this.clientWidth;
  }

  get isFullscreen() {
    return document.fullscreenElement === this || this.pseudoFullscreen;
  }

  async toggleFullscreen() {
    if (this.pseudoFullscreen) {
      this.setPseudoFullscreen(false);
    } else if (document.fullscreenElement === this) {
      try {
        await document.exitFullscreen();
      } catch {
        this.syncFullscreen();
      }
    } else {
      try {
        if (!document.fullscreenEnabled || !this.requestFullscreen) {
          this.setPseudoFullscreen(true);
          return;
        }
        await this.requestFullscreen();
      } catch {
        // В браузерах без Fullscreen API разворачиваем просмотрщик в пределах окна.
        if (this.isConnected) this.setPseudoFullscreen(true);
      }
    }
  }

  setPseudoFullscreen(active) {
    this.pseudoFullscreen = active;
    this.classList.toggle('is-fullscreen', active);
    document.body.classList.toggle('slides-fullscreen-open', active);
    this.syncFullscreen();
  }

  syncFullscreen() {
    const active = this.isFullscreen;
    this.fullscreenButton.textContent = active ? 'Выйти' : 'На весь экран';
    this.fullscreenButton.setAttribute('aria-label', active ? 'Выйти из полноэкранного режима' : 'На весь экран');
    this.fullscreenButton.setAttribute('aria-pressed', String(active));
    if (active !== this.fullscreenActive) {
      this.fullscreenActive = active;
      if (active) this.focus({ preventScroll: true });
      else this.fullscreenButton.focus({ preventScroll: true });
    }
    if (this.pdf) this.goTo(this.pageNumber);
  }

  async load() {
    try {
      const assets = new URL('pdfjs/', import.meta.url);
      const { getDocument, GlobalWorkerOptions } = await import(new URL('pdf.mjs', assets).href);
      if (!this.isConnected) return;
      GlobalWorkerOptions.workerSrc = new URL('pdf.worker.mjs', assets).href;
      this.loading = getDocument({
        url: this.getAttribute('src'),
        cMapUrl: new URL('cmaps/', assets).href,
        cMapPacked: true,
        standardFontDataUrl: new URL('standard_fonts/', assets).href,
        wasmUrl: new URL('wasm/', assets).href,
      });
      this.pdf = await this.loading.promise;
      if (!this.isConnected) return;
      this.input.max = this.pdf.numPages;
      this.controls.querySelector('.slide-count').textContent = `из ${this.pdf.numPages}`;
      this.controls.hidden = false;
      await this.goTo(1);
    } catch (error) {
      if (this.isConnected) this.status.textContent = 'Не удалось показать слайды. Откройте PDF по ссылке под слайдами.';
    }
  }

  async goTo(number) {
    if (!this.pdf) return;
    number = Number.isFinite(number) ? Math.max(1, Math.min(this.pdf.numPages, Math.trunc(number))) : this.pageNumber;
    this.pageNumber = number;
    this.input.value = number;
    this.controls.querySelector('[data-step="-1"]').disabled = number === 1;
    this.controls.querySelector('[data-step="1"]').disabled = number === this.pdf.numPages;
    const generation = ++this.generation;
    this.lastWidth = this.renderWidth;
    try {
      const page = await this.pdf.getPage(number);
      if (generation !== this.generation || !this.isConnected) return;
      const original = page.getViewport({ scale: 1 });
      const width = Math.max(1, this.renderWidth);
      const height = width * 9 / 16;
      const viewport = page.getViewport({ scale: Math.min(width / original.width, height / original.height) });
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      const canvas = document.createElement('canvas');
      canvas.width = Math.floor(viewport.width * ratio);
      canvas.height = Math.floor(viewport.height * ratio);
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', `Слайд ${number} из ${this.pdf.numPages}`);
      const render = page.render({ canvasContext: canvas.getContext('2d'), viewport, transform: [ratio, 0, 0, ratio, 0, 0] });
      await render.promise;
      const text = await page.getTextContent();
      if (generation !== this.generation || !this.isConnected) return;
      this.surface.replaceChildren(canvas);
      this.transcript.textContent = text.items.map(item => item.str).join(' ');
      this.querySelector('.slide-fallback')?.setAttribute('hidden', '');
      this.status.textContent = `Слайд ${number} из ${this.pdf.numPages}`;
    } catch (error) {
      if (generation === this.generation && this.isConnected) this.status.textContent = 'Не удалось показать слайд. Откройте PDF по ссылке под слайдами.';
    }
  }

  disconnectedCallback() {
    ++this.generation;
    this.events?.abort();
    if (this.pseudoFullscreen) {
      document.body.classList.remove("slides-fullscreen-open");
      this.classList.remove("is-fullscreen");
    }
    this.observer?.disconnect();
    this.loading?.destroy();
    this.started = false;
    const fallback = this.querySelector('.slide-fallback');
    if (fallback) this.prepend(fallback);
    this.stage?.remove();
    this.surface?.remove();
    this.controls?.remove();
    this.status?.remove();
    this.transcript?.remove();
  }
}
