#!/usr/bin/env bash
# Download Unbounded and IBM Plex Sans (latin + cyrillic subsets) into site/fonts/.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FONTS_DIR="${REPO_ROOT}/site/fonts"
VENV="${REPO_ROOT}/.venv-fonts"
GOOGLE_FONTS="https://raw.githubusercontent.com/google/fonts/main"

mkdir -p "${FONTS_DIR}"

if [[ ! -d "${VENV}" ]]; then
  python3 -m venv "${VENV}"
  "${VENV}/bin/pip" install -q fonttools brotli
fi

PYTHON="${VENV}/bin/python3"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

curl -fsSL "${GOOGLE_FONTS}/ofl/unbounded/Unbounded%5Bwght%5D.ttf" \
  -o "${TMP_DIR}/unbounded.ttf"
curl -fsSL "${GOOGLE_FONTS}/ofl/ibmplexsans/IBMPlexSans%5Bwdth%2Cwght%5D.ttf" \
  -o "${TMP_DIR}/ibm-plex-sans.ttf"
curl -fsSL "${GOOGLE_FONTS}/ofl/unbounded/OFL.txt" \
  -o "${FONTS_DIR}/OFL-Unbounded.txt"
curl -fsSL "${GOOGLE_FONTS}/ofl/ibmplexsans/OFL.txt" \
  -o "${FONTS_DIR}/OFL-IBMPlexSans.txt"

"${PYTHON}" - "${TMP_DIR}" "${FONTS_DIR}" <<'PY'
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

tmp_dir = Path(sys.argv[1])
fonts_dir = Path(sys.argv[2])

UNICODE_RANGES = [
    (0x0000, 0x00FF),
    (0x0100, 0x024F),
    (0x0400, 0x04FF),
    (0x0500, 0x052F),
    (0x2000, 0x206F),
    (0x20AC, 0x20AC),
    (0x2013, 0x2014),
    (0x00AB, 0x00BB),
]

FONTS = [
    ("unbounded.ttf", "unbounded-latin-cyrillic.woff2"),
    ("ibm-plex-sans.ttf", "ibm-plex-sans-latin-cyrillic.woff2"),
]


def subset_to_woff2(src: Path, dest: Path) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.recalc_bounds = True
    options.recalc_timestamp = False
    options.desubroutinize = True

    unicodes = []
    for start, end in UNICODE_RANGES:
        unicodes.extend(range(start, end + 1))

    options.unicodes = unicodes

    font = TTFont(src)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    font.flavor = "woff2"
    font.save(dest)


for src_name, dest_name in FONTS:
    subset_to_woff2(tmp_dir / src_name, fonts_dir / dest_name)
    print(f"Wrote {fonts_dir / dest_name}")
PY

echo "Fonts vendored to ${FONTS_DIR}"
