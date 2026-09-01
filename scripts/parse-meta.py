#!/usr/bin/env python3
"""Minimal YAML field reader for flat meta.yaml files (no external deps)."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_meta(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_]+):\s*(.+)$", line)
        if not match:
            continue
        key, raw = match.group(1), match.group(2).strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        elif raw.startswith("'") and raw.endswith("'"):
            raw = raw[1:-1]
        data[key] = raw
    return data


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: parse-meta.py <meta.yaml> <field>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    field = sys.argv[2]
    data = parse_meta(path)
    value = data.get(field, "")
    print(value)


if __name__ == "__main__":
    main()
