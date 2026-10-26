#!/usr/bin/env bash
# Путь материала относительно course/.
session_slug() {
  local dir
  dir="$(cd "$1" && pwd)"
  SESSION_SLUG="$(python3 - "$dir" "$REPO_ROOT" <<'PYTHON'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[2]) / 'utils/scripts'))
from course_catalog import session_slug
print(session_slug(Path(sys.argv[1])))
PYTHON
)" || return 1
}
