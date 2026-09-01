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

# shellcheck source=session-slug.sh
source "${REPO_ROOT}/scripts/session-slug.sh"

for kind in lectures practices; do
  kind_dir="${REPO_ROOT}/${kind}"
  [[ -d "$kind_dir" ]] || continue

  for session_dir in "${kind_dir}"/*/; do
    [[ -d "$session_dir" ]] || continue

    if ! should_build "$session_dir"; then
      echo "Skipping $(basename "$session_dir")"
      continue
    fi

    session_slug "$session_dir"

    if [[ -f "${session_dir}/main.tex" ]]; then
      "${REPO_ROOT}/scripts/build-presentation.sh" "$session_dir"

      if command -v pdftoppm >/dev/null 2>&1 && [[ -f "${session_dir}/main.pdf" ]]; then
        thumb_dir="${SITE_DIR}/thumbs/$(dirname "$SESSION_SLUG")"
        mkdir -p "$thumb_dir"
        pdftoppm -png -f 1 -l 1 -singlefile \
          "${session_dir}/main.pdf" "${SITE_DIR}/thumbs/${SESSION_SLUG}" || true
        if [[ -f "${SITE_DIR}/thumbs/${SESSION_SLUG}.png" ]]; then
          echo "Thumbnail ${SITE_DIR}/thumbs/${SESSION_SLUG}.png"
        fi
      fi
    fi

    "${REPO_ROOT}/scripts/build-materials.sh" "$session_dir"
  done
done

echo "All presentations built."
