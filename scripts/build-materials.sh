#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <session-directory>" >&2
  exit 1
fi

SESSION_DIR="$(cd "$1" && pwd)"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${REPO_ROOT}/_site"
META="${SESSION_DIR}/meta.yaml"

# shellcheck source=session-slug.sh
source "${REPO_ROOT}/scripts/session-slug.sh"
session_slug "$SESSION_DIR"

OUT_DIR="${SITE_DIR}/materials/${SESSION_SLUG}"

if [[ ! -f "$META" ]]; then
  echo "No meta.yaml in ${SESSION_DIR}; skipping materials"
  exit 0
fi

mapfile -t MATERIAL_LINES < <(
  python3 - "$META" "$REPO_ROOT" <<'PY'
import sys
from pathlib import Path

repo_root = Path(sys.argv[2])
sys.path.insert(0, str(repo_root / "scripts"))

from meta_parser import get_materials, parse_meta

meta = parse_meta(Path(sys.argv[1]))
for item in get_materials(meta):
    print(f"{item['path']}\t{item['label']}")
PY
)

if [[ ${#MATERIAL_LINES[@]} -eq 0 ]]; then
  exit 0
fi

mkdir -p "$OUT_DIR"
built=0

for line in "${MATERIAL_LINES[@]}"; do
  [[ -n "$line" ]] || continue
  rel_path="${line%%$'\t'*}"
  src="${SESSION_DIR}/${rel_path}"

  if [[ ! -f "$src" ]]; then
    echo "Warning: material not found, skipping: ${rel_path}" >&2
    continue
  fi

  base="$(basename "$rel_path")"
  dest="${OUT_DIR}/${base}"
  cp "$src" "$dest"
  echo "Copied ${dest}"

  if [[ "${base##*.}" == "ipynb" ]]; then
    stem="${base%.ipynb}"
    if command -v jupyter >/dev/null 2>&1; then
      jupyter nbconvert \
        --to html \
        --output "${stem}.html" \
        --output-dir "$OUT_DIR" \
        "$dest" >/dev/null
      echo "Rendered ${OUT_DIR}/${stem}.html"
    else
      echo "Warning: jupyter not found; skipped HTML for ${base}" >&2
    fi
  fi

  built=$((built + 1))
done

if [[ $built -gt 0 ]]; then
  echo "Built ${built} material(s) for ${SESSION_SLUG}"
fi
