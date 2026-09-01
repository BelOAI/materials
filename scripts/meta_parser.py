#!/usr/bin/env python3
"""Minimal YAML reader for lecture meta.yaml (flat keys + list blocks, no deps)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REFERENCE_KIND_LABELS = {
    "contest": "Яндекс.Контест",
    "kaggle": "Kaggle",
    "huggingface": "Hugging Face",
    "colab": "Google Colab",
}

MATERIAL_EXTENSION_LABELS = {
    ".ipynb": "Jupyter Notebook",
    ".pdf": "PDF",
    ".zip": "Архив",
    ".csv": "CSV",
    ".py": "Python",
    ".md": "Markdown",
}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _parse_scalar(line: str) -> tuple[str, str] | None:
    match = re.match(r"^([A-Za-z_]+):\s*(.+)$", line.strip())
    if not match:
        return None
    return match.group(1), _strip_quotes(match.group(2))


def parse_meta(path: Path) -> dict[str, Any]:
    """Parse meta.yaml into flat fields plus list blocks for references/materials."""
    lines = path.read_text(encoding="utf-8").splitlines()
    data: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        i += 1
        if not stripped or stripped.startswith("#"):
            continue

        if re.match(r"^([A-Za-z_]+):\s*$", stripped):
            key = stripped.split(":", 1)[0]
            items, i = _parse_list_block(lines, i)
            data[key] = items
            continue

        parsed = _parse_scalar(stripped)
        if parsed:
            key, value = parsed
            data[key] = value

    return data


def _parse_list_block(lines: list[str], start: int) -> tuple[list[dict[str, str]], int]:
    items: list[dict[str, str]] = []
    i = start
    current: dict[str, str] | None = None

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if not raw.startswith(" ") and not raw.startswith("\t"):
            break

        if stripped.startswith("- "):
            if current:
                items.append(current)
            current = {}
            remainder = stripped[2:].strip()
            if remainder:
                parsed = _parse_scalar(remainder)
                if parsed:
                    current[parsed[0]] = parsed[1]
            i += 1
            continue

        parsed = _parse_scalar(stripped)
        if parsed and current is not None:
            current[parsed[0]] = parsed[1]
        i += 1

    if current:
        items.append(current)

    return items, i


def get_flat(meta: dict[str, Any], key: str, default: str = "") -> str:
    value = meta.get(key, default)
    if isinstance(value, str):
        return value
    return default


def get_references(meta: dict[str, Any]) -> list[dict[str, str]]:
    raw = meta.get("references", [])
    if not isinstance(raw, list):
        return []

    refs: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "").strip()
        if not url:
            continue
        kind = item.get("kind", "").strip().lower()
        label = item.get("label", "").strip()
        if not label and kind:
            label = REFERENCE_KIND_LABELS.get(kind, "")
        if not label:
            continue
        refs.append({"kind": kind, "label": label, "url": url})

    refs.sort(key=lambda ref: (0 if ref["kind"] == "contest" else 1, ref["label"].lower()))
    return refs


def get_materials(meta: dict[str, Any]) -> list[dict[str, str]]:
    raw = meta.get("materials", [])
    if not isinstance(raw, list):
        return []

    materials: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        path = item.get("path", "").strip()
        if not path:
            continue
        label = item.get("label", "").strip()
        if not label:
            suffix = Path(path).suffix.lower()
            label = MATERIAL_EXTENSION_LABELS.get(suffix, Path(path).name)
        materials.append({"path": path, "label": label})

    return materials


def material_label_for_path(path: str, label: str = "") -> str:
    if label.strip():
        return label.strip()
    suffix = Path(path).suffix.lower()
    return MATERIAL_EXTENSION_LABELS.get(suffix, Path(path).name)
