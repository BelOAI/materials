#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${REPO_ROOT}/_site"
META_PARSER="${REPO_ROOT}/scripts/parse-meta.py"

mkdir -p "${SITE_DIR}/pdfs" "${SITE_DIR}/thumbs" "${SITE_DIR}/materials"

should_build() {
  local dir="$1"
  local base
  base="$(basename "$dir")"

  if [[ "$base" == _* ]]; then
    return 1
  fi

  if [[ -f "${dir}/meta.yaml" ]]; then
    if python3 "$META_PARSER" "$dir/meta.yaml" build 2>/dev/null | grep -qx 'false'; then
      return 1
    fi
  fi

  return 0
}

for lecture_dir in "${REPO_ROOT}"/lectures/*/; do
  [[ -d "$lecture_dir" ]] || continue

  if ! should_build "$lecture_dir"; then
    echo "Skipping $(basename "$lecture_dir")"
    continue
  fi

  if [[ -f "${lecture_dir}/main.tex" ]]; then
    "${REPO_ROOT}/scripts/build-presentation.sh" "$lecture_dir"

    slug="$(basename "$lecture_dir")"
    if command -v pdftoppm >/dev/null 2>&1 && [[ -f "${lecture_dir}/main.pdf" ]]; then
      pdftoppm -png -f 1 -l 1 -singlefile \
        "${lecture_dir}/main.pdf" "${SITE_DIR}/thumbs/${slug}" || true
      if [[ -f "${SITE_DIR}/thumbs/${slug}.png" ]]; then
        echo "Thumbnail ${SITE_DIR}/thumbs/${slug}.png"
      fi
    fi
  fi

  "${REPO_ROOT}/scripts/build-materials.sh" "$lecture_dir"
done

echo "All presentations built."
