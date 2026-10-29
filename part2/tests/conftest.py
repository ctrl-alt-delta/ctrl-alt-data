"""Shared fixtures for Part 2 tests."""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from part2.card import load_card
from part2.data.generate import RAW_PATH, generate

PART2_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def raw_csv_path() -> Path:
    if not RAW_PATH.exists():
        generate(RAW_PATH)
    return RAW_PATH


@pytest.fixture
def target_pkg(target_name: str):
    pkg = f"part2.{target_name}"
    return {
        "name": target_name,
        "ingest": importlib.import_module(f"{pkg}.ingest"),
        "transform": importlib.import_module(f"{pkg}.transform"),
        "checks": importlib.import_module(f"{pkg}.checks"),
        "alerts": importlib.import_module(f"{pkg}.alerts"),
        "card_path": PART2_DIR / target_name / "pipeline_card.yaml",
        "card": load_card(PART2_DIR / target_name / "pipeline_card.yaml"),
    }
