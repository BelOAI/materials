"""Единые пути исходников и результатов сборки относительно репозитория."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COURSE_ROOT = REPO_ROOT / 'course'
HANDBOOKS_ROOT = REPO_ROOT / 'handbooks'
UTILS_ROOT = REPO_ROOT / 'utils'
SITE_ROOT = UTILS_ROOT / 'site'
LATEX_ROOT = UTILS_ROOT / 'latex'
SITE_OUTPUT = REPO_ROOT / '_site'
