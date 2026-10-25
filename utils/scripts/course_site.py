"""Структура занятий и статические страницы с прогрессивным улучшением."""

from __future__ import annotations

import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path
from string import Template

from meta_parser import get_flat, parse_meta
from authorship import normalize_authors, authors_html

KINDS = {"lecture": "Лекции", "practice": "Практики", "assignment": "Задания"}
LABELS = {"lecture": "Лекция", "practice": "Практика", "assignment": "Задание"}


def load_course(root: Path, entries: list[dict]) -> dict:
    course = json.loads((root / "course/course.json").read_text(encoding="utf-8"))
    if (
        not isinstance(course, dict)
        or not all(
            isinstance(course.get(key), str) and course[key].strip()
            for key in ("title", "description")
        )
        or not isinstance(course.get("weeks"), list)
    ):
        raise ValueError("Некорректная структура course.json")
    known, public = set(), set()
    for kind in ("lectures", "practices", "assignments"):
        for meta_path in (root / "course" / kind).glob("*/meta.yaml"):
            if meta_path.parent.name.startswith("_"):
                continue
            identifier = f"{kind}/{meta_path.parent.name}"
            known.add(identifier)
            meta = parse_meta(meta_path)
            if all(
                get_flat(meta, key, default).lower() != value
                for key, default, value in (
                    ("build", "true", "false"),
                    ("hidden", "false", "true"),
                )
            ):
                public.add(identifier)
    assigned, slugs, numbers = set(), set(), set()
    available = {entry["slug"] for entry in entries}
    weeks = []
    for week in course["weeks"]:
        if (
            not isinstance(week, dict)
            or not all(
                isinstance(week.get(key), str) and week[key].strip()
                for key in ("slug", "title", "description")
            )
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", week["slug"])
        ):
            raise ValueError("Некорректная неделя в course.json")
        number = week.get("number")
        if (
            type(number) is not int
            or number < 0
            or number in numbers
            or week["slug"] in slugs
        ):
            raise ValueError("Номера и slug недель должны быть уникальными")
        ids = week.get("materials")
        if not isinstance(ids, list) or not all(
            isinstance(identifier, str) for identifier in ids
        ):
            raise ValueError(
                "Неделя должна содержать список идентификаторов материалов"
            )
        for identifier in ids:
            if identifier not in known:
                raise ValueError(f"Неизвестный материал: {identifier}")
            if identifier in assigned:
                raise ValueError(f"Материал назначен повторно: {identifier}")
            assigned.add(identifier)
        slugs.add(week["slug"])
        numbers.add(number)
        visible = [
            identifier
            for identifier in ids
            if identifier in available and identifier in public
        ]
        if visible:
            weeks.append(
                {key: week[key] for key in ("slug", "number", "title", "description")}
                | {"materials": visible}
            )
    missing = public - assigned
    if missing:
        raise ValueError("Материалы без недели: " + ", ".join(sorted(missing)))
    return {
        "title": course["title"],
        "description": course["description"],
        "weeks": weeks,
    }


def link(href: str, label: str, attributes: str = "") -> str:
    return f'<a href="{escape(href, quote=True)}"{attributes}>{escape(label)}</a>'


def date_label(value: str) -> str:
    months = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    try:
        parsed = date.fromisoformat(value)
        return f"{parsed.day} {months[parsed.month - 1]} {parsed.year}"
    except ValueError:
        return value


