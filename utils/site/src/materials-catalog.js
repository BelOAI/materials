import { ReactiveElement } from "lit";
import { validateManifest, filterMaterials } from "./manifest.js";
import { CatalogLocationController } from "./catalog-location.js";

export class MaterialsCatalog extends ReactiveElement {
  static properties = {
    root: {}, query: { state: true }, filter: { state: true }, status: { state: true },
  };
  constructor() {
    super();
    this.root = "./";
    this.materials = [];
    this.status = "loading";
    this.locationState = new CatalogLocationController(this, state => {
      this.query = state.query;
      this.filter = state.filter;
    });
    this.onControl = event => {
      if (event.target !== this.controls) return;
      if (event.type === "catalog-retry") return this.load();
      if (event.type === "query-change") this.query = event.detail.query;
      if (event.type === "filter-change") this.filter = event.detail.filter;
      if (event.type === "catalog-reset") { this.query = ""; this.filter = "all"; }
      this.locationState.write(this.query, this.filter, event.type === "query-change");
    };
  }
  createRenderRoot() { return this; }
  get controls() { return this.querySelector(":scope > catalog-controls"); }
  rows() { return this.querySelectorAll(":scope > .catalog-list > .material"); }
  showAll() { this.rows().forEach(row => { row.hidden = false; }); }
  connectedCallback() {
    super.connectedCallback();
    for (const type of ["query-change", "filter-change", "catalog-reset", "catalog-retry"]) {
      this.addEventListener(type, this.onControl);
    }
    this.load();
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    for (const type of ["query-change", "filter-change", "catalog-reset", "catalog-retry"]) {
      this.removeEventListener(type, this.onControl);
    }
    this.request?.abort();
    this.request = null;
    this.showAll();
  }
  async load() {
    this.request?.abort();
    const request = new AbortController();
    this.request = request;
    this.status = "loading";
    this.showAll();
    try {
      const response = await fetch(new URL(`${this.root}materials.json`, this.baseURI), { signal: request.signal });
      if (!response.ok) throw new Error("Не удалось загрузить манифест");
      const materials = validateManifest(await response.json());
      if (request !== this.request || !this.isConnected) return;
      this.materials = materials;
      this.status = "ready";
    } catch (error) {
      if (error.name !== "AbortError" && request === this.request && this.isConnected) {
        this.status = "error";
        this.showAll();
      }
    }
  }
  updated() {
    if (!this.isConnected) return;
    let count = this.rows().length;
    if (this.status === "ready") {
      const visible = new Set(filterMaterials(this.materials, this.filter, this.query).map(m => m.id));
      count = 0;
      this.rows().forEach(row => {
        row.hidden = !visible.has(row.dataset.id);
        if (!row.hidden) count++;
      });
    }
    if (this.controls) Object.assign(this.controls, {
      query: this.query, filter: this.filter, status: this.status, count, total: this.materials.length,
    });
  }
}
