#!/usr/bin/env python3
"""Generate GitHub Pages index from session meta.yaml files and built artifacts."""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_parser import get_flat, get_materials, get_references, parse_meta

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_ROOTS = (REPO_ROOT / "lectures", REPO_ROOT / "practices")
SITE_DIR = REPO_ROOT / "_site"
FONTS_SRC = REPO_ROOT / "site" / "fonts"
FONTS_DEST = SITE_DIR / "fonts"

SITE = {
    "lang": "ru",
    "title": "BelOAI",
    "subtitle": "Подготовка к олимпиаде по искусственному интеллекту",
    "page_title": "BelOAI — материалы к занятиям",
    "tagline": "Лекции и практики в одном списке — слайды, ноутбуки и ссылки на задания.",
    "download_pdf": "Скачать PDF",
    "open_notebook": "Открыть ноутбук",
    "download_material": "Скачать",
    "references_label": "Ссылки",
    "scheduled": "Проведение",
    "session_label_lecture": "Лекция",
    "session_label_practice": "Практика",
    "empty": "Пока нет опубликованных материалов.",
    "count_one": "{} занятие",
    "count_few": "{} занятия",
    "count_many": "{} занятий",
    "lecture_one": "{} лекция",
    "lecture_few": "{} лекции",
    "lecture_many": "{} лекций",
    "practice_one": "{} практика",
    "practice_few": "{} практики",
    "practice_many": "{} практик",
    "license": "Материалы — CC BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "repo": "Исходники на GitHub",
    "repo_url": "https://github.com/BelOAI/materials",
}

DEFAULT_TIME_SLOTS = {
    "1": "11:25–12:50",
    "2": "13:15–14:40",
}
DEFAULT_SLOT = "1"

MONTHS_RU = (
    "",
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


def folder_kind(root_name: str) -> str:
    if root_name == "lectures":
        return "lecture"
    if root_name == "practices":
        return "practice"
    raise ValueError(f"unknown session root: {root_name}")


def session_number(folder_name: str) -> str:
    match = re.match(r"^(\d+)", folder_name)
    return match.group(1).lstrip("0") or match.group(1) if match else ""


def format_date_ru(iso_date: str) -> str:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso_date.strip())
    if not match:
        return iso_date
    year, month, day = match.groups()
    month_idx = int(month)
    if not 1 <= month_idx <= 12:
        return iso_date
    return f"{int(day)} {MONTHS_RU[month_idx]} {year}"


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
    return int(slot) if slot.isdigit() else 1


