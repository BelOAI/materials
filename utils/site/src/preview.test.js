import test from "node:test";
import assert from "node:assert/strict";
import { placePreview } from "./preview.js";

const rect = (left, top, right, bottom) => ({ left, top, right, bottom });
function fits(source, viewport, image) {
  const box = placePreview(source, viewport, image);
  assert.ok(box);
  assert.ok(box.left >= 16 && box.top >= 16);
  assert.ok(box.left + box.width <= viewport.width - 16);
  assert.ok(box.top + box.height <= viewport.height - 16);
  assert.ok(box.width <= 300 && box.height <= 362);
  assert.ok(box.left >= source.right || box.left + box.width <= source.left ||
    box.top >= source.bottom || box.top + box.height <= source.top);
  return box;
}
test("сохраняются пропорции горизонтальных, вертикальных и квадратных изображений", () => {
  for (const image of [{ width: 1600, height: 900 }, { width: 600, height: 900 }, { width: 800, height: 800 }]) {
    for (const source of [rect(352, 80, 700, 110), rect(32, 350, 970, 380)]) {
      const box = fits(source, { width: 1024, height: 400 }, image);
      assert.ok(Math.abs((box.width - 2) / (box.height - 2) - image.width / image.height) < 1e-10);
    }
  }
  assert.equal(placePreview(rect(352, 80, 700, 110), { width: 1024, height: 400 }, { width: 0, height: 900 }), null);
});
test("превью включая рамку помещается в короткое окно", () => {
  for (const source of [rect(352, 80, 700, 110), rect(352, 340, 950, 380), rect(32, 350, 970, 380)]) {
    fits(source, { width: 1024, height: 400 });
  }
});
test("длинная ссылка: свободное место сверху или снизу", () => {
  assert.ok(fits(rect(32, 100, 730, 140), { width: 768, height: 1000 }).top > 140);
  const source = rect(32, 800, 730, 830);
  const box = fits(source, { width: 768, height: 1000 });
  assert.ok(box.top + box.height < source.top);
});
test("размер уменьшается до доступной области сбоку", () => {
  const box = fits(rect(210, 100, 700, 140), { width: 920, height: 400 });
  assert.equal(box.width, 192);
});
test("не показывать вне экрана или при недостатке места", () => {
  assert.equal(placePreview(rect(10, -100, 300, -20), { width: 1024, height: 400 }), null);
  assert.equal(placePreview(rect(10, 410, 300, 440), { width: 1024, height: 400 }), null);
  assert.equal(placePreview(rect(10, 20, 750, 60), { width: 768, height: 80 }), null);
});
