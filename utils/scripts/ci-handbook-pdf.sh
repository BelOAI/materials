#!/usr/bin/env bash
set -euo pipefail
export PDF_RENDER_TESTS=1
export PRESS_RENDER_TESTS=1
npm --prefix utils/site ci
python3 -m unittest discover -s utils/scripts/tests
mkdir -p output/release
python3 utils/scripts/build-handbook-pdf.py handbooks/ml --book-only \
  --output output/release/beloai-ml-handbook.pdf --site-url https://materials.beloai.by/
python3 utils/scripts/build-handbook-pdf.py handbooks/ml --book-only --profile belarus-textbook \
  --output output/release/beloai-ml-handbook-belarus-textbook.pdf --site-url https://materials.beloai.by/
python3 - <<'PY'
import hashlib
from pathlib import Path
import re
import subprocess
import importlib.util
spec = importlib.util.spec_from_file_location('release', 'utils/scripts/handbook-release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
folder = Path('output/release')
checksums = []
for name in release.PDF_ASSETS:
    pdf = folder / name
    info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
    match = re.search(r'^Pages:\s+(\d+)', info, re.M)
    if not match or int(match[1]) < 1 or re.search(r'Encrypted:\s*yes', info):
        raise SystemExit(f'Неверный PDF: {name}')
    checksums.append(f'{hashlib.sha256(pdf.read_bytes()).hexdigest()}  {pdf.name}\n')
(folder / 'SHA256SUMS').write_text(''.join(checksums))
release.verify_assets(folder)
PY

# Separate production artifact; the public release still contains the two reader PDFs.
python3 utils/scripts/build-handbook-pdf.py handbooks/ml --book-only --profile belarus-textbook --press-ready