def render_material(material: dict, root: str, show_description: bool = False) -> str:
    m = material
    resources = []
    if m.get("pdf"):
        resources.append(link(root + m["pdf"], "PDF"))
    for file in m["materials"]:
        label = "Ноутбук" if file["label"] == "Jupyter Notebook" else file["label"]
        if file["open"]:
            resources.append(link(root + file["open"], f"Открыть: {label}"))
        if file["download"]:
            suffix = " (.ipynb)" if file["is_notebook"] else ""
            resources.append(
                link(root + file["download"], f"Скачать: {label}{suffix}", " download")
            )
    files = (
        '<ul class="resource-links">'
        + "".join(f"<li>{resource}</li>" for resource in resources)
        + "</ul>"
        if resources
        else ""
    )
    references = (
        '<ul class="resource-links references">'
        + "".join(
            f'<li>{link(ref["url"], ref["label"])}</li>' for ref in m["references"]
        )
        + "</ul>"
        if m["references"]
        else ""
    )
    first_file = next(
        (file for file in m["materials"] if file["is_notebook"]),
        next(iter(m["materials"]), None),
    )
    target = m.get("pdf") or (
        first_file["open"] or first_file["download"] if first_file else ""
    )
    target = root + target if target else m["references"][0]["url"]
    preview = (
        f' data-preview="{escape(root + m["thumb"], quote=True)}"'
        if m.get("thumb")
        else ""
    )
    name = link(target, m["title"], ' class="material-title"' + preview)
    label = f'{LABELS[m["kind"]]} {m["number"]}'.strip()
    if m.get("assignment_type"):
        label += " · " + (
            "Математика" if m["assignment_type"] == "math" else "Программирование"
        )
    date_html = (
        f'<time datetime="{escape(m["date"], quote=True)}">{escape(date_label(m["date"]))}</time>'
        if m["date"]
        else ""
    )
    if m["time"]:
        date_html += (", " if date_html else "") + escape(m["time"])
    description = m["description"] or m["subtitle"]
    meta = escape(label) + (" · " + date_html if date_html else "")
    return f"""<li class="material" data-id="{escape(m['id'], quote=True)}" data-kind="{m['kind']}">
      {name} <span class="material-meta">({meta})</span>
      {f'<p class="material-description">{escape(description)}</p>' if show_description and description else ''}
      {authors_html(m.get('_authors'))}
      {files}{references}
    </li>"""


def write_page(
    source: Path, output: Path, weeks: list,
    path: str, title: str, description: str, content: str, active: str, root: str,
    extra_navigation: str = "",
    *, navigation_override: str | None = None, navigation_top: str = "",
    brand_href: str | None = None, navigation_label: str = "Навигация по материалам",
) -> None:
    about = link(
        root, "О подготовке", ' aria-current="page"' if active == "home" else ""
    )
    nav = "<ul><li>" + about + '</li></ul><hr><ul class="week-navigation">'
    for week in weeks:
        current = ' aria-current="page"' if active == week["slug"] else ""
        href = escape(root + f'weeks/{week["slug"]}/', quote=True)
        nav += (
            f'<li><a href="{href}" title="{escape("Неделя " + str(week["number"]) + " · " + week["title"], quote=True)}"{current}>Неделя {week["number"]} '
            f'<span class="nav-topic">{escape(week["title"])}</span></a></li>'
        )
    nav += (
        "</ul><hr><ul><li>"
        + link(
            root + "materials/",
            "Все материалы",
            ' aria-current="page"' if active == "catalog" else "",
        )
        + '</li>'
        + '<li><a href="https://github.com/BelOAI/materials">Исходники на GitHub</a></li></ul>'
    )
    nav = navigation_override if navigation_override is not None else nav + extra_navigation
    template = Template((source / "utils/site/index.html").read_text(encoding="utf-8"))
    html = template.substitute(
        title=escape(title),
        description=escape(description, quote=True),
        root=root,
        page=active,
        content=content,
        navigation=nav,
        navigation_top=navigation_top,
        navigation_class="handbook-navigation" if active == "handbook" else "",
        brand_href=escape(brand_href if brand_href is not None else root, quote=True),
        navigation_label=escape(navigation_label, quote=True),
        license_current=' aria-current="page"' if path == "license" else "",
    )
    dest = output / path / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")


