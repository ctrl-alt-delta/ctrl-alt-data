"""Reconciliation & data-contract checks for Part 2: Batches, Streams & Screams (Starter)."""
from __future__ import annotations

from typing import Any

import pandas as pd


def check_row_conservation(
    raw_count: int,
    silver_count: int,
    duplicates_dropped: int,
    quarantine_count: int,
) -> str | None:
    # TODO(part2-checks-1): Verify `raw_count == silver_count + duplicates_dropped + quarantine_count`.
    raise NotImplementedError("TODO(part2-checks-1): implement check_row_conservation in part2/starter/checks.py")


def check_unique_txn_id(silver_df: pd.DataFrame) -> str | None:
    # TODO(part2-checks-2): Verify `silver_df['txn_id']` has zero duplicates.
    raise NotImplementedError("TODO(part2-checks-2): implement check_unique_txn_id in part2/starter/checks.py")


def check_settlement_cutoff(silver_df: pd.DataFrame) -> str | None:
    # TODO(part2-checks-3): Verify `settlement_date == event_date` for every row.
    raise NotImplementedError("TODO(part2-checks-3): implement check_settlement_cutoff in part2/starter/checks.py")


def check_watermark_lag(silver_df: pd.DataFrame, max_watermark_minutes: int = 180) -> str | None:
    # TODO(part2-checks-4): Verify no row has `lag_minutes > max_watermark_minutes`.
    raise NotImplementedError("TODO(part2-checks-4): implement check_watermark_lag in part2/starter/checks.py")


def check_fx_and_amounts(silver_df: pd.DataFrame) -> str | None:
    # TODO(part2-checks-5): Verify no negative/zero `amount_usd` or `net_amount_usd` and no FX mismatch.
    raise NotImplementedError("TODO(part2-checks-5): implement check_fx_and_amounts in part2/starter/checks.py")


def check_quarantine_routed(silver_df: pd.DataFrame, dlq_df: pd.DataFrame) -> str | None:
    # TODO(part2-checks-6): Verify zero poison-pill rows leaked into `silver_df`.
    raise NotImplementedError("TODO(part2-checks-6): implement check_quarantine_routed in part2/starter/checks.py")


def run_all_checks(
    silver_df: pd.DataFrame,
    dlq_df: pd.DataFrame,
    *,
    raw_count: int,
    duplicates_dropped: int,
    card: dict[str, Any],
) -> list[str]:
    watermark_minutes = int(card.get("watermark_minutes", 180))
    results = [
        check_quarantine_routed(silver_df, dlq_df),
        check_row_conservation(raw_count, len(silver_df), duplicates_dropped, len(dlq_df)),
        check_unique_txn_id(silver_df),
        check_settlement_cutoff(silver_df),
        check_watermark_lag(silver_df, max_watermark_minutes=watermark_minutes),
        check_fx_and_amounts(silver_df),
    ]
    return [r for r in results if r is not None]
