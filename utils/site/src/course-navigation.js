import { ReactiveElement } from "lit";
import { MediaQueryController } from "./media-query.js";

export class CourseNavigation extends ReactiveElement {
  constructor() {
    super();
    this.mobile = new MediaQueryController(this, "(max-width: 991.98px)", () => this.syncMenu());
    this.onToggle = () => this.syncOverlay();
    this.onKeydown = event => {
      if (!this.overlayOpen) return;
      if (event.key === "Escape") {
        event.preventDefault();
        this.closeMenu();
      } else if (event.key === "Tab") {
        const items = [...this.menu.querySelectorAll('summary, a[href], button, [tabindex]')]
          .filter(el => el.tabIndex >= 0 && !el.disabled && el.getClientRects().length);
        const first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus();
        }
      }
    };
    this.onNavigate = event => {
      if (this.overlayOpen && event.target.closest('a[href]')) this.closeMenu();
    };
  }
  createRenderRoot() { return this; }
  connectedCallback() {
    super.connectedCallback();
    this.menu = this.querySelector('.course-menu');
    this.handbook = document.body.dataset.page === 'handbook';
    if (this.handbook) {
      this.closest('.sidebar')?.classList.add('handbook-sidebar');
      this.menu?.setAttribute('data-overlay', '');
      this.menu?.addEventListener('toggle', this.onToggle);
      this.menu?.addEventListener('click', this.onNavigate);
      document.addEventListener('keydown', this.onKeydown);
    }
    this.syncMenu();
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    cancelAnimationFrame(this.scrollFrame);
    this.menu?.removeEventListener('toggle', this.onToggle);
    this.menu?.removeEventListener('click', this.onNavigate);
    document.removeEventListener('keydown', this.onKeydown);
    this.setOverlay(false);
    this.closest('.sidebar')?.classList.remove('handbook-sidebar');
  }
  syncMenu() {
    const menu = this.querySelector('.course-menu');
    if (menu) menu.open = !this.mobile.matches;
    this.syncOverlay();
    cancelAnimationFrame(this.scrollFrame);
    if (!this.mobile.matches) this.scrollFrame = requestAnimationFrame(() => this.revealCurrentLesson());
  }
  closeMenu() {
    this.menu.open = false;
    this.syncOverlay();
    this.menu.querySelector(':scope > summary')?.focus();
  }
  syncOverlay() { this.setOverlay(Boolean(this.handbook && this.mobile.matches && this.menu?.open)); }
  setOverlay(open) {
    if (open === Boolean(this.overlayOpen)) return;
    this.overlayOpen = open;
    cancelAnimationFrame(this.scrollFrame);
    if (open) {
      this.previousOverflow = document.body.style.overflow;
      this.scrollFrame = requestAnimationFrame(() => this.revealCurrentLesson());
    }
    document.body.style.overflow = open ? 'hidden' : this.previousOverflow ?? '';
    for (const el of document.querySelectorAll('.workspace, .sidebar > header, .skip-link')) el.inert = open;
  }
  revealCurrentLesson() {
    const current = this.querySelector('.handbook-navigation a[aria-current="page"]');
    const sidebar = this.menu.querySelector('.navigation-body');
    if (!current || !sidebar || !sidebar.contains(current)) return;
    const area = sidebar.getBoundingClientRect();
    const position = current.getBoundingClientRect();
    if (position.bottom > area.bottom - 24 || position.top < area.top + 24) {
      const offset = Math.max(0, (area.height - position.height) / 2);
      sidebar.scrollTop += position.top - area.top - offset;
    }
  }
}
