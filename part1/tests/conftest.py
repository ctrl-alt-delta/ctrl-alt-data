from datetime import date
from pathlib import Path

import pytest

from part1.data.generate import write_csv
from part1.runner import load_target

AS_OF = date(2026, 3, 7)
CLEAN_ROWS = 486  # 500 transactions - 6 bad dates - 8 missing amounts (15 duplicates removed)


@pytest.fixture(scope="session")
def target(target_name):
    return load_target(target_name)


@pytest.fixture
def feed(tmp_path):
    """Write a feed (optionally broken) into a temp folder and return its path."""

    def _make(break_mode=None) -> Path:
        return write_csv(tmp_path / f"landing-{break_mode or 'normal'}" / "transactions.csv", break_mode=break_mode)

    return _make


@pytest.fixture
def cleaned(target, feed):
    """Run extract + clean for a given feed, using the target's code."""

    def _clean(break_mode=None):
        return target.pipeline.clean(target.pipeline.extract(feed(break_mode)))

    return _clean
