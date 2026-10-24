"""Part 1 solution: checks that run BEFORE anything is loaded.

Every check returns None when it passes, or a sentence a tired human can act on.
"""

from __future__ import annotations

from datetime import date

import pandas as pd


def check_schema(raw_columns: list[str], contract_columns: list[str]) -> str | None:
    """Q1, where does the data come from: the source must still send what we agreed."""
    seen = {c.strip().lower() for c in raw_columns}
    missing = [c for c in contract_columns if c not in seen]
    if missing:
        extra = sorted(seen - set(contract_columns))
        return f"schema: missing contract column(s) {missing}; file has unexpected {extra}"
    return None


def check_row_count(df: pd.DataFrame, min_rows: int) -> str | None:
    """Q5, how do you know it's right: a sudden drop in rows is the loudest clue."""
    if len(df) < min_rows:
        return f"row count: {len(df)} clean rows, expected at least {min_rows}"
    return None


def check_freshness(df: pd.DataFrame, as_of: date, max_lag_days: int) -> str | None:
    """Q2, how fresh does it need to be: the newest row must be recent enough."""
    if df.empty:
        return "freshness: no rows, so no newest date"
    latest = pd.Timestamp(df["txn_date"].max()).date()
    lag = (as_of - latest).days
    if lag > max_lag_days:
        return (
            f"freshness: newest txn_date is {latest}, {lag} days before as-of {as_of} "
            f"(allowed: {max_lag_days})"
        )
    return None


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


def check_allowed_values(df: pd.DataFrame, column: str, allowed: list[str]) -> str | None:
    """Q5: codes come from a known list."""
    unknown = sorted(set(df[column].dropna()) - set(allowed))
    if unknown:
        return f"allowed values: {column} has unexpected {unknown}"
    return None
