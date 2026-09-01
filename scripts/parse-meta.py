#!/usr/bin/env python3
"""Minimal YAML field reader for flat meta.yaml files (no external deps)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meta_parser import get_flat, parse_meta

from meta_parser import get_flat, parse_meta


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: parse-meta.py <meta.yaml> <field>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    field = sys.argv[2]
    data = parse_meta(path)
    value = get_flat(data, field, "")
    print(value)


if __name__ == "__main__":
    main()
