#!/usr/bin/env python3
"""Generate GitHub Pages index from lecture meta.yaml files and built PDFs."""

from __future__ import annotations

import html
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LECTURES_DIR = REPO_ROOT / "lectures"
SITE_DIR = REPO_ROOT / "_site"

SITE = {
    "lang": "ru",
    "title": "BelOAI",
    "subtitle": "Белорусская олимпиада по искусственному интеллекту",
    "page_title": "BelOAI — презентации к занятиям",
    "tagline": "Слайды в PDF для просмотра и конспекта. Список занятий — на главной странице.",
    "download": "Скачать PDF",
    "scheduled": "Проведение",
    "session_label": "Занятие",
    "empty": "Пока нет опубликованных материалов.",
    "count_one": "{} занятие",
    "count_few": "{} занятия",
    "count_many": "{} занятий",
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


def parse_meta(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_]+):\s*(.+)$", line)
        if not match:
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data


def lecture_sort_key(slug: str) -> tuple:
    match = re.match(r"^(\d+)", slug)
    num = int(match.group(1)) if match else 9999
    return (num, slug)


def lecture_number(slug: str) -> str:
    match = re.match(r"^(\d+)", slug)
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


def resolve_time(meta: dict[str, str]) -> str:
    explicit = meta.get("time", "").strip()
    if explicit:
        return explicit
    slot = meta.get("slot", DEFAULT_SLOT).strip() or DEFAULT_SLOT
    return DEFAULT_TIME_SLOTS.get(slot, DEFAULT_TIME_SLOTS[DEFAULT_SLOT])


def format_scheduled_ru(iso_date: str, time: str = "") -> str:
    date_part = format_date_ru(iso_date)
    if not date_part:
        return ""
    time_part = time.strip()
    if time_part:
        return f"{date_part}, {time_part}"
    return date_part


def plural_sessions(count: int) -> str:
    n = abs(count) % 100
    n1 = n % 10
    if 11 <= n <= 19:
        return SITE["count_many"].format(count)
    if n1 == 1:
        return SITE["count_one"].format(count)
    if 2 <= n1 <= 4:
        return SITE["count_few"].format(count)
    return SITE["count_many"].format(count)


def discover_lectures() -> list[dict]:
    entries: list[dict] = []
    for lecture_dir in sorted(LECTURES_DIR.iterdir()):
        if not lecture_dir.is_dir():
            continue
        slug = lecture_dir.name
        if slug.startswith("_"):
            continue
        meta_path = lecture_dir / "meta.yaml"
        if not meta_path.exists():
            continue
        meta = parse_meta(meta_path)
        if meta.get("build", "true").lower() == "false":
            continue
        if meta.get("hidden", "false").lower() == "true":
            continue
        pdf = SITE_DIR / "pdfs" / f"{slug}.pdf"
        if not pdf.exists():
            continue
        thumb = SITE_DIR / "thumbs" / f"{slug}.png"
        entries.append(
            {
                "slug": slug,
                "number": lecture_number(slug),
                "title": meta.get("title", slug),
                "subtitle": meta.get("subtitle", ""),
                "date": meta.get("date", ""),
                "time": resolve_time(meta),
                "scheduled_display": format_scheduled_ru(
                    meta.get("date", ""), resolve_time(meta)
                ),
                "description": meta.get("description", ""),
                "pdf": f"pdfs/{slug}.pdf",
                "thumb": f"thumbs/{slug}.png" if thumb.exists() else "",
            }
        )
    entries.sort(key=lambda e: lecture_sort_key(e["slug"]))
    return entries


def render_lecture_row(entry: dict, index: int) -> str:
    title = html.escape(entry["title"])
    subtitle = html.escape(entry["subtitle"])
    scheduled_display = html.escape(entry["scheduled_display"])
    description = html.escape(entry["description"])
    pdf = html.escape(entry["pdf"])
    lecture_no = html.escape(entry["number"])
    thumb_alt = html.escape(f"{SITE['session_label']} {entry['number']}: {entry['title']}")
    aria_label = html.escape(
        f"{SITE['session_label']} {entry['number']}: {entry['title']} — скачать PDF"
    )

    thumb_html = ""
    if entry["thumb"]:
        thumb = html.escape(entry["thumb"])
        thumb_html = (
            f'<div class="lecture-thumb-wrap">'
            f'<img class="lecture-thumb" src="{thumb}" alt="{thumb_alt}">'
            f"</div>"
        )

    index_html = ""
    if lecture_no:
        index_html = f'<p class="lecture-index">{SITE["session_label"]} {lecture_no}</p>'

    subtitle_html = f'<p class="lecture-subtitle">{subtitle}</p>' if subtitle else ""
    desc_html = f'<p class="lecture-desc">{description}</p>' if description else ""
    scheduled_html = (
        f'<p class="lecture-meta"><span class="lecture-meta-label">{SITE["scheduled"]}</span> '
        f'<time datetime="{html.escape(entry["date"])}">{scheduled_display}</time></p>'
        if scheduled_display
        else ""
    )

    return f"""
    <article class="lecture" style="--i: {index}">
      <a class="lecture-link" href="{pdf}" aria-label="{aria_label}">
        {thumb_html}
        <div class="lecture-body">
          {index_html}
          <h2 class="lecture-title">{title}</h2>
          {subtitle_html}
          {desc_html}
          {scheduled_html}
          <span class="lecture-action">{SITE["download"]}<span class="lecture-arrow" aria-hidden="true">→</span></span>
        </div>
      </a>
    </article>"""


