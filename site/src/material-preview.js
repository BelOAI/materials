import { LitElement, html, nothing } from "lit";
import { placePreview } from "./preview.js";
import { MediaQueryController } from "./media-query.js";

export class MaterialPreview extends LitElement {
  static properties = { targetId: { attribute: "for" }, source: { state: true }, label: { state: true } };
  constructor() {
    super();
    this.source = "";
    this.imageSizes = new Map();
    this.dismissed = new WeakSet();
    this.targetId = "content";
    this.capable = new MediaQueryController(this, "(min-width: 761px) and (hover: hover) and (pointer: fine)", () => this.syncPreview());
    this.onPointerOver = (event) => {
      if (this.contains(event.target)) {
        this.hoveredPreview = true;
      } else {
        const anchor = event.target.closest?.("a[data-preview]");
        if (!anchor) return;
        if (anchor !== this.hoveredAnchor) this.dismissed.delete(anchor);
        this.hoveredAnchor = anchor;
        this.hoveredPreview = false;
      }
      this.syncPreview();
    };
    this.onPointerOut = (event) => {
      const anchor = event.target.closest?.("a[data-preview]");
      if (anchor && !anchor.contains(event.relatedTarget)) {
        if (anchor === this.hoveredAnchor) this.hoveredAnchor = null;
      } else if (this.contains(event.target)) {
        if (this.contains(event.relatedTarget)) return;
        this.hoveredPreview = false;
      } else return;
      if (this.contains(event.relatedTarget)) this.hoveredPreview = true;
      this.deferPreview();
    };
    this.onFocusIn = (event) => {
      const anchor = event.target.closest?.("a[data-preview]");
      if (!anchor) return;
      this.focusedAnchor = anchor;
      this.dismissed.delete(anchor);
      this.syncPreview();
    };
    this.onFocusOut = (event) => {
      if (!this.focusedAnchor?.contains(event.target)) return;
      if (this.focusedAnchor.contains(event.relatedTarget)) return;
      this.focusedAnchor = null;
      this.deferPreview();
    };
    this.onKey = (event) => {
      if (event.key !== "Escape" || !this.source) return;
      for (const anchor of [this.anchor, this.focusedAnchor, this.hoveredAnchor]) {
        if (anchor) this.dismissed.add(anchor);
      }
      this.hide();
    };
    this.onViewport = () => this.syncPreview();
    this.onLoad = (event) => {
      const image = event.target;
      if (image.getAttribute("src") !== this.source) return;
      this.imageSizes.set(this.source, { width: image.naturalWidth, height: image.naturalHeight });
      this.syncPreview();
      this.requestUpdate();
    };
    this.onError = () => {
      if (this.anchor) this.dismissed.add(this.anchor);
      this.hide();
    };
  }
  createRenderRoot() { return this; }
  connectedCallback() {
    super.connectedCallback();
    this.target = this.ownerDocument.getElementById(this.targetId);
    for (const scope of [this.target, this]) {
      scope?.addEventListener("pointerover", this.onPointerOver);
      scope?.addEventListener("pointerout", this.onPointerOut);
    }
    this.target?.addEventListener("focusin", this.onFocusIn);
    this.target?.addEventListener("focusout", this.onFocusOut);
    this.ownerDocument.addEventListener("keydown", this.onKey);
    window.addEventListener("resize", this.onViewport);
    window.addEventListener("scroll", this.onViewport, true);
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this.hideTimer);
    for (const scope of [this.target, this]) {
      scope?.removeEventListener("pointerover", this.onPointerOver);
      scope?.removeEventListener("pointerout", this.onPointerOut);
    }
    this.target?.removeEventListener("focusin", this.onFocusIn);
    this.target?.removeEventListener("focusout", this.onFocusOut);
    this.ownerDocument.removeEventListener("keydown", this.onKey);
    window.removeEventListener("resize", this.onViewport);
    window.removeEventListener("scroll", this.onViewport, true);
    this.focusedAnchor = this.hoveredAnchor = null;
    this.hoveredPreview = false;
    this.hide();
  }
  deferPreview() {
    clearTimeout(this.hideTimer);
    if (this.focusedAnchor && !this.dismissed.has(this.focusedAnchor)) this.syncPreview();
    else this.hideTimer = setTimeout(() => this.syncPreview(), 160);
  }
  syncPreview() {
    clearTimeout(this.hideTimer);
    const anchor = [this.focusedAnchor, this.hoveredAnchor, this.hoveredPreview ? this.anchor : null]
      .find((candidate) => candidate?.isConnected && !this.dismissed.has(candidate));
    if (!anchor || !this.capable.matches) return this.hide();
    const placement = placePreview(anchor.getBoundingClientRect(), { width: innerWidth, height: innerHeight },
      this.imageSizes.get(anchor.dataset.preview));
    if (!placement) return this.hide();
    for (const [key, value] of Object.entries(placement)) {
      this.style.setProperty(`--preview-${key}`, `${value}px`);
    }
    this.anchor = anchor;
    this.label = anchor.textContent;
    this.source = anchor.dataset.preview;
  }
  hide() { clearTimeout(this.hideTimer); this.source = ""; this.anchor = null; }
  render() {
    return this.source ? html`<div class="preview-surface" style=${this.imageSizes.has(this.source) ? "" : "visibility: hidden"}><img src=${this.source}
      alt=${`Превью: ${this.label}`} @load=${this.onLoad} @error=${this.onError} /></div>` : nothing;
  }
}
