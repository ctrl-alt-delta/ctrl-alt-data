"""Tiny loader and validator for Part 2's pipeline_card.yaml.

Reads the subset of YAML used by pipeline_card.yaml (key: value, nested maps,
and simple lists) using only the Python standard library.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_KEYS = (
    "name",
    "owner",
    "freshness_sla_minutes",
    "watermark_minutes",
    "grain",
    "required_fields",
    "allowed_currencies",
    "tables",
    "bad_run_policy",
)


def _scalar(raw: str) -> Any:
    s = raw.strip()
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x) for x in inner.split(",")] if inner else []
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if s.isdigit():
        return int(s)
    return s


def load_card(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key is not None:
            data.setdefault(current_key, []).append(_scalar(line[4:]))
        elif line.startswith("  ") and ":" in line and current_key is not None:
            sub_k, sub_v = line.strip().split(":", 1)
            if not isinstance(data.get(current_key), dict):
                data[current_key] = {}
            data[current_key][sub_k.strip()] = _scalar(sub_v)
        elif ":" in line:
            k, v = line.split(":", 1)
            current_key = k.strip()
            data[current_key] = _scalar(v) if v.strip() else []
    return data


def validate_card(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for k in REQUIRED_KEYS:
        val = card.get(k)
        if val in (None, "", [], {}):
            errors.append(f"pipeline_card.yaml: '{k}' is missing or empty")
        elif isinstance(val, str) and "TODO" in val:
            errors.append(f"pipeline_card.yaml: '{k}' still contains TODO ({val!r})")
    for int_key in ("freshness_sla_minutes", "watermark_minutes"):
        val = card.get(int_key)
        if not isinstance(val, int) or val <= 0:
            errors.append(f"pipeline_card.yaml: '{int_key}' must be a positive integer, got {val!r}")
    tables = card.get("tables")
    if isinstance(tables, dict):
        for tk in ("bronze", "silver", "gold", "quarantine"):
            tv = tables.get(tk, "")
            if not tv or "TODO" in str(tv):
                errors.append(f"pipeline_card.yaml: tables.{tk} is missing or TODO")
    else:
        errors.append("pipeline_card.yaml: 'tables' must be a mapping of bronze/silver/gold/quarantine")
    return errors