def render_index(entries: list[dict]) -> str:
    rows = "\n".join(render_lecture_row(e, i) for i, e in enumerate(entries))
    if not rows.strip():
        rows = f'<p class="empty">{SITE["empty"]}</p>'

    count_html = ""
    if entries:
        count_html = f'<p class="hero-count">{html.escape(plural_sessions(len(entries)))}</p>'

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
      font-family: system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
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
    main {{
      max-width: var(--content-width);
      margin: 0 auto;
      padding: 0 1.5rem 3.5rem;
    }}
    .lecture-list {{
      margin-top: 2rem;
    }}
    .lecture {{
      border-bottom: 1px solid var(--ac-rule);
      animation: fade-up 0.5s ease both;
      animation-delay: calc(0.08s * var(--i) + 0.15s);
    }}
    .lecture-link {{
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 1.5rem;
      align-items: start;
      padding: 1.5rem 0;
      color: inherit;
      text-decoration: none;
      transition: background 0.15s ease;
    }}
    .lecture-link:hover {{
      background: rgba(255, 255, 255, 0.45);
    }}
    .lecture-link:focus-visible {{
      outline: 2px solid var(--ac-mid);
      outline-offset: 4px;
      border-radius: 2px;
    }}
    .lecture-thumb-wrap {{
      overflow: hidden;
      border-radius: 2px;
      background: #fff;
    }}
    .lecture-thumb {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      transition: transform 0.25s ease;
    }}
    .lecture-link:hover .lecture-thumb {{
      transform: scale(1.03);
    }}
    .lecture-body {{
      min-width: 0;
      padding-top: 0.1rem;
    }}
    .lecture-index {{
      margin: 0;
      font-size: 0.8rem;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--ac-mid);
    }}
    .lecture-title {{
      margin: 0.35rem 0 0;
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--ac-dark);
      line-height: 1.25;
    }}
    .lecture-subtitle {{
      margin: 0.4rem 0 0;
      font-size: 0.95rem;
      color: var(--ac-mid);
    }}
    .lecture-desc {{
      margin: 0.55rem 0 0;
      font-size: 0.92rem;
      color: #3a3a3a;
      max-width: 52rem;
    }}
    .lecture-meta {{
      margin: 0.65rem 0 0;
      font-size: 0.85rem;
      color: var(--ac-gray);
      font-variant-numeric: tabular-nums;
    }}
    .lecture-meta-label {{
      color: var(--ac-mid);
      font-weight: 600;
      margin-right: 0.35rem;
    }}
    .lecture-meta time {{
      color: var(--ac-gray);
    }}
    .lecture-action {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      margin-top: 0.85rem;
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--ac-mid);
    }}
    .lecture-arrow {{
      display: inline-block;
      opacity: 0;
      transform: translateX(-4px);
      transition: opacity 0.15s ease, transform 0.15s ease;
    }}
    .lecture-link:hover .lecture-arrow {{
      opacity: 1;
      transform: translateX(0);
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
      .lecture-link {{
        grid-template-columns: 1fr;
        gap: 1rem;
      }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .hero-inner,
      .lecture {{
        animation: none;
      }}
      .lecture-thumb,
      .lecture-arrow {{
        transition: none;
      }}
      .lecture-link:hover .lecture-thumb {{
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
    <div class="lecture-list">
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
    entries = discover_lectures()
    index_path = SITE_DIR / "index.html"
    index_path.write_text(render_index(entries), encoding="utf-8")
    print(f"Wrote {index_path} ({len(entries)} presentation(s))")


if __name__ == "__main__":
    main()
