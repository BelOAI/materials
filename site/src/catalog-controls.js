import { LitElement, html, nothing } from "lit";
import { countLabel } from "./manifest.js";
import { filters } from "./catalog-location.js";

let nextSearchId = 0;
export class CatalogControls extends LitElement {
  static properties = {
    query: {}, filter: {}, status: {}, count: { type: Number }, total: { type: Number },
  };
  constructor() {
    super();
    this.query = "";
    this.filter = "all";
    this.status = "loading";
    this.count = this.total = 0;
    this.searchId = `material-search-${++nextSearchId}`;
  }
  createRenderRoot() { return this; }
  emit(type, detail = {}) {
    this.dispatchEvent(new CustomEvent(type, { detail, bubbles: true, composed: true }));
  }
  render() {
    if (this.status === "loading") return html`<p class="status" role="status">Загрузка поиска…</p>`;
    if (this.status === "error") return html`<div class="status" role="alert">
      <p>Поиск недоступен. Все материалы показаны ниже.</p>
      <button type="button" @click=${() => this.emit("catalog-retry")}>Попробовать ещё раз</button>
    </div>`;
    return html`<div class="catalog-toolbar">
      <label class="search-label" for=${this.searchId}>Поиск по материалам</label>
      <input id=${this.searchId} type="search" .value=${this.query}
        placeholder="Название или тема" @input=${(event) => {
          this.emit("query-change", { query: event.target.value });
        }} />
      <nav class="filters" aria-label="Фильтр материалов">
        ${filters.map(([kind, label]) => html`<button type="button" aria-pressed=${this.filter === kind}
          @click=${() => { this.emit("filter-change", { filter: kind }); }}>${label}</button>`)}
      </nav>
      <p class="result-count" role="status" aria-live="polite">${countLabel(this.count)}</p>
      ${!this.count && this.total ? html`<p>Материалы не найдены.
        <button class="text-button" @click=${() => {
          this.emit("catalog-reset");
        }}>Сбросить поиск</button></p>` : nothing}
    </div>`;
  }
}
