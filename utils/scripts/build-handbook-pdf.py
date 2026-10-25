"""Build a print-friendly handbook chapter with the SDS-en PDF profile."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import tempfile

import pymupdf
import yaml


ROOT = Path(__file__).resolve().parents[2]
STYLE = ROOT / "handbooks/pdf"


def print_source(article: Path, scratch: Path) -> Path:
    source = (article / "content.md").read_text(encoding="utf-8")
    metadata = yaml.safe_load(article.joinpath("meta.yaml").read_text(encoding="utf-8"))
    title = metadata["title"]
    authors = ", ".join(metadata.get("authors", []))

    for index, match in enumerate(re.finditer(r"!\[[^]]*\]\(([^)]+\.svg)\)", source)):
        svg_path = (article / match.group(1)).resolve()
        if not svg_path.is_relative_to(article.resolve()):
            raise ValueError(f"SVG outside article: {svg_path}")
        pdf_path = scratch / f"figure-{index + 1}.pdf"
        svg = pymupdf.open(svg_path)
        try:
            pdf_path.write_bytes(svg.convert_to_pdf())
        finally:
            svg.close()
        original = match.group(0)
        rendered = original.replace(match.group(1), pdf_path.as_posix()) + "{ width=85% }"
        source = source.replace(original, rendered)

    source = re.sub(r"<details>\s*<summary>Подсказка</summary>", "\n\n**Подсказка.**\n\n", source)
    source = re.sub(r"<details>\s*<summary>Решение</summary>", "\n\n**Ответ и разбор.**\n\n", source)
    source = source.replace("</details>", "").replace("<br>", "  \n")
    source = re.sub(r"(?m)^(### \d+\.)", r"\\Needspace{8\\baselineskip}\n\n\1", source)
    source = source.replace("## Самопроверка", "\\begingroup\\small\\setlength{\\parskip}{2pt}\n\n## Самопроверка", 1)
    source += "\n\n\\endgroup\n"
    label = "Автор" if len(metadata.get("authors", [])) == 1 and not authors.startswith("Авторы") else "Авторы"
    byline = f"**{label}:** {authors}\n\n" if authors else ""
    source = f"# {title}\n\n{byline}" + source

    output = scratch / "chapter.md"
    output.write_text(source, encoding="utf-8", newline="\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path, help="Chapter directory containing content.md and meta.yaml")
    parser.add_argument("--output", type=Path, help="Output PDF path")
    args = parser.parse_args()
    article = args.article.resolve()
    if not article.is_dir():
        parser.error(f"Not a directory: {article}")
    output = (args.output or ROOT / "output/pdf" / f"{article.name}.pdf").resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="handbook-pdf-") as temp:
        source = print_source(article, Path(temp))
        command = [
            "pandoc", str(source),
            "--from=markdown+raw_tex",
            "--pdf-engine=xelatex",
            "--lua-filter", str(STYLE / "keep-short-code.lua"),
            "--include-in-header", str(STYLE / "pdf-header.tex"),
            "-V", "papersize:a4",
            "-V", "geometry:margin=18mm",
            "-V", "fontsize:10pt",
            "-V", "mainfont:Times New Roman",
            "-V", "monofont:Consolas",
            "-V", "lang:ru-RU",
            "--output", str(output),
        ]
        subprocess.run(command, check=True, cwd=article)
    pdf = pymupdf.open(output)
    try:
        print(f"{output} ({len(pdf)} pages)")
    finally:
        pdf.close()


if __name__ == "__main__":
    main()
