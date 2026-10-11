const kinds = ["lecture", "practice", "assignment"];
const textFields = [
  "id",
  "number",
  "title",
  "subtitle",
  "description",
  "date",
  "time",
];
const isObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const isString = (value) => typeof value === "string";
const localUrl = (value) =>
  isString(value) &&
  value.length > 0 &&
  !/^(?:[a-z][a-z\d+.-]*:|\/|\\)/i.test(value) &&
  !value.split("/").some((part) => part === "..") &&
  !value.includes("\\");
const externalUrl = (value) => {
  if (!isString(value)) return false;
  try {
    return ["https:", "http:"].includes(new URL(value).protocol);
  } catch {
    return false;
  }
};

export function validateManifest(data) {
  if (!isObject(data) || data.version !== 2 || !Array.isArray(data.materials)) {
    throw new Error("Неподдерживаемый манифест");
  }
  const ids = new Set();
  for (const item of data.materials) {
    if (
      !isObject(item) ||
      !textFields.every((key) => isString(item[key])) ||
      !item.id ||
      ids.has(item.id) ||
      !kinds.includes(item.kind) ||
      (item.kind === "assignment" &&
        !["math", "coding"].includes(item.assignment_type)) ||
      ("thumb" in item && !(item.thumb_href || item.pdf)) ||
      ["pdf", "thumb", "thumb_href"].some(
        (key) => key in item && !localUrl(item[key]),
      ) ||
      !Array.isArray(item.materials) ||
      !Array.isArray(item.references)
    ) {
      throw new Error("Некорректная запись материала");
    }
    ids.add(item.id);
    for (const file of item.materials) {
      if (
        !isObject(file) ||
        !isString(file.label) ||
        typeof file.is_notebook !== "boolean" ||
        !["download", "open"].every(
          (key) => isString(file[key]) && (!file[key] || localUrl(file[key])),
        ) ||
        (!file.download && !file.open)
      )
        throw new Error("Некорректный файл");
    }
    for (const ref of item.references) {
      if (
        !isObject(ref) ||
        !isString(ref.kind) ||
        !isString(ref.label) ||
        !ref.label ||
        !externalUrl(ref.url)
      )
        throw new Error("Некорректная ссылка");
    }
    if (!item.pdf && !item.materials.length && !item.references.length) {
      throw new Error("Материал без ресурсов");
    }
  }
  const course = data.course;
  if (!isObject(course) || !["title", "description"].every(
    (key) => isString(course[key]) && course[key].trim(),
  ) || !Array.isArray(course.weeks)) throw new Error("Некорректный курс");
  const assigned = new Set();
  const slugs = new Set();
  const numbers = new Set();
  for (const week of course.weeks) {
    if (!isObject(week) || !isString(week.slug) ||
      !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(week.slug) || slugs.has(week.slug) ||
      !Number.isInteger(week.number) || week.number < 0 || numbers.has(week.number) ||
      !["title", "description"].every((key) => isString(week[key]) && week[key].trim()) ||
      !Array.isArray(week.materials) || !week.materials.length) {
      throw new Error("Некорректная неделя");
    }
    slugs.add(week.slug);
    numbers.add(week.number);
    for (const id of week.materials) {
      if (!ids.has(id) || assigned.has(id)) throw new Error("Некорректное назначение материала");
      assigned.add(id);
    }
  }
  if (assigned.size !== ids.size) throw new Error("Материал без недели");
  return data.materials;
}

export function filterMaterials(materials, kind, query) {
  const words = query.toLocaleLowerCase("ru").trim().split(/\s+/).filter(Boolean);
  return materials.filter((material) => {
    const text = [material.title, material.subtitle, material.description]
      .join(" ").toLocaleLowerCase("ru");
    return (kind === "all" || material.kind === kind) && words.every((word) => text.includes(word));
  });
}

export function countLabel(count) {
  const mod100 = count % 100;
  const mod10 = count % 10;
  const word =
    mod100 >= 11 && mod100 <= 19
      ? "материалов"
      : mod10 === 1
        ? "материал"
        : mod10 >= 2 && mod10 <= 4
          ? "материала"
          : "материалов";
  return `${count} ${word}`;
}

export function formatDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ru-RU", {
        timeZone: "UTC",
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(date);
}
