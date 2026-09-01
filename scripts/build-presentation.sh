#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <lecture-directory>" >&2
  exit 1
fi

LECTURE_DIR="$(cd "$1" && pwd)"
MAIN_TEX="${LECTURE_DIR}/main.tex"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${REPO_ROOT}/_site"
SLUG="$(basename "$LECTURE_DIR")"

if [[ ! -f "$MAIN_TEX" ]]; then
  echo "Error: main.tex not found in ${LECTURE_DIR}" >&2
  exit 1
fi

export TEXINPUTS="${REPO_ROOT}/latex/tex/latex//:${TEXINPUTS:-}"

cd "$LECTURE_DIR"

echo "Building ${SLUG}..."
pdflatex -file-line-error -halt-on-error -interaction=nonstopmode main.tex >/dev/null
pdflatex -file-line-error -halt-on-error -interaction=nonstopmode main.tex >/dev/null

if [[ ! -f main.pdf ]]; then
  echo "Error: main.pdf was not produced" >&2
  exit 1
fi

mkdir -p "${SITE_DIR}/pdfs"
cp main.pdf "${SITE_DIR}/pdfs/${SLUG}.pdf"
echo "Built ${SITE_DIR}/pdfs/${SLUG}.pdf"
