import test from "node:test";
import assert from "node:assert/strict";
import { validateManifest, countLabel, formatDate } from "./manifest.js";
const item = () => ({
  id: "lectures/01-topic",
  kind: "lecture",
  number: "1",
  title: "Тема <&>",
  subtitle: "",
  description: "",
  date: "2026-10-10",
  time: "11:00",
  pdf: "pdfs/lectures/01-topic.pdf",
  materials: [],
  references: [],
});
const manifest = (material) => ({ version: 1, materials: [material] });
test("валидный и пустой каталог", () => {
  assert.equal(validateManifest(manifest(item()))[0].title, "Тема <&>");
  assert.deepEqual(validateManifest({ version: 1, materials: [] }), []);
});
test("версия, структура, повторяющиеся id и тип задания", () => {
  for (const data of [
    null,
    { version: 2, materials: [] },
    { version: 1 },
    manifest({ ...item(), kind: "other" }),
    manifest({ ...item(), kind: "assignment" }),
    { version: 1, materials: [item(), item()] },
    manifest({ ...item(), materials: [null] }),
  ]) {
    assert.throws(() => validateManifest(data));
  }
});
test("небезопасные адреса и запись без ресурсов", () => {
  for (const pdf of [
    "javascript:alert(1)",
    "//example.com/a",
    "../a",
    "/a",
    "a\\b",
  ]) {
    assert.throws(() => validateManifest(manifest({ ...item(), pdf })));
  }
  assert.throws(() =>
    validateManifest(manifest({ ...item(), pdf: undefined })),
  );
  assert.throws(() =>
    validateManifest(
      manifest({
        ...item(),
        references: [
          { kind: "custom", label: "Ссылка", url: "javascript:alert(1)" },
        ],
      }),
    ),
  );
});
test("несколько ноутбуков и ссылки без PDF", () => {
  const data = item();
  delete data.pdf;
  data.materials = ["Первый", "Второй"].map((label, i) => ({
    label,
    is_notebook: true,
    download: `materials/${i}.ipynb`,
    open: i ? "" : "materials/0.html",
  }));
  assert.equal(validateManifest(manifest(data))[0].materials.length, 2);
  data.materials = [];
  data.references = [
    { kind: "contest", label: "Задачи", url: "https://example.com" },
  ];
  assert.equal(validateManifest(manifest(data))[0].references.length, 1);
});
test("русские подписи и дата", () => {
  assert.equal(countLabel(1), "1 материал");
  assert.equal(countLabel(2), "2 материала");
  assert.equal(countLabel(11), "11 материалов");
  assert.equal(countLabel(21), "21 материал");
  assert.match(formatDate("2026-10-10"), /10 октября 2026/);
});

test("превью ноутбука без PDF и адрес перехода", () => {
  const data = item();
  delete data.pdf;
  data.kind = "practice";
  data.materials = [
    {
      label: "Ноутбук",
      is_notebook: true,
      download: "materials/a.ipynb",
      open: "materials/a.html",
    },
  ];
  data.thumb = "thumbs/practices/01-topic/a.ipynb.svg";
  data.thumb_href = "materials/a.html";
  assert.equal(
    validateManifest(manifest(data))[0].thumb_href,
    "materials/a.html",
  );
  data.thumb_href = "javascript:alert(1)";
  assert.throws(() => validateManifest(manifest(data)));
  delete data.thumb_href;
  assert.throws(() => validateManifest(manifest(data)));
});
