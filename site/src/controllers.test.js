import test from "node:test";
import assert from "node:assert/strict";
import { MediaQueryController } from "./media-query.js";
import { CatalogLocationController } from "./catalog-location.js";

const host = () => ({ addController(controller) { this.controller = controller; }, requestUpdate() {} });

test("Media subscription is cleaned up and reconnects once", () => {
  const media = new EventTarget();
  media.matches = false;
  let calls = 0;
  const controller = new MediaQueryController(host(), "test", () => calls++, () => media);
  controller.hostConnected();
  media.dispatchEvent(new Event("change"));
  assert.equal(calls, 1);
  controller.hostDisconnected();
  media.dispatchEvent(new Event("change"));
  assert.equal(calls, 1);
  controller.hostConnected();
  media.dispatchEvent(new Event("change"));
  assert.equal(calls, 2);
  controller.hostDisconnected();
});

function browser() {
  const result = new EventTarget();
  result.location = { href: "https://example.org/materials/materials/?other=keep&q=numpy#practices" };
  result.writes = [];
  result.history = Object.fromEntries(["pushState", "replaceState"].map(method => [method, (_state, _title, url) => {
    result.writes.push(method);
    result.location.href = url.href;
  }]));
  return result;
}

test("Catalog URL retains unrelated parameters and distinguishes input from filter", () => {
  const view = browser();
  const controller = new CatalogLocationController(host(), () => {}, view);
  assert.deepEqual(controller.read(), { query: "numpy", filter: "practice" });
  controller.write("матрицы", "lecture", true);
  assert.equal(new URL(view.location.href).searchParams.get("other"), "keep");
  assert.equal(new URL(view.location.href).hash, "#lectures");
  controller.write("", "all");
  assert.equal(new URL(view.location.href).searchParams.has("q"), false);
  assert.deepEqual(view.writes, ["replaceState", "pushState"]);
  controller.write("", "all");
  assert.equal(view.writes.length, 2);
});

test("Catalog URL subscriptions clean up and reread state on reconnect", () => {
  const view = browser();
  const states = [];
  const controller = new CatalogLocationController(host(), state => states.push(state), view);
  controller.hostConnected();
  view.dispatchEvent(new Event("popstate"));
  assert.equal(states.length, 2);
  controller.hostDisconnected();
  view.dispatchEvent(new Event("hashchange"));
  assert.equal(states.length, 2);
  view.location.href = "https://example.org/materials/?q=test#assignments";
  controller.hostConnected();
  assert.deepEqual(states.at(-1), { query: "test", filter: "assignment" });
  view.dispatchEvent(new Event("hashchange"));
  assert.equal(states.length, 4);
  controller.hostDisconnected();
});
