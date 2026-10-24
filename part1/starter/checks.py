"""Part 1 starter: checks that run BEFORE anything is loaded.

Every check returns None when it passes, or a sentence a tired human can act on.
Two are done for you as examples. The rest raise NotImplementedError, which the
runner reports as "TODO" and lets through. That is the point: a check you never
wrote can't stop a bad load.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


# ---- done for you ---------------------------------------------------------

def check_unique(df: pd.DataFrame, key: str) -> str | None:
    """Q5: one row per business key."""
    dupes = int(df[key].duplicated().sum())
    if dupes:
        return f"unique: {dupes} duplicate {key} value(s)"
    return None


def check_not_null(df: pd.DataFrame, columns: list[str]) -> str | None:
    """Q5: required columns are filled in."""
    nulls = {c: int(df[c].isna().sum() + (df[c].astype(str) == "").sum()) for c in columns}
    bad = {c: n for c, n in nulls.items() if n}
    if bad:
        return f"not null: empty values in {bad}"
    return None


# ---- break-and-fix: TODO 6 and 7 -----------------------------------------

def check_row_count(df: pd.DataFrame, min_rows: int) -> str | None:
    """Q5, how do you know it's right: a sudden drop in rows is the loudest clue.

    TODO 6: return a message like "row count: 289 clean rows, expected at least 450"
    when len(df) < min_rows, otherwise return None.
    """
    raise NotImplementedError("TODO 6: check_row_count")


def check_freshness(df: pd.DataFrame, as_of: date, max_lag_days: int) -> str | None:
    """Q2, how fresh does it need to be: the newest row must be recent enough.

    TODO 7: find the newest txn_date, work out how many days it is behind as_of,
    and return a message naming both dates when the lag is more than max_lag_days.
    An empty DataFrame should fail too.
    Hint: latest = pd.Timestamp(df["txn_date"].max()).date(); (as_of - latest).days
    """
    raise NotImplementedError("TODO 7: check_freshness")


# ---- go further: TODO 8 and 9 --------------------------------------------

def check_schema(raw_columns: list[str], contract_columns: list[str]) -> str | None:
    """Q1, where does the data come from: the source must still send what we agreed.

    TODO 8: compare the raw headers (strip + lower them first) with the contract.
    Return a message that names every missing column, otherwise None.
    """
    raise NotImplementedError("TODO 8: check_schema")


def check_allowed_values(df: pd.DataFrame, column: str, allowed: list[str]) -> str | None:
    """Q5: codes come from a known list.

    TODO 9: return a message naming any values in df[column] not in `allowed`.
    """
    raise NotImplementedError("TODO 9: check_allowed_values")
