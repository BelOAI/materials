#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <session-directory>" >&2
  exit 1
fi

SESSION_DIR="$(cd "$1" && pwd)"
MAIN_TEX="${SESSION_DIR}/main.tex"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE_DIR="${REPO_ROOT}/_site"

# shellcheck source=session-slug.sh
source "${REPO_ROOT}/scripts/session-slug.sh"
session_slug "$SESSION_DIR"

if [[ ! -f "$MAIN_TEX" ]]; then
  echo "Error: main.tex not found in ${SESSION_DIR}" >&2
  exit 1
fi

export TEXINPUTS="${REPO_ROOT}/latex/tex/latex//:${TEXINPUTS:-}"

cd "$SESSION_DIR"

echo "Building ${SESSION_SLUG}..."
pdflatex -file-line-error -halt-on-error -interaction=nonstopmode main.tex >/dev/null
pdflatex -file-line-error -halt-on-error -interaction=nonstopmode main.tex >/dev/null

if [[ ! -f main.pdf ]]; then
  echo "Error: main.pdf was not produced" >&2
  exit 1
fi

PDF_DEST="${SITE_DIR}/pdfs/${SESSION_SLUG}.pdf"
mkdir -p "$(dirname "$PDF_DEST")"
cp main.pdf "$PDF_DEST"
echo "Built ${PDF_DEST}"
