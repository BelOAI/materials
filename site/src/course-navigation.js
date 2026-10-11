import { ReactiveElement } from "lit";
import { MediaQueryController } from "./media-query.js";

export class CourseNavigation extends ReactiveElement {
  constructor() {
    super();
    this.mobile = new MediaQueryController(this, "(max-width: 991.98px)", () => this.syncMenu());
  }
  createRenderRoot() { return this; }
  connectedCallback() { super.connectedCallback(); this.syncMenu(); }
  syncMenu() {
    const menu = this.querySelector(".course-menu");
    if (menu) menu.open = !this.mobile.matches;
  }
}
