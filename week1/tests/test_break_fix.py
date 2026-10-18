"""Break-and-fix: the checks that would have caught the upstream change."""

from datetime import date

import pandas as pd
import pytest

from week1.runner import run_pipeline, table_count

from .conftest import AS_OF, CLEAN_ROWS

pytestmark = pytest.mark.fix


def test_date_format_change_is_silent_without_checks(cleaned):
    # This passes even before you write any checks. It shows the problem:
    # the new DD/MM/YYYY rows quietly turn into NaT and get dropped.
    assert len(cleaned("date-format")) < CLEAN_ROWS * 0.7


def test_row_count_check(target, cleaned):
    assert target.checks.check_row_count(cleaned(), 450) is None
    message = target.checks.check_row_count(cleaned("date-format"), 450)
    assert message and "450" in message


def test_freshness_check(target, cleaned):
    assert target.checks.check_freshness(cleaned(), AS_OF, 1) is None
    late = target.checks.check_freshness(cleaned("late"), AS_OF, 1)
    assert late and "2026-03-05" in late
    assert target.checks.check_freshness(cleaned("date-format"), AS_OF, 1)


def test_freshness_check_fails_on_empty_batch(target):
    empty = pd.DataFrame({"txn_date": pd.Series([], dtype="datetime64[ns]")})
    assert target.checks.check_freshness(empty, date(2026, 3, 7), 1)


@pytest.mark.parametrize("break_mode", ["date-format", "late"])
def test_bad_feed_never_reaches_the_warehouse(target, feed, tmp_path, break_mode):
    """End to end: a good load, then a broken feed. With action=stop, yesterday's table survives."""
    db = tmp_path / "w.duckdb"
    good = run_pipeline(target, feed(), db, AS_OF, tmp_path)
    assert good.status == "loaded", good.log
    bad = run_pipeline(target, feed(break_mode), db, AS_OF, tmp_path)
    assert bad.failures, "a broken feed went through without a single failed check"
    if target.card["on_failure"]["action"] == "stop":
        assert bad.status == "stopped"
        assert table_count(db) == CLEAN_ROWS
