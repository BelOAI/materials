import test from "node:test";
import assert from "node:assert/strict";
import { validateManifest, countLabel, formatDate, filterMaterials } from "./manifest.js";
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
const manifest = (material) => ({ version: 2, materials: [material], course: {
  title: "Подготовка", description: "Описание", weeks: [{ slug: "topic", number: 0,
    title: "Тема", description: "Описание", materials: [material.id] }],
} });
test("валидный и пустой каталог", () => {
  assert.equal(validateManifest(manifest(item()))[0].title, "Тема <&>");
  assert.deepEqual(validateManifest({ version: 2, materials: [], course: { title: "Подготовка", description: "Описание", weeks: [] } }), []);
});
test("версия, структура, повторяющиеся id и тип задания", () => {
  for (const data of [
    null,
    { version: 1, materials: [] },
    { version: 2 },
    manifest({ ...item(), kind: "other" }),
    manifest({ ...item(), kind: "assignment" }),
    { ...manifest(item()), materials: [item(), item()] },
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


test("структура занятий и однозначное назначение материалов", () => {
  for (const mutate of [
    (data) => { delete data.course; },
    (data) => { data.course.weeks = []; },
    (data) => { data.course.weeks[0].slug = "../topic"; },
    (data) => { data.course.weeks[0].number = -1; },
    (data) => { data.course.weeks[0].materials = ["unknown"]; },
    (data) => { data.course.weeks[0].materials.push(item().id); },
    (data) => { data.course.weeks.push({ ...data.course.weeks[0] }); },
    (data) => { data.course.weeks[0].description = ""; },
  ]) {
    const data = manifest(item());
    mutate(data);
    assert.throws(() => validateManifest(data));
  }
});

test("поиск по словам, регистр, подзаголовок и сочетание с фильтром", () => {
  const materials = [
    { ...item(), title: "Машинное обучение", subtitle: "Метрики качества", description: "Работа с данными" },
    { ...item(), id: "practices/01", kind: "practice", title: "NumPy", subtitle: "Матрицы", description: "Работа с данными" },
  ];
  assert.equal(filterMaterials(materials, "all", "  ДАННЫМИ  ").length, 2);
  assert.equal(filterMaterials(materials, "lecture", "данными").length, 1);
  assert.equal(filterMaterials(materials, "all", "качества машинное").length, 1);
  assert.equal(filterMaterials(materials, "all", "матрицы")[0].kind, "practice");
  assert.equal(filterMaterials(materials, "practice", "качества").length, 0);
  assert.equal(filterMaterials(materials, "all", "").length, 2);
});

test("лекция с PDF обязательна после нулевой недели", () => {
  const data = manifest(item());
  data.course.weeks[0].number = 1;
  assert.equal(validateManifest(data).length, 1);
  const practice = { ...item(), id: "01-topic/practice", kind: "practice" };
  data.materials = [practice];
  data.course.weeks[0].materials = [practice.id];
  assert.throws(() => validateManifest(data), /лекцию/);
  data.course.weeks[0].number = 0;
  assert.equal(validateManifest(data).length, 1);
  data.materials = [item(), { ...item(), id: "01-topic/another" }];
  data.course.weeks[0].materials = data.materials.map(item => item.id);
  assert.throws(() => validateManifest(data), /лекцию/);
});
