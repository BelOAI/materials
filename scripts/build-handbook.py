#!/usr/bin/env python3
"""Отдельная сборка учебника на общей оболочке сайта."""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('generate_site', root / 'scripts/generate-site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)
site.main()
