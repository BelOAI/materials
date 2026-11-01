"""Find visibly overlapping words in a rendered handbook PDF.

Usage: python utils/scripts/check-pdf-overlaps.py output/pdf/ml/classic-ml/chapter.pdf
Requires PyMuPDF. Visual review is still needed for drawings and table borders.
"""

import argparse
from pathlib import Path
import re

import pymupdf


def overlaps(path):
    with pymupdf.open(path) as document:
        for page_number, page in enumerate(document, 1):
            words = sorted(page.get_text("words"), key=lambda word: word[1])
            for index, left in enumerate(words):
                a = pymupdf.Rect(left[:4])
                for right in words[index + 1:]:
                    if right[1] >= a.y1:
                        break
                    b = pymupdf.Rect(right[:4])
                    common = a & b
                    if common.is_empty:
                        continue
                    # Formula indices and superscripts often overlap by design.
                    if (len(left[4]) < 2 or len(right[4]) < 2
                            or re.search(r"[=()−+.]", left[4] + right[4])):
                        continue
                    if (common.width >= 2 and common.height >= min(a.height, b.height) * 0.35
                            and left[4] != right[4]):
                        yield page_number, left[4], right[4], tuple(round(v, 1) for v in common)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    found = list(overlaps(args.pdf))
    for page, left, right, rect in found:
        print(f"стр. {page}: {left!r} / {right!r} — {rect}")
    if found:
        raise SystemExit(f"Найдены пересечения слов: {len(found)}")
    print("Пересечений слов не найдено")


if __name__ == "__main__":
    main()
