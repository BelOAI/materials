#!/usr/bin/env python3
"""Отдельная сборка учебника на общей оболочке сайта."""
import importlib.util
from pathlib import Path

from repo_paths import REPO_ROOT as root
spec = importlib.util.spec_from_file_location('generate_site', root / 'utils/scripts/generate-site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)
site.main()
