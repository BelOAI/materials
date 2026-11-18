"""Собирает условия и разборы этапов в формате олимпиадных сборников."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from datetime import date
from importlib.util import find_spec
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

from handbook_pdf import Builder, environment, walk
from handbook_svg import renderer_identity
from contest_site import load_contests, validate_links
from repo_paths import REPO_ROOT


def _chrome() -> tuple[Path, str]:
    candidates = [os.environ.get("CHROME_BIN", ""), shutil.which("google-chrome") or "",
                  shutil.which("chromium") or "",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    binary = next((Path(item).resolve() for item in candidates if item and Path(item).is_file()), None)
    if binary is None:
        raise ValueError("Для PDF рисунков нужен Google Chrome или Chromium в PATH")
    result = subprocess.run([str(binary), "--version"], text=True, capture_output=True, check=True)
    return binary, result.stdout.strip()


def _svg_pdf(source: Path, destination: Path, chrome: Path, identity: str) -> None:
    root = ElementTree.fromstring(source.read_bytes())
    width, height = root.get("width"), root.get("height")
    if not width or not height:
        box = root.get("viewBox", "").split()
        if len(box) != 4:
            raise ValueError(f"SVG без размеров: {source}")
        width, height = box[2], box[3]
    width = width.removesuffix("px")
    height = height.removesuffix("px")
    html = ("<!doctype html><html><head><meta charset=utf-8><style>"
            f"@page{{size:{width}px {height}px;margin:0}}"
            f"html,body{{margin:0;width:{width}px;height:{height}px;"
            "-webkit-print-color-adjust:exact;print-color-adjust:exact}"
            "body>svg{display:block}</style></head><body>"
            + source.read_text(encoding="utf-8") + "</body></html>")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="contest-svg-") as temp:
        folder = Path(temp)
        page = folder / "figure.html"
        page.write_text(html, encoding="utf-8")
        command = [str(chrome), "--headless=new", "--disable-gpu", "--disable-extensions",
                   "--disable-background-networking", "--no-first-run", "--no-default-browser-check",
                   "--no-pdf-header-footer", f"--user-data-dir={folder / 'profile'}",
                   f"--print-to-pdf={destination}", page.as_uri()]
        subprocess.run(command, text=True, capture_output=True, check=True)
    if not destination.is_file() or destination.stat().st_size < 100:
        raise ValueError(f"Chromium не создал PDF из {source} ({identity})")


def _prepare(builder: Builder, root: Path, item: dict, source: Path) -> dict:
    identifier = item["id"] + "/" + source.stem
    _, ast, _ = builder.prepare({"id": identifier, "_content": source})
    asset_folder = source.parent
    for node in walk(ast):
        if node.get("t") != "Image":
            continue
        href = node["c"][2][0]
        parsed = urlsplit(href)
        if parsed.scheme or parsed.netloc:
            raise ValueError(f"{identifier}: PDF требует локальный рисунок: {href}")
        path = (asset_folder / unquote(parsed.path)).resolve()
        if not path.is_relative_to((root / "contests").resolve()) or not path.is_file():
            raise ValueError(f"{identifier}: рисунок отсутствует или вне contests: {href}")
        if path.suffix.lower() == ".svg" and builder.svg_identity is None:
            chrome, chrome_id = _chrome()
            key = hashlib.sha256(path.read_bytes() + chrome_id.encode()).hexdigest()
            target = builder.scratch / "images" / (key + ".pdf")
            if not target.is_file():
                _svg_pdf(path, target, chrome, chrome_id)
            node["c"][2][0] = "images/" + target.name
        else:
            node["c"][2][0] = builder.image(path)[1]
    return ast


def _tex(text: str) -> str:
    return text.translate(str.maketrans({
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%",
        "$": r"\$", "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }))


def _raw(text: str) -> dict:
    return {"t": "RawBlock", "c": ["latex", text]}


def _task_heading(task: dict) -> tuple[str, str]:
    code, separator, title = task["title"].partition(" — ")
    return ("Задача " + code, title) if separator else ("Задача", code)


def _sample_pair(blocks: list[dict]) -> list[dict]:
    """Сверстать два CSV из одного раздела примера как таблицу."""
    for index, block in enumerate(blocks):
        if block["t"] != "Header" or block["c"][2] != [{"t": "Str", "c": "Пример"}]:
            continue
        end = next((i for i in range(index + 1, len(blocks)) if blocks[i]["t"] == "Header"), len(blocks))
        code = [i for i in range(index + 1, end)
                if blocks[i]["t"] == "CodeBlock" and "csv" in blocks[i]["c"][0][1]]
        if len(code) == 2:
            first, second = code
            return [
                *blocks[:first], *blocks[first + 1:second],
                _raw(r"\begin{contestsample}\begin{contestsamplecolumn}"),
                blocks[first],
                _raw(r"\end{contestsamplecolumn}&\begin{contestsamplecolumn}"),
                blocks[second],
                _raw(r"\end{contestsamplecolumn}\end{contestsample}"),
                *blocks[second + 1:],
            ]
    return blocks


def _statement(task: dict, ast: dict) -> list[dict]:
    number, title = map(_tex, _task_heading(task))
    for block in ast["blocks"]:
        if block["t"] == "Header":
            block["c"][0] = 2
            block["c"][1][0] = task["slug"] + "-" + block["c"][1][0]
    heading = number + ". " + title
    return [_raw(r"\begin{problem}{" + heading + "}{}{}{}{}{}"),
            *_sample_pair(ast["blocks"]), _raw(r"\end{problem}")]


def _document(template: dict, title: str, blocks: list[dict]) -> dict:
    meta = {"lang": {"t": "MetaString", "c": "ru-RU"},
            "title": {"t": "MetaString", "c": title}}
    return {**template, "meta": meta, "blocks": blocks}


def build(root: Path = REPO_ROOT, site_dir: Path | None = None) -> int:
    root = root.resolve()
    output = (site_dir or root / "_site").resolve()
    stages = list(load_contests(root)["_stages"].values())
    if not stages:
        return 0
    tools, env = environment()
    headers = {name: (root / "utils/pdf" / f"contest-{name}.tex").read_text(encoding="utf-8")
               for name in ("statements", "debrief")}
    count = 0
    with tempfile.TemporaryDirectory(prefix="contest-pdf-") as temp:
        builder = Builder(root, Path(temp), "https://materials.beloai.by/", tools, env, "reader")
        if find_spec("playwright") is not None:
            builder.svg_identity = renderer_identity()
        for stage in stages:
            date_label = date.fromisoformat(stage["date"]).strftime("%d.%m.%Y")
            stage_header = r"\renewcommand{\conteststage}{" + _tex(stage["title"]) + "}\n"
            base = "contests/" + stage["id"]

            def compile_pdf(name, document):
                header = headers[name] + stage_header
                if name == "statements":
                    header += r"\renewcommand{\contestdate}{" + date_label + "}\n"
                builder.compile({"item": {"id": stage["id"] + "/" + name},
                                 "filename": f"{base}/{name}.pdf", "toc": False},
                                document, output, extra_header=header)

            statements, solutions = [], []
            for task in stage["tasks"]:
                statement = _prepare(builder, root, task, task["_statement"])
                statements.extend(_statement(task, statement))

                solution = _prepare(builder, root, task, task["_analysis"])
                for block in solution["blocks"]:
                    if block["t"] == "Header":
                        block["c"][0] = 2
                solutions.append({"t": "Header", "c": [
                    1, [task["slug"], [], []],
                    [{"t": "Str", "c": ": ".join(_task_heading(task))}],
                ]})
                solutions.extend(solution["blocks"])
            compile_pdf("statements", _document(statement, stage["title"] + " — условия задач", statements))
            compile_pdf("debrief", _document(solution, stage["title"] + " — разбор задач", solutions))
            for legacy in (output / base).glob("*/statement.pdf"):
                legacy.unlink()
            count += 2
    validate_links(output, require_pdfs=True)
    print(f"PDF условий и разборов: {count}")
    return count
