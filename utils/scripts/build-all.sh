#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
python3 - "$REPO_ROOT" <<'PYTHON'
import sys, shutil, subprocess
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / 'utils/scripts'))
from course_catalog import session_directories
from meta_parser import parse_meta, get_flat
for name in ('pdfs', 'thumbs', 'materials'):
    shutil.rmtree(root / '_site' / name, ignore_errors=True)
    (root / '_site' / name).mkdir(parents=True, exist_ok=True)
for session in session_directories(root / 'course'):
    if get_flat(parse_meta(session / 'material.yml'), 'build', 'true').lower() != 'false':
        subprocess.run([sys.executable, str(root / 'utils/scripts/build-session.py'), str(session)], check=True)
print('All sessions built.')
PYTHON
