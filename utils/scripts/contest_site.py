"""Публикация и проверка иерархических разборов контестов."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from course_site import link, publish_katex, write_page

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"Не удалось прочитать {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: ожидается объект YAML")
    return value


def _source_file(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Небезопасный путь в каталоге контестов: {relative}")
    resolved = (root / "contests" / path).resolve()
    if not resolved.is_relative_to((root / "contests").resolve()) or not resolved.is_file():
        raise ValueError(f"Не найден исходник контеста: {relative}")
    return resolved


def load_contests(source: Path) -> dict:
    """Читает каталог, год, этапы, задачи и проверяет их исходники."""
    folder = source / "contests"
    registry = folder / "contests.yml"
    if not registry.is_file():
        return {"years": [], "_stages": {}, "_tasks": {}}
    data = _read_yaml(registry)
    years = data.get("years")
    if not isinstance(years, list):
        raise ValueError(f"В {registry} ожидается список years")
    seen_years: set[str] = set()
    catalog = {"years": [], "_stages": {}, "_tasks": {}}
    for entry in years:
        if not isinstance(entry, dict):
            raise ValueError(f"Некорректная запись года в {registry}")
        slug = entry.get("slug")
        if not isinstance(slug, str) or not re.fullmatch(r"20[0-9]{2}", slug) or slug in seen_years:
            raise ValueError(f"Некорректный или повторный год: {slug}")
        year_meta = _read_yaml(_source_file(source, f"{slug}/meta.yml"))
        if (year_meta.get("slug") != slug or not isinstance(year_meta.get("title"), str)
                or not isinstance(year_meta.get("description"), str)
                or not isinstance(year_meta.get("stages"), list)):
            raise ValueError(f"{slug}/meta.yml: нужны slug, title, description и stages")
        stage_ids = list(year_meta["stages"])
        year_meta.update(id=slug, _folder=folder / slug,
                         _content=_source_file(source, f"{slug}/content.md"), stages=[])
        seen_years.add(slug)
        stage_slugs: set[str] = set()
        for stage_slug in stage_ids:
            if not isinstance(stage_slug, str) or not SLUG.fullmatch(stage_slug) or stage_slug in stage_slugs:
                raise ValueError(f"{slug}: некорректный или повторный этап: {stage_slug}")
            stage_slugs.add(stage_slug)
            stage_id = f"{slug}/{stage_slug}"
            stage_meta = _read_yaml(_source_file(source, f"{stage_id}/meta.yml"))
            if (stage_meta.get("slug") != stage_slug
                    or not all(isinstance(stage_meta.get(key), str) and stage_meta[key].strip()
                               for key in ("title", "description", "date"))
                    or not isinstance(stage_meta.get("tasks"), list) or not stage_meta["tasks"]):
                raise ValueError(f"{stage_id}/meta.yml: неполные метаданные этапа")
            task_ids = list(stage_meta["tasks"])
            stage_meta.update(id=stage_id, year=year_meta,
                              _folder=folder / stage_id,
                              _content=_source_file(source, f"{stage_id}/content.md"), tasks=[])
            task_slugs: set[str] = set()
            for task_slug in task_ids:
                if not isinstance(task_slug, str) or not SLUG.fullmatch(task_slug) or task_slug in task_slugs:
                    raise ValueError(f"{stage_id}: некорректная или повторная задача: {task_slug}")
                task_slugs.add(task_slug)
                task_id = f"{stage_id}/{task_slug}"
                task_folder = folder / stage_id / task_slug
                task_meta = _read_yaml(_source_file(source, f"{stage_id}/{task_slug}/meta.yml"))
                if (task_meta.get("slug") != task_slug
                        or not all(isinstance(task_meta.get(key), str) and task_meta[key].strip()
                                   for key in ("title", "description", "kind"))
                        or task_meta.get("kind") not in {"math", "programming"}
                        or not isinstance(task_meta.get("web_limits", ""), str)):
                    raise ValueError(f"{task_id}/meta.yml: неполные метаданные задачи")
                if task_meta.get("original") and not urlsplit(task_meta["original"]).scheme in {"https", "http"}:
                    raise ValueError(f"{task_id}: ссылка original должна использовать HTTP(S)")
                task_meta.update(id=task_id, stage=stage_meta, _folder=task_folder,
                                 _statement=_source_file(source, f"{stage_id}/{task_slug}/statement.md"),
                                 _analysis=_source_file(source, f"{stage_id}/{task_slug}/analysis.md"))
                stage_meta["tasks"].append(task_meta)
                catalog["_tasks"][task_id] = task_meta
            year_meta["stages"].append(stage_meta)
            catalog["_stages"][stage_id] = stage_meta
        catalog["years"].append(year_meta)
    return catalog


def render_markdown(source: Path, items: list[dict]) -> dict[str, str]:
    if not items:
        return {}
    payload = [{"name": item["slug"], "source": item["_source"] if "_source" in item
                else item["_content"].read_text(encoding="utf-8")} for item in items]
    rendered = subprocess.run(
        ["node", str(source / "utils/site/render-handbook.mjs")],
        input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True, check=True,
    )
    return {item["slug"]: html["html"] for item, html in zip(items, json.loads(rendered.stdout), strict=True)}


def validate_links(output: Path, *, require_pdfs: bool = False) -> None:
    """Проверяет локальные ссылки и якоря на всех страницах контестов."""
    from handbook_site import PageLinks

    pages = {page.resolve(): PageLinks(page.read_text(encoding="utf-8"))
             for page in (output / "contests").rglob("index.html")}
    for page, parsed in pages.items():
        for href in parsed.urls:
            url = urlsplit(href)
            if url.scheme in ("http", "https", "mailto", "data") or url.netloc:
                continue
            if url.scheme or url.path.startswith("/"):
                raise ValueError(f"Ссылка не поддерживает префикс сайта: {href}")
            target = (page.parent / unquote(url.path)).resolve() if url.path else page
            if target.is_dir():
                target /= "index.html"
            if not target.is_relative_to(output.resolve()):
                raise ValueError(f"{page.relative_to(output.resolve())}: ссылка выходит за сайт: {href}")
            if not target.is_file():
                if target.suffix.lower() == ".pdf" and not require_pdfs:
                    continue
                raise ValueError(f"{page.relative_to(output.resolve())}: недоступная ссылка {href}")
            if url.fragment and target.suffix == ".html":
                anchors = pages.get(target) or PageLinks(target.read_text(encoding="utf-8"))
                if unquote(url.fragment) not in anchors.ids:
                    raise ValueError(f"Отсутствует якорь: {href}")


def publish_contests(source: Path, output: Path, weeks: list, *, validate: bool = True) -> None:
    if not (source / "contests/contests.yml").is_file():
        return
    catalog = load_contests(source)
    publish_katex(source, output)
    sources = [{"slug": "catalog", "_content": source / "contests/README.md"}]
    for year in catalog["years"]:
        sources.append({"slug": year["id"], "_content": year["_content"]})
        for stage in year["stages"]:
            sources.append({"slug": stage["id"], "_content": stage["_content"]})
            for task in stage["tasks"]:
                statement = task["_statement"].read_text(encoding="utf-8")
                if limits := task.get("web_limits"):
                    statement = limits + "\n\n" + statement
                sources.extend([
                    {"slug": task["id"] + "-statement", "_source": statement},
                    {"slug": task["id"] + "-analysis", "_content": task["_analysis"]},
                ])
    rendered = render_markdown(source, sources)
    shutil.rmtree(output / "contests", ignore_errors=True)
    for year in catalog["years"]:
        for stage in year["stages"]:
            for task in stage["tasks"]:
                media = task["_folder"] / "media"
                if media.is_dir():
                    destination = output / "contests" / stage["id"] / task["slug"] / "media"
                    shutil.copytree(media, destination, dirs_exist_ok=True)

    def page(identifier: str, title: str, description: str, body: str, trail=()) -> None:
        path = "contests" + ("/" + identifier if identifier else "")
        root = "../" * len(Path(path).parts)

        def navlink(target, label):
            href = root + "contests/" + (target + "/" if target else "")
            current = ' aria-current="page"' if target == identifier else ""
            return link(href, label, current)

        year = next((item for item in catalog["years"]
                     if identifier.split("/")[0] == item["id"]), None)
        navigation = '<div class="handbook-tree">'
        if year is None:
            navigation += '<ul>' + "".join(
                '<li>' + navlink(item["id"], item["title"]) + '</li>' for item in catalog["years"]
            ) + '</ul>'
        else:
            navigation += '<ul><li>' + navlink(year["id"], year["title"]) + '</li></ul><hr><ul>'
            for stage in year["stages"]:
                navigation += '<li>' + navlink(stage["id"], stage["title"])
                if identifier == stage["id"] or identifier.startswith(stage["id"] + "/"):
                    navigation += '<ul class="handbook-lessons">' + "".join(
                        '<li>' + navlink(task["id"], task["title"]) + '</li>' for task in stage["tasks"]
                    ) + '</ul>'
                navigation += '</li>'
            navigation += '</ul>'
        navigation += ('</div><hr><ul><li>' + link(root, "Занятия курса") + '</li><li>'
                       + link(root + "materials/", "Все материалы") + '</li><li>'
                       + link(root + "handbooks/", "Учебники") + '</li></ul>')
        top = '<div class="handbook-links"><ul><li>' + navlink("", "Все контесты") + '</li></ul></div>'
        if identifier:
            crumbs = '<nav class="breadcrumbs" aria-label="Путь к странице"><ol>' + "".join(
                '<li>' + navlink(target, label) + '</li>'
                for target, label in (("", "Все контесты"), *trail)
            )
            body = crumbs + '<li aria-current="page">' + escape(title) + '</li></ol></nav>' + body
        write_page(source, output, weeks, path, title, description,
                   '<div class="handbook-content">' + body + '</div>',
                   "contest" if identifier else "contests", root,
                   navigation_override=navigation, navigation_top=top,
                   navigation_label="Оглавление контестов", math=True)

    def contents(items, label):
        return (
            f'<nav class="lesson-toc" aria-label="{escape(label, quote=True)}"><h2>{escape(label)}</h2>'
            '<ul class="contest-list">' + "".join(
                '<li>' + link(item["slug"] + "/", item["title"]) + '</li>' for item in items
            ) + '</ul></nav>'
        )

    page("", "Разборы контестов", "Каталог разборов контестов BelOAI.",
         rendered["catalog"] + contents(catalog["years"], "Годы"))

    for year in catalog["years"]:
        year_crumb = ((year["id"], year["title"]),)
        page(year["id"], year["title"], year["description"],
             rendered[year["id"]] + contents(year["stages"], "Этапы"), trail=())
        for stage in year["stages"]:
            stage_crumb = (*year_crumb, (stage["id"], stage["title"]))
            downloads = ('<nav class="contest-download" aria-label="PDF этапа">'
                         '<a href="statements.pdf">Условия задач (PDF)</a>'
                         '<a href="debrief.pdf">Разбор задач (PDF)</a></nav>')
            page(stage["id"], stage["title"], stage["description"],
                 rendered[stage["id"]] + downloads + contents(stage["tasks"], "Задачи"), year_crumb)
            for index, task in enumerate(stage["tasks"]):
                body = f'<h1>{escape(task["title"])}</h1>'
                body += ('<nav class="contest-download" aria-label="На странице">'
                         '<a href="#statement">Условие</a><a href="#analysis">Разбор</a>'
                         + (link(task["original"], "Оригинальное условие") if task.get("original") else '')
                         + '</nav>')
                body += '<section><h2 id="statement">Условие</h2>'
                body += rendered[task["id"] + "-statement"] + '</section>'
                body += '<section><h2 id="analysis">Разбор</h2>'
                body += rendered[task["id"] + "-analysis"] + '</section>'
                neighbors = []
                if index:
                    previous = stage["tasks"][index - 1]
                    neighbors.append(link("../" + previous["slug"] + "/", "← " + previous["title"], ' rel="prev"'))
                if index + 1 < len(stage["tasks"]):
                    following = stage["tasks"][index + 1]
                    neighbors.append(link("../" + following["slug"] + "/", following["title"] + " →", ' rel="next"'))
                if neighbors:
                    body += '<nav class="week-pagination" aria-label="Соседние задачи">' + "".join(neighbors) + '</nav>'
                page(task["id"], task["title"], task["description"], body, stage_crumb)
    if validate:
        validate_links(output)
