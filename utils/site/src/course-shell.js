import { ReactiveElement } from "lit";
import { filters } from "./catalog-location.js";

export class CourseShell extends ReactiveElement {
  static properties = { root: {}, page: {} };
  constructor() {
    super();
    this.root = "./";
    this.onSkip = event => {
      if (!event.target.closest?.(".skip-link")) return;
      const content = this.querySelector("main");
      if (!content) return;
      event.preventDefault();
      content.focus({ preventScroll: true });
      content.scrollIntoView({ block: "start", behavior: "instant" });
    };
  }
  createRenderRoot() { return this; }
  connectedCallback() {
    super.connectedCallback();
    this.addEventListener("click", this.onSkip);
    const location = this.ownerDocument.defaultView.location;
    if (this.page === "home" && filters.some(([, , hash]) => hash && hash === location.hash)) {
      location.replace(new URL(`${this.root}materials/${location.search}${location.hash}`, this.baseURI));
    }
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventListener("click", this.onSkip);
  }
}