def publish_pages(source: Path, output: Path, manifest: dict) -> None:
    course = manifest["course"]
    weeks = course["weeks"]
    materials = {}
    for item in manifest['materials']:
        meta = source / 'course' / item['id'] / 'meta.yaml'
        authors = normalize_authors(parse_meta(meta).get('authors')) if meta.is_file() else []
        materials[item['id']] = dict(item, _authors=authors)
    # Не оставляем страницы удалённых или скрытых недель.
    shutil.rmtree(output / "weeks", ignore_errors=True)

    def page(*args):
        write_page(source, output, weeks, *args)

    overview = '<ul class="week-list">'
    for week in weeks:
        href = f'weeks/{week["slug"]}/'
        number = link(href, "Неделя " + str(week["number"]))
        overview += f'<li>{number} — {escape(week["title"])}</li>'
    overview += "</ul>"
    page(
        "",
        course["title"],
        course["description"],
        f'<h1>О подготовке</h1><p>{escape(course["description"])}</p>'
        f'<h2>Темы занятий</h2>{overview if weeks else "<p>Материалы для подготовки пока не опубликованы.</p>"}',
        "home",
        "./",
    )
    for index, week in enumerate(weeks):
        content = f'<h1>Неделя {week["number"]} <span class="heading-topic">{escape(week["title"])}</span></h1><p>{escape(week["description"])}</p><ul class="week-resources">'
        for kind, label in KINDS.items():
            selected = [
                materials[identifier]
                for identifier in week["materials"]
                if materials[identifier]["kind"] == kind
            ]
            if selected:
                content += f'<li><span id="{kind}">{label}</span><ul>'
                content += (
                    "".join(render_material(m, "../../") for m in selected)
                    + "</ul></li>"
                )
        content += "</ul>"
        neighbors = []
        if index:
            prev = weeks[index - 1]
            neighbors.append(
                link(
                    f'../{prev["slug"]}/',
                    f'← Неделя {prev["number"]} · {prev["title"]}',
                    ' rel="prev"',
                )
            )
        if index + 1 < len(weeks):
            nxt = weeks[index + 1]
            neighbors.append(
                link(
                    f'../{nxt["slug"]}/',
                    f'Неделя {nxt["number"]} · {nxt["title"]} →',
                    ' rel="next"',
                )
            )
        content += (
            '<nav class="week-pagination" aria-label="Предыдущая и следующая недели">'
            + "".join(neighbors)
            + "</nav>"
        )
        page(
            f'weeks/{week["slug"]}',
            week["title"],
            week["description"],
            content,
            week["slug"],
            "../../",
        )
    catalog = '<h1>Все материалы</h1><materials-catalog root="../"><catalog-controls></catalog-controls><ul class="catalog-list">'
    catalog += (
        "".join(
            render_material(m, "../", show_description=True)
            for m in materials.values()
        )
        + "</ul></materials-catalog>"
    )
    if not materials:
        catalog += "<p>Пока нет опубликованных материалов.</p>"
    page(
        "materials",
        "Все материалы",
        "Лекции, практики и задания для подготовки к BelOAI.",
        catalog,
        "catalog",
        "../",
    )
    page(
        "license",
        "Лицензия",
        "Условия использования материалов и кода BelOAI.",
        '<h1>Лицензия</h1>'
        '<p>Авторы BelOAI. '
        '<a href="https://github.com/BelOAI/materials/blob/main/CONTRIBUTORS.md">'
        'Участники проекта</a>.</p>'
        '<h2>Учебные материалы</h2>'
        '<p>Лекции, практики, задания, учебник, учебные PDF, тексты каталога и данные материалов '
        'распространяются по '
        '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. '
        '<a href="../LICENSE-CC-BY-4.0">Полный текст лицензии</a>.</p>'
        '<p>При повторном использовании укажите авторов и роли из подписи конкретного материала, источник и лицензию. '
        'Если материал изменён, опишите изменения. Не создавайте впечатление, '
        'что авторы одобряют вашу версию.</p>'
        '<p>Пример атрибуции: «Материалы BelOAI. © Авторы BelOAI. '
        'Источник: <a href="https://beloai.github.io/materials/">сайт BelOAI</a>. '
        'Лицензия: CC BY 4.0».</p>'
        '<h2>Программный код</h2>'
        '<p>Собственный код сайта, скрипты сборки и общие стили LaTeX '
        'распространяются по <a href="../LICENSE-MIT">MIT</a>. '
        'При распространении сохраняйте уведомление об авторских правах '
        'и полный текст лицензии.</p>'
        '<h2>Сторонние компоненты</h2><ul>'
        '<li>Шрифты — SIL Open Font License: '
        '<a href="../fonts/OFL-PTSans.txt">PT Sans</a>, '
        '<a href="../fonts/OFL-IBMPlexSans.txt">IBM Plex Sans</a>, '
        '<a href="../fonts/OFL-Unbounded.txt">Unbounded</a>.</li>'
        '<li>Lit — <a href="../assets/LICENSE-Lit.txt">BSD-3-Clause</a>.</li>'
        '<li>Иконки Font Awesome Free 6.7.2 — CC BY 4.0. '
        '<a href="../assets/fontawesome/LICENSE.txt">Официальные условия лицензирования</a>; '
        '<a href="https://github.com/FortAwesome/Font-Awesome/tree/6.7.2">источник</a>. '
        'Товарные знаки принадлежат соответствующим владельцам.</li>'
        '<li>Значок Python — логотип Python Software Foundation. '
        '<a href="https://www.python.org/community/logos/">Условия использования</a>.</li>'
        '</ul><p><a href="../LICENSE.txt">Лицензии, атрибуция и происхождение материалов</a>.</p>',
        "license",
        "../",
    )
