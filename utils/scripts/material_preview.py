#!/usr/bin/env python3
"""Создание превью PDF или Jupyter Notebook для учебного материала."""

import base64
import html
import io
import json
import keyword
import shutil
import subprocess
import sys
import tokenize
import xml.etree.ElementTree as ET
from pathlib import Path

from meta_parser import get_materials, parse_meta

from repo_paths import REPO_ROOT


def notebook_content(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    cells = data["cells"]
    if not isinstance(cells, list):
        raise ValueError("поле cells должно быть списком")
    content = []
    for cell in cells:
        source = cell.get("source", "")
        if isinstance(source, list) and all(isinstance(line, str) for line in source):
            source = "".join(source)
        if not isinstance(source, str):
            raise ValueError("неверный текст ячейки")
        kind = cell.get("cell_type")
        if kind == "code" and source.strip():
            content.append((kind, source.strip()))
    return content[:4] or None


def highlighted_line(line):
    parts, position = [], 0
    try:
        for token in tokenize.generate_tokens(io.StringIO(line).readline):
            if token.start[0] != 1 or token.type in (
                tokenize.NEWLINE,
                tokenize.ENDMARKER,
            ):
                continue
            start, end = token.start[1], token.end[1]
            parts.append(html.escape(line[position:start]))
            color = None
            if token.type == tokenize.STRING:
                color = "#18704a"
            elif token.type == tokenize.COMMENT:
                color = "#6b7789"
            elif token.type == tokenize.NUMBER:
                color = "#a34b16"
            elif token.type == tokenize.NAME and keyword.iskeyword(token.string):
                color = "#7951b0"
            elif token.type == tokenize.NAME and token.string in (
                "print",
                "len",
                "range",
                "sum",
            ):
                color = "#2469a5"
            text = html.escape(line[start:end])
            parts.append(f'<tspan fill="{color}">{text}</tspan>' if color else text)
            position = end
    except (tokenize.TokenError, IndentationError):
        pass  # Незавершённая строка в миниатюре остаётся обычным текстом.
    parts.append(html.escape(line[position:]))
    return "".join(parts)


def render_preview(content):
    logo_root = ET.fromstring((REPO_ROOT / "utils/site/assets/python-logo.svg").read_bytes())
    logo_root.set("viewBox", "0 0 111.161 112")
    logo_root.set("width", "112")
    logo_root.set("height", "112")
    for shadow in logo_root.findall("{http://www.w3.org/2000/svg}ellipse"):
        logo_root.remove(shadow)
    logo = base64.b64encode(ET.tostring(logo_root)).decode("ascii")
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">',
        '<rect width="640" height="360" fill="#f8fafc"/>',
        '<g font-family="monospace" font-size="19" fill="#28364a">',
    ]
    y = 38
    for kind, source in content:
        if kind != "code" or y > 318:
            continue
        if y > 38:
            parts.append(
                f'<path d="M28 {y - 26} H{480 if y - 26 >= 228 else 612}" stroke="#d5dde8" stroke-width="1"/>'
            )
        source_lines = source.expandtabs(4).splitlines()
        for index, line in enumerate(source_lines[:6]):
            if y > 326:
                break
            width = 39 if y > 218 else 50
            if len(line) > width:
                line = line[: width - 1] + "…"
            if index == 5 and len(source_lines) > 6:
                line = line[: width - 2] + " …"
            parts.append(
                f'<text xml:space="preserve" x="28" y="{y}">{highlighted_line(line)}</text>'
            )
            y += 26
        y += 24
    parts.extend(
        [
            "</g>",
            '<rect x="508" y="228" width="132" height="132" fill="#e8eef5"/>',
            f'<image aria-label="Python" x="528" y="248" width="92" height="92" href="data:image/svg+xml;base64,{logo}"/>',
            "</svg>",
        ]
    )
    return "\n".join(parts) + "\n"


def build_preview(session_dir, site_dir):
    if session_dir.parent.name not in ("lectures", "practices", "assignments"):
        return
    slug = f"{session_dir.parent.name}/{session_dir.name}"
    output = site_dir / "thumbs" / slug
    pdf_preview = site_dir / "thumbs" / f"{slug}.png"
    pdf_preview.unlink(missing_ok=True)
    if output.is_dir():
        shutil.rmtree(output)
    else:
        output.unlink(missing_ok=True)

    pdf = site_dir / "pdfs" / f"{slug}.pdf"
    if pdf.is_file():
        if not shutil.which("pdftoppm"):
            print(
                f"Предупреждение: pdftoppm не найден, PDF {slug} опубликован без превью.",
                file=sys.stderr,
            )
            return
        pdf_preview.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                "pdftoppm",
                "-scale-to",
                "1280",
                "-png",
                "-f",
                "1",
                "-l",
                "1",
                "-singlefile",
                str(pdf),
                str(pdf_preview.with_suffix("")),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode or not pdf_preview.is_file():
            pdf_preview.unlink(missing_ok=True)
            print(
                f"Предупреждение: не удалось создать превью PDF {slug}",
                file=sys.stderr,
            )
        else:
            print(f"Превью PDF: {pdf_preview}")
        return

    meta_path = session_dir / "meta.yaml"
    if not meta_path.is_file():
        return
    for material in get_materials(parse_meta(session_dir / "meta.yaml")):
        source = session_dir / material["path"]
        if source.suffix.lower() != ".ipynb" or not source.is_file():
            continue
        try:
            content = notebook_content(source)
            if content:
                output.mkdir(parents=True, exist_ok=True)
                target = output / f"{source.name}.svg"
                target.write_text(render_preview(content), encoding="utf-8")
                print(f"Превью ноутбука: {target}")
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            print(f"Не удалось создать превью {source}: {error}", file=sys.stderr)
        return


if __name__ == "__main__":
    build_preview(Path(sys.argv[1]).resolve(), REPO_ROOT / "_site")