def parse_iso_date(iso_date: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", iso_date.strip())
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def format_scheduled_ru(iso_date: str, time: str = "") -> str:
    date_part = format_date_ru(iso_date)
    if not date_part:
        return ""
    time_part = time.strip()
    if time_part:
        return f"{date_part}, {time_part}"
    return date_part


def plural_ru(count: int, one: str, few: str, many: str) -> str:
    n = abs(count) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        return many.format(count)
    if n1 == 1:
        return one.format(count)
    if 2 <= n1 <= 4:
        return few.format(count)
    return many.format(count)


def plural_sessions(count: int) -> str:
    return plural_ru(
        count,
        SITE["count_one"],
        SITE["count_few"],
        SITE["count_many"],
    )


def session_label(kind: str) -> str:
    if kind == "practice":
        return SITE["session_label_practice"]
    return SITE["session_label_lecture"]


def session_sort_key(entry: dict) -> tuple:
    date_tuple = parse_iso_date(entry["date"])
    kind_order = 0 if entry["kind"] == "lecture" else 1
    return (date_tuple, entry["slot_index"], kind_order, entry["slug"])


def discover_built_materials(slug: str, declared: list[dict[str, str]]) -> list[dict[str, str]]:
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
            download_url = f"materials/{slug}/{base}"

        if suffix == ".ipynb":
            html_name = f"{stem}.html"
            if (out_dir / html_name).exists():
                open_url = f"materials/{slug}/{html_name}"

        if download_url or open_url:
            built.append(
                {
                    "label": item["label"],
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

            slug = f"{root.name}/{folder_name}"
            pdf_rel = f"pdfs/{slug}.pdf"
            pdf_exists = (SITE_DIR / pdf_rel).exists()
            references = get_references(meta)
            declared_materials = get_materials(meta)
            built_materials = discover_built_materials(slug, declared_materials)

            if not pdf_exists and not built_materials and not references:
                continue

            thumb = SITE_DIR / "thumbs" / f"{slug}.png"
            thumb_href = ""
            if pdf_exists:
                thumb_href = pdf_rel
            elif built_materials:
                for material in built_materials:
                    if material["open"]:
                        thumb_href = material["open"]
                        break
                    if material["download"]:
                        thumb_href = material["download"]
                        break

            entries.append(
                {
                    "slug": slug,
                    "kind": kind,
                    "number": session_number(folder_name),
                    "title": get_flat(meta, "title", folder_name),
                    "subtitle": get_flat(meta, "subtitle", ""),
                    "date": get_flat(meta, "date", ""),
                    "time": resolve_time(meta),
                    "slot_index": resolve_slot_index(meta),
                    "scheduled_display": format_scheduled_ru(
                        get_flat(meta, "date", ""), resolve_time(meta)
                    ),
                    "description": get_flat(meta, "description", ""),
                    "pdf": pdf_rel if pdf_exists else "",
                    "thumb": f"thumbs/{slug}.png" if thumb.exists() else "",
                    "thumb_href": thumb_href,
                    "materials": built_materials,
                    "references": references,
                }
            )

    entries.sort(key=session_sort_key, reverse=True)
    return entries


def render_action_link(href: str, label: str, css_class: str = "session-action") -> str:
    return (
        f'<a class="{css_class}" href="{html.escape(href)}">'
        f"{html.escape(label)}</a>"
    )


def render_material_actions(materials: list[dict]) -> str:
    parts: list[str] = []
    for material in materials:
        if material["is_notebook"] and material["open"]:
            parts.append(
                render_action_link(
                    material["open"],
                    SITE["open_notebook"],
                    "session-action session-action-primary",
                )
            )
            if material["download"]:
                parts.append(
                    render_action_link(
                        material["download"],
                        f"{SITE['download_material']} .ipynb",
                    )
                )
        elif material["download"]:
            parts.append(
                render_action_link(
                    material["download"],
                    f"{SITE['download_material']} {material['label']}",
                )
            )
    return "\n          ".join(parts)


def render_reference_chips(references: list[dict]) -> str:
    if not references:
        return ""

    chips: list[str] = []
    for ref in references:
        css = "session-ref"
        if ref["kind"] == "contest":
            css += " ref-contest"
        chips.append(
            f'<a class="{css}" href="{html.escape(ref["url"])}" '
            f'target="_blank" rel="noopener noreferrer">'
            f'{html.escape(ref["label"])}</a>'
        )

    inner = "\n        ".join(chips)
    return f"""
        <div class="session-refs">
          <span class="session-refs-label">{html.escape(SITE["references_label"])}</span>
          {inner}
        </div>"""


def render_session_row(entry: dict, index: int) -> str:
    title = html.escape(entry["title"])
    subtitle = html.escape(entry["subtitle"])
    scheduled_display = html.escape(entry["scheduled_display"])
    description = html.escape(entry["description"])
    session_no = html.escape(entry["number"])
    kind = entry["kind"]
    kind_class = f"session-{kind}"
    label = session_label(kind)

    thumb_html = ""
    if entry["thumb"]:
        thumb = html.escape(entry["thumb"])
        thumb_alt = html.escape(f"{label} {entry['number']}: {entry['title']}")
        if entry["thumb_href"]:
            thumb_href = html.escape(entry["thumb_href"])
            thumb_inner = (
                f'<a class="session-thumb-link" href="{thumb_href}">'
                f'<img class="session-thumb" src="{thumb}" alt="{thumb_alt}">'
                f"</a>"
            )
        else:
            thumb_inner = f'<img class="session-thumb" src="{thumb}" alt="{thumb_alt}">'
        thumb_html = f'<div class="session-thumb-wrap">{thumb_inner}</div>'

    index_html = ""
    if session_no:
        index_html = f'<p class="session-index">{html.escape(label)} {session_no}</p>'

    subtitle_html = f'<p class="session-subtitle">{subtitle}</p>' if subtitle else ""
    desc_html = f'<p class="session-desc">{description}</p>' if description else ""
    scheduled_html = (
        f'<p class="session-meta"><span class="session-meta-label">{SITE["scheduled"]}</span> '
        f'<time datetime="{html.escape(entry["date"])}">{scheduled_display}</time></p>'
        if scheduled_display
        else ""
    )

    actions: list[str] = []
    if entry["pdf"]:
        actions.append(
            render_action_link(
                entry["pdf"],
                SITE["download_pdf"],
                "session-action session-action-primary",
            )
        )
    actions.append(render_material_actions(entry["materials"]))
    actions_html = "\n          ".join(part for part in actions if part)
    refs_html = render_reference_chips(entry["references"])

    return f"""
    <article class="session {kind_class}" style="--i: {index}">
      <div class="session-card">
        {thumb_html}
        <div class="session-body">
          {index_html}
          <h2 class="session-title">{title}</h2>
          {subtitle_html}
          {desc_html}
          {scheduled_html}
          <div class="session-actions">
            {actions_html}
          </div>
          {refs_html}
        </div>
      </div>
    </article>"""


def render_hero_count(entries: list[dict]) -> str:
    if not entries:
        return ""

    lecture_count = sum(1 for entry in entries if entry["kind"] == "lecture")
    practice_count = sum(1 for entry in entries if entry["kind"] == "practice")

    parts = [html.escape(plural_sessions(len(entries)))]
    breakdown: list[str] = []
    if lecture_count:
        breakdown.append(
            html.escape(
                plural_ru(
                    lecture_count,
                    SITE["lecture_one"],
                    SITE["lecture_few"],
                    SITE["lecture_many"],
                )
            )
        )
    if practice_count:
        breakdown.append(
            html.escape(
                plural_ru(
                    practice_count,
                    SITE["practice_one"],
                    SITE["practice_few"],
                    SITE["practice_many"],
                )
            )
        )
    if breakdown:
        parts.append(f'<span class="hero-count-breakdown">{" · ".join(breakdown)}</span>')

    return f'<p class="hero-count">{" ".join(parts)}</p>'


def copy_fonts() -> None:
    if not FONTS_SRC.is_dir():
        raise SystemExit(
            f"Missing fonts directory: {FONTS_SRC}\n"
            "Run: bash scripts/vendor-fonts.sh"
        )
    shutil.copytree(FONTS_SRC, FONTS_DEST, dirs_exist_ok=True)


def render_font_faces() -> str:
    return """@font-face {
      font-family: "Unbounded";
      src: url("fonts/unbounded-latin-cyrillic.woff2") format("woff2");
      font-weight: 200 900;
      font-style: normal;
      font-display: swap;
    }
    @font-face {
      font-family: "IBM Plex Sans";
      src: url("fonts/ibm-plex-sans-latin-cyrillic.woff2") format("woff2");
      font-weight: 100 700;
      font-style: normal;
      font-display: swap;
    }"""


def render_index(entries: list[dict]) -> str:
    rows = "\n".join(render_session_row(e, i) for i, e in enumerate(entries))
    if not rows.strip():
        rows = f'<p class="empty">{SITE["empty"]}</p>'

    count_html = render_hero_count(entries)

    page_title = html.escape(SITE["page_title"])
    meta_description = html.escape(SITE["tagline"])

    return f"""<!DOCTYPE html>
<html lang="{SITE["lang"]}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{meta_description}">
  <meta name="theme-color" content="#172a4a">
  <title>{page_title}</title>
  <style>
    {render_font_faces()}
    :root {{
      --ac-dark: #172a4a;
      --ac-mid: #3e547a;
      --ac-gray: #6c737c;
      --ac-light: #eff1f4;
      --ac-rule: #c6cbd2;
      --content-width: 1100px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
      background: var(--ac-light);
      color: #222;
      line-height: 1.55;
    }}
    @keyframes fade-up {{
      from {{
        opacity: 0;
        transform: translateY(12px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}
    .site-hero {{
      background: var(--ac-dark);
      color: #fff;
      padding: clamp(2.5rem, 8vw, 5rem) 1.5rem;
    }}
    .hero-inner {{
      max-width: var(--content-width);
      margin: 0 auto;
      animation: fade-up 0.55s ease both;
    }}
    .hero-brand {{
      margin: 0;
      font-family: "Unbounded", "IBM Plex Sans", system-ui, sans-serif;
      font-size: clamp(1.75rem, 4.5vw, 3rem);
      font-weight: 700;
      line-height: 1.15;
      letter-spacing: -0.02em;
    }}
    .hero-subtitle {{
      margin: 0.65rem 0 0;
      font-size: 1.1rem;
      font-weight: 500;
      color: rgba(255, 255, 255, 0.82);
    }}
    .hero-tagline {{
      margin: 1rem 0 0;
      max-width: 36rem;
      font-size: 1rem;
      color: rgba(255, 255, 255, 0.65);
    }}
    .hero-count {{
      margin: 1.25rem 0 0;
      font-size: 0.9rem;
      font-weight: 600;
      color: rgba(255, 255, 255, 0.5);
      letter-spacing: 0.02em;
    }}
    .hero-count-breakdown {{
      font-weight: 500;
      color: rgba(255, 255, 255, 0.38);
    }}
    main {{
      max-width: var(--content-width);
      margin: 0 auto;
      padding: 0 1.5rem 3.5rem;
    }}
    .session-list {{
      margin-top: 2rem;
    }}
    .session {{
      border-bottom: 1px solid var(--ac-rule);
      animation: fade-up 0.5s ease both;
      animation-delay: calc(0.08s * var(--i) + 0.15s);
    }}
    .session-lecture {{
      --session-dark: #172a4a;
      --session-mid: #3e547a;
    }}
    .session-practice {{
      --session-dark: #1a4a3d;
      --session-mid: #2d7a62;
    }}
    .session-card {{
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 1.5rem;
      align-items: start;
      padding: 1.5rem 0 1.5rem 1rem;
      border-left: 3px solid var(--session-mid);
    }}
    .session-thumb-wrap {{
      overflow: hidden;
      border-radius: 2px;
      background: #fff;
    }}
    .session-thumb-link {{
      display: block;
      color: inherit;
      text-decoration: none;
    }}
    .session-thumb {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      transition: transform 0.25s ease;
    }}
    .session-thumb-link:hover .session-thumb {{
      transform: scale(1.03);
    }}
    .session-body {{
      min-width: 0;
      padding-top: 0.1rem;
    }}
    .session-index {{
      margin: 0;
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--session-mid);
    }}
    .session-title {{
      margin: 0.35rem 0 0;
      font-family: "Unbounded", "IBM Plex Sans", system-ui, sans-serif;
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--session-dark);
      line-height: 1.25;
    }}
    .session-subtitle {{
      margin: 0.4rem 0 0;
      font-size: 0.95rem;
      color: var(--session-mid);
    }}
    .session-desc {{
      margin: 0.55rem 0 0;
      font-size: 0.92rem;
      color: #3a3a3a;
      max-width: 52rem;
    }}
    .session-meta {{
      margin: 0.65rem 0 0;
      font-size: 0.85rem;
      color: var(--ac-gray);
      font-variant-numeric: tabular-nums;
    }}
    .session-meta-label {{
      color: var(--session-mid);
      font-weight: 600;
      margin-right: 0.35rem;
    }}
    .session-meta time {{
      color: var(--ac-gray);
    }}
    .session-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem 0.75rem;
      margin-top: 0.85rem;
    }}
    .session-action {{
      display: inline-flex;
      align-items: center;
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--session-mid);
      text-decoration: none;
      padding: 0.2rem 0;
      border-bottom: 1px solid transparent;
      transition: color 0.15s ease, border-color 0.15s ease;
    }}
    .session-action:hover {{
      color: var(--session-dark);
      border-bottom-color: var(--session-mid);
    }}
    .session-action:focus-visible {{
      outline: 2px solid var(--session-mid);
      outline-offset: 3px;
      border-radius: 2px;
    }}
    .session-action-primary {{
      color: var(--session-dark);
    }}
    .session-refs {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 0.4rem 0.55rem;
      margin-top: 0.75rem;
    }}
    .session-refs-label {{
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      color: var(--ac-gray);
      margin-right: 0.15rem;
    }}
    .session-ref {{
      display: inline-flex;
      align-items: center;
      font-size: 0.82rem;
      font-weight: 500;
      color: var(--session-mid);
      text-decoration: none;
      padding: 0.15rem 0.55rem;
      border: 1px solid var(--ac-rule);
      border-radius: 2px;
      background: rgba(255, 255, 255, 0.7);
      transition: background 0.15s ease, border-color 0.15s ease;
    }}
    .session-ref:hover {{
      background: #fff;
      border-color: var(--session-mid);
      color: var(--session-dark);
    }}
    .session-ref:focus-visible {{
      outline: 2px solid var(--session-mid);
      outline-offset: 2px;
    }}
    .ref-contest {{
      font-weight: 700;
      color: var(--session-dark);
      border-color: var(--session-mid);
      background: #fff;
    }}
    .empty {{
      margin: 3rem 0;
      text-align: center;
      color: var(--ac-gray);
    }}
    .site-footer {{
      max-width: var(--content-width);
      margin: 0 auto;
      padding: 0 1.5rem 2.5rem;
      font-size: 0.85rem;
      color: var(--ac-gray);
    }}
    .site-footer p {{
      margin: 0;
      padding-top: 1.25rem;
      border-top: 1px solid var(--ac-rule);
    }}
    .site-footer a {{
      color: var(--ac-mid);
      text-decoration: none;
    }}
    .site-footer a:hover {{
      text-decoration: underline;
    }}
    @media (max-width: 640px) {{
      .session-card {{
        grid-template-columns: 1fr;
        gap: 1rem;
      }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .hero-inner,
      .session {{
        animation: none;
      }}
      .session-thumb {{
        transition: none;
      }}
      .session-thumb-link:hover .session-thumb {{
        transform: none;
      }}
    }}
  </style>
</head>
<body>
  <header class="site-hero">
    <div class="hero-inner">
      <h1 class="hero-brand">{html.escape(SITE["title"])}</h1>
      <p class="hero-subtitle">{html.escape(SITE["subtitle"])}</p>
      <p class="hero-tagline">{html.escape(SITE["tagline"])}</p>
      {count_html}
    </div>
  </header>
  <main>
    <div class="session-list">
      {rows}
    </div>
  </main>
  <footer class="site-footer">
    <p>
      <a href="{html.escape(SITE["license_url"])}">{html.escape(SITE["license"])}</a>
      ·
      <a href="{html.escape(SITE["repo_url"])}">{html.escape(SITE["repo"])}</a>
    </p>
  </footer>
</body>
</html>
"""


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    copy_fonts()
    entries = discover_sessions()
    index_path = SITE_DIR / "index.html"
    index_path.write_text(render_index(entries), encoding="utf-8")
    print(f"Wrote {index_path} ({len(entries)} session(s))")


if __name__ == "__main__":
    main()
