#!/usr/bin/env python3
"""Публикация манифеста материалов и оболочки сайта GitHub Pages."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_parser import (
    get_assignment_type,
    get_flat,
    get_materials,
    get_references,
    parse_meta,
)
from course_site import load_course, publish_pages
from handbook_site import publish_handbook

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_ROOTS = (
    REPO_ROOT / "lectures",
    REPO_ROOT / "practices",
    REPO_ROOT / "assignments",
)
SITE_DIR = REPO_ROOT / "_site"
FONTS_SRC = REPO_ROOT / "site" / "fonts"
FONTS_DEST = SITE_DIR / "fonts"

DEFAULT_TIME_SLOTS = {
    "1": "11:25–12:50",
    "2": "13:15–14:40",
}
DEFAULT_SLOT = "1"

KIND_ORDER = {
    "assignment": 0,
    "lecture": 1,
    "practice": 2,
}


def folder_kind(root_name: str) -> str:
    if root_name == "lectures":
        return "lecture"
    if root_name == "practices":
        return "practice"
    if root_name == "assignments":
        return "assignment"
    raise ValueError(f"unknown session root: {root_name}")


def session_number(folder_name: str) -> str:
    match = re.match(r"^(\d+)", folder_name)
    return match.group(1).lstrip("0") or match.group(1) if match else ""


def resolve_time(meta: dict) -> str:
    explicit = get_flat(meta, "time", "").strip()
    if explicit:
        return explicit
    slot = get_flat(meta, "slot", DEFAULT_SLOT).strip() or DEFAULT_SLOT
    return DEFAULT_TIME_SLOTS.get(slot, DEFAULT_TIME_SLOTS[DEFAULT_SLOT])


def resolve_slot_index(meta: dict) -> int:
    explicit = get_flat(meta, "time", "").strip()
    if explicit:
        match = re.match(r"^(\d{1,2}):(\d{2})", explicit)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))
        return 0
    slot = get_flat(meta, "slot", DEFAULT_SLOT).strip() or DEFAULT_SLOT
    start = DEFAULT_TIME_SLOTS.get(slot, DEFAULT_TIME_SLOTS[DEFAULT_SLOT])
    hour, minute = start.split("–")[0].split(":")
    return int(hour) * 60 + int(minute)


def parse_iso_date(iso_date: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso_date.strip())
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def session_sort_key(entry: dict) -> tuple:
    date_tuple = parse_iso_date(entry["date"])
    kind_order = KIND_ORDER.get(entry["kind"], 9)
    return (
        date_tuple,
        entry["kind"] == "assignment",
        entry["slot_index"],
        -kind_order,
        entry["slug"],
    )


def discover_built_materials(
    slug: str, declared: list[dict[str, str]]
) -> list[dict[str, str]]:
    built: list[dict[str, str]] = []
    out_dir = SITE_DIR / "materials" / slug
    if not out_dir.is_dir():
        return built

    for item in declared:
        rel_path = item["path"]
        base = Path(rel_path).name
        stem = Path(base).stem
        suffix = Path(base).suffix.lower()

        download_url = ""
        open_url = ""
        if (out_dir / base).exists():
            download_url = quote(f"materials/{slug}/{base}")

        if suffix == ".ipynb":
            html_name = f"{stem}.html"
            if (out_dir / html_name).exists():
                open_url = quote(f"materials/{slug}/{html_name}")

        if download_url or open_url:
            built.append(
                {
                    "label": (
                        f"{item['label']} — {base}"
                        if sum(other["label"] == item["label"] for other in declared)
                        > 1
                        else item["label"]
                    ),
                    "download": download_url,
                    "open": open_url,
                    "is_notebook": suffix == ".ipynb",
                }
            )

    return built


def discover_sessions() -> list[dict]:
    entries: list[dict] = []
    for root in SESSION_ROOTS:
        if not root.is_dir():
            continue
        kind = folder_kind(root.name)

        for session_dir in sorted(root.iterdir()):
            if not session_dir.is_dir():
                continue
            folder_name = session_dir.name
            if folder_name.startswith("_"):
                continue
            meta_path = session_dir / "meta.yaml"
            if not meta_path.exists():
                continue

            meta = parse_meta(meta_path)
            if get_flat(meta, "build", "true").lower() == "false":
                continue
            if get_flat(meta, "hidden", "false").lower() == "true":
                continue

            assignment_type = ""
            if kind == "assignment":
                assignment_type = get_assignment_type(meta)
                if not assignment_type:
                    print(
                        f"Пропущено {session_dir}: "
                        "assignment_type должен быть math или coding",
                        file=sys.stderr,
                    )
                    continue

            slug = f"{root.name}/{folder_name}"
            pdf_rel = f"pdfs/{slug}.pdf"
            pdf_exists = (SITE_DIR / pdf_rel).exists()
            references = get_references(meta)
            declared_materials = get_materials(meta)
            built_materials = discover_built_materials(slug, declared_materials)

            if not pdf_exists and not built_materials and not references:
                continue

            thumb = SITE_DIR / "thumbs" / f"{slug}.png"
            thumb_url = (
                quote(f"thumbs/{slug}.png") if pdf_exists and thumb.is_file() else ""
            )
            thumb_href = quote(pdf_rel) if thumb_url else ""
            if not pdf_exists:
                notebook = next(
                    (file for file in built_materials if file["is_notebook"]), None
                )
                if notebook:
                    name = Path(unquote(notebook["download"] or notebook["open"])).name
                    preview_rel = f"thumbs/{slug}/{name}.svg"
                    if (SITE_DIR / preview_rel).is_file():
                        thumb_url = quote(preview_rel)
                        thumb_href = notebook["open"] or notebook["download"]
            if kind == "assignment":
                time = get_flat(meta, "time", "").strip()
                slot_index = resolve_slot_index(meta) if time else 0
            else:
                time = resolve_time(meta)
                slot_index = resolve_slot_index(meta)

            entries.append(
                {
                    "slug": slug,
                    "kind": kind,
                    "assignment_type": assignment_type,
                    "number": session_number(folder_name),
                    "title": get_flat(meta, "title", folder_name),
                    "subtitle": get_flat(meta, "subtitle", ""),
                    "date": get_flat(meta, "date", ""),
                    "time": time,
                    "slot_index": slot_index,
                    "description": get_flat(meta, "description", ""),
                    "pdf": quote(pdf_rel) if pdf_exists else "",
                    "thumb": thumb_url,
                    "thumb_href": thumb_href,
                    "materials": built_materials,
                    "references": references,
                }
            )

    entries.sort(key=session_sort_key, reverse=True)
    return entries


def build_manifest(entries: list[dict], course: dict) -> dict:
    materials = []
    for entry in entries:
        item = {
            key: entry[key]
            for key in (
                "kind",
                "number",
                "title",
                "subtitle",
                "description",
                "date",
                "time",
                "materials",
                "references",
            )
        }
        item["id"] = entry["slug"]
        for key in ("assignment_type", "pdf", "thumb", "thumb_href"):
            if entry[key]:
                item[key] = entry[key]
        materials.append(item)
    return {"version": 2, "course": course, "materials": materials}


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    if not FONTS_SRC.is_dir():
        raise SystemExit("Нет шрифтов: выполните bash scripts/vendor-fonts.sh")
    entries = discover_sessions()
    course = load_course(REPO_ROOT, entries)
    manifest = build_manifest(entries, course)
    shutil.copytree(FONTS_SRC, FONTS_DEST, dirs_exist_ok=True)
    assets = REPO_ROOT / "site/assets"
    if assets.is_dir():
        shutil.copytree(assets, SITE_DIR / "assets", dirs_exist_ok=True)
    for filename in ("LICENSE-CC-BY-4.0", "LICENSE-MIT"):
        shutil.copyfile(REPO_ROOT / filename, SITE_DIR / filename)
    (SITE_DIR / "materials.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    publish_pages(REPO_ROOT, SITE_DIR, manifest)
    shutil.copyfile(REPO_ROOT / "site/favicon.svg", SITE_DIR / "favicon.svg")
    if (REPO_ROOT / "handbook/handbook.json").is_file():
        publish_handbook(REPO_ROOT, SITE_DIR, course["weeks"])
    print(f"Опубликован манифест: {len(entries)} материалов")


if __name__ == "__main__":
    main()
