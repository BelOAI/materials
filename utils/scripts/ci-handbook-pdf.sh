#!/usr/bin/env bash
set -euo pipefail
python3 -m unittest discover -s utils/scripts/tests
mkdir -p output/release
python3 utils/scripts/build-handbook-pdf.py handbooks/ml --book-only \
  --output output/release/beloai-ml-handbook.pdf --site-url https://materials.beloai.by/
python3 - <<'PY'
import hashlib
from pathlib import Path
import re
import subprocess
pdf = Path('output/release/beloai-ml-handbook.pdf')
info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
match = re.search(r'^Pages:\s+(\d+)', info, re.M)
if not match or int(match[1]) < 1:
    raise SystemExit('PDF не содержит страниц')
(pdf.parent / 'SHA256SUMS').write_text(f'{hashlib.sha256(pdf.read_bytes()).hexdigest()}  {pdf.name}\n')
PY
