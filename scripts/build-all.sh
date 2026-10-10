#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${REPO_ROOT}/_site"
META_PARSER="${REPO_ROOT}/scripts/parse-meta.py"

# Удаляем только генерируемые ресурсы, включая результаты удалённых занятий.
rm -rf "${SITE_DIR}/pdfs" "${SITE_DIR}/thumbs" "${SITE_DIR}/materials"
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

for kind in lectures practices assignments; do
  kind_dir="${REPO_ROOT}/${kind}"
  [[ -d "$kind_dir" ]] || continue

  for session_dir in "${kind_dir}"/*/; do
    [[ -d "$session_dir" ]] || continue

    if ! should_build "$session_dir"; then
      echo "Skipping $(basename "$session_dir")"
      continue
    fi

    python3 "${REPO_ROOT}/scripts/build-session.py" "$session_dir"

  done
done

echo "All sessions built."
