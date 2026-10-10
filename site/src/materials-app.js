import { LitElement, html, nothing } from "lit";
import { validateManifest, countLabel, formatDate } from "./manifest.js";

const labels = {
  lecture: "Лекция",
  practice: "Практика",
  assignment: "Домашнее задание",
};
const hashes = {
  "#lectures": "lecture",
  "#practices": "practice",
  "#assignments": "assignment",
};
const filters = [
  ["all", "Все", ""],
  ["lecture", "Лекции", "#lectures"],
  ["practice", "Практики", "#practices"],
  ["assignment", "Задания", "#assignments"],
];

class MaterialRow extends LitElement {
  static properties = { material: { attribute: false } };
  createRenderRoot() {
    return this;
  }
  render() {
    const m = this.material;
    if (!m) return nothing;
    const name = `${labels[m.kind]}${m.number ? ` ${m.number}` : ""}`;
    return html` <article class="session session-${m.kind}">
      ${
        m.thumb
          ? html`<a
              class="thumbnail"
              href=${m.thumb_href || m.pdf}
              aria-label=${`${m.pdf ? "Открыть PDF" : "Открыть ноутбук"}: ${m.title}`}
            >
              <img
                src=${m.thumb}
                alt=${`${m.pdf ? "Первая страница" : "Содержимое ноутбука"}: ${m.title}`}
                loading="lazy"
                decoding="async"
              />
            </a>`
          : nothing
      }
      <div class="session-body">
        <div class="session-heading">
          <span class="session-index">${name}</span>
          ${m.assignment_type ? html`<span class="type-badge">${m.assignment_type === "math" ? "Математика" : "Программирование"}</span>` : nothing}
        </div>
        <h2>${m.title}</h2>
        ${m.subtitle ? html`<p class="subtitle">${m.subtitle}</p>` : nothing}
        ${m.description ? html`<p class="description">${m.description}</p>` : nothing}
        ${
          m.date
            ? html`<p class="date">
                <span>${m.kind === "assignment" ? "Выдано" : "Занятие"}</span>
                <time datetime=${m.date}>${formatDate(m.date)}</time
                >${m.time ? `, ${m.time}` : nothing}
              </p>`
            : nothing
        }
        ${
          m.pdf || m.materials.length
            ? html`<nav class="actions" aria-label=${`Файлы: ${m.title}`}>
                ${m.pdf ? html`<a class="primary" href=${m.pdf}>${m.kind === "assignment" ? "Скачать задание" : "Скачать PDF"}</a>` : nothing}
                ${m.materials.map(
                  (file) => html`
                    ${file.open ? html`<a class=${m.pdf ? "secondary" : "primary"} href=${file.open}>Открыть ${file.label === "Jupyter Notebook" ? "ноутбук" : file.label}</a>` : nothing}
                    ${file.download ? html`<a class="secondary" href=${file.download}>Скачать ${file.label === "Jupyter Notebook" ? ".ipynb" : `${file.label}${file.is_notebook ? " (.ipynb)" : ""}`}</a>` : nothing}
                  `,
                )}
              </nav>`
            : nothing
        }
        ${
          m.references.length
            ? html`<nav class="references" aria-label=${`Ссылки: ${m.title}`}>
                <span class="refs-label">Ссылки</span>
                ${m.references.map(
                  (ref) =>
                    html`<a
                      class=${ref.kind === "contest" ? "contest" : ""}
                      href=${ref.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      >${ref.label}<span class="sr-only">
                        (в новой вкладке)</span
                      ></a
                    >`,
                )}
              </nav>`
            : nothing
        }
      </div>
    </article>`;
  }
}
customElements.define("material-row", MaterialRow);

class MaterialsApp extends LitElement {
  static properties = {
    materials: { state: true },
    status: { state: true },
    filter: { state: true },
  };
  constructor() {
    super();
    this.materials = [];
    this.status = "loading";
    this.filter = hashes[location.hash] || "all";
    this.onHashChange = () => {
      this.filter = hashes[location.hash] || "all";
    };
  }
  createRenderRoot() {
    this.replaceChildren();
    return this;
  }
  connectedCallback() {
    super.connectedCallback();
    window.addEventListener("hashchange", this.onHashChange);
    this.load();
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener("hashchange", this.onHashChange);
    this.request?.abort();
  }
  async load() {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.status = "loading";
    try {
      const response = await fetch("materials.json", {
        signal: request.signal,
      });
      if (!response.ok) throw new Error("Не удалось загрузить манифест");
      const materials = validateManifest(await response.json());
      if (this.request !== request) return;
      this.materials = materials;
      this.status = "ready";
    } catch (error) {
      if (error.name !== "AbortError" && this.request === request)
        this.status = "error";
    }
  }
  selectFilter(kind, hash) {
    if (location.hash !== hash) {
      if (hash) location.hash = hash;
      else {
        history.pushState(null, "", location.pathname + location.search);
      }
    }
    this.filter = kind;
  }
  render() {
    if (this.status === "loading")
      return html`<p class="status" role="status">Загрузка материалов…</p>`;
    if (this.status === "error")
      return html`<div class="status" role="alert">
        <p>Не удалось загрузить материалы.</p>
        <button @click=${this.load}>Попробовать ещё раз</button>
      </div>`;
    const visible = this.materials.filter(
      (m) => this.filter === "all" || m.kind === this.filter,
    );
    return html` <div class="toolbar">
        <nav class="filters" aria-label="Фильтр материалов">
          ${filters.map(
            ([kind, label, hash]) =>
              html`<button
                type="button"
                aria-pressed=${this.filter === kind}
                @click=${() => this.selectFilter(kind, hash)}
              >
                ${label}
              </button>`,
          )}
        </nav>
        <p class="result-count" role="status">${countLabel(visible.length)}</p>
      </div>
      <div class="session-list">
        ${visible.map((material) => html`<material-row .material=${material}></material-row>`)}
        ${!visible.length ? html`<p class="status">${this.materials.length ? "В этом разделе пока нет материалов." : "Пока нет опубликованных материалов."}</p>` : nothing}
      </div>`;
  }
}
customElements.define("materials-app", MaterialsApp);
