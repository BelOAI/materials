export const filters = [
  ["all", "Все", ""],
  ["lecture", "Лекции", "#lectures"],
  ["practice", "Практики", "#practices"],
  ["assignment", "Задания", "#assignments"],
];

export class CatalogLocationController {
  constructor(host, onChange, browser = window) {
    this.host = host;
    this.browser = browser;
    this.onLocation = () => { onChange(this.read()); host.requestUpdate(); };
    host.addController(this);
  }
  hostConnected() {
    this.browser.addEventListener("hashchange", this.onLocation);
    this.browser.addEventListener("popstate", this.onLocation);
    this.onLocation();
  }
  hostDisconnected() {
    this.browser.removeEventListener("hashchange", this.onLocation);
    this.browser.removeEventListener("popstate", this.onLocation);
  }
  read() {
    const url = new URL(this.browser.location.href);
    return {
      query: url.searchParams.get("q") || "",
      filter: filters.find(([, , hash]) => hash === url.hash)?.[0] || "all",
    };
  }
  write(query, filter, replace = false) {
    const url = new URL(this.browser.location.href);
    if (query.trim()) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    url.hash = filters.find(([kind]) => kind === filter)?.[2] || "";
    if (url.href !== this.browser.location.href) {
      this.browser.history[replace ? "replaceState" : "pushState"](null, "", url);
    }
  }
}
