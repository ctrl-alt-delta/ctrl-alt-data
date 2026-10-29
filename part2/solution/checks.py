"""Reconciliation & data-contract checks for Part 2: Batches, Streams & Screams (Solution).

Every check returns `None` when it passes, or a human-readable problem string when it fails.
`run_all_checks` collects every failure so the gate stops bad data before executive reporting.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def check_row_conservation(
    raw_count: int,
    silver_count: int,
    duplicates_dropped: int,
    quarantine_count: int,
) -> str | None:
    """Conservation law: raw_events == silver_loaded + duplicates_dropped + quarantined_dlq."""
    accounted = silver_count + duplicates_dropped + quarantine_count
    if raw_count != accounted:
        diff = raw_count - accounted
        return (
            f"row_conservation: raw_count ({raw_count}) != silver ({silver_count}) + "
            f"duplicates_dropped ({duplicates_dropped}) + quarantined ({quarantine_count}); "
            f"{abs(diff)} unrecorded row drop(s)"
        )
    return None


def check_unique_txn_id(silver_df: pd.DataFrame) -> str | None:
    """Every `txn_id` in `silver_payments` must be unique (gateway retries deduplicated)."""
    dups = int(silver_df["txn_id"].duplicated().sum())
    if dups > 0:
        return f"unique_txn_id: {dups} duplicate retry row(s) leaked into silver_payments"
    return None


def check_settlement_cutoff(silver_df: pd.DataFrame) -> str | None:
    """Every event's `settlement_date` must match its true `event_date` (when the customer swiped)."""
    if "event_date" not in silver_df.columns or "settlement_date" not in silver_df.columns:
        return "settlement_cutoff: missing event_date or settlement_date column"
    misbooked = int((silver_df["settlement_date"] != silver_df["event_date"]).sum())
    if misbooked > 0:
        return (
            f"settlement_cutoff: {misbooked} late-arriving pre-midnight event(s) misbooked into "
            "the wrong settlement date by arrival-time cutoff"
        )
    return None


def check_watermark_lag(silver_df: pd.DataFrame, max_watermark_minutes: int = 180) -> str | None:
    """All ingested events must fall within the watermark window (`lag_minutes <= max_watermark_minutes`)."""
    if "lag_minutes" not in silver_df.columns:
        return "watermark_lag: missing lag_minutes column"
    max_lag = float(silver_df["lag_minutes"].max()) if not silver_df.empty else 0.0
    breached = int((silver_df["lag_minutes"] > float(max_watermark_minutes)).sum())
    if breached > 0:
        return (
            f"watermark_lag: {breached} event(s) exceeded the {max_watermark_minutes}m watermark "
            f"(max lag {max_lag:.1f}m — watermark stalled or upstream queue backed up)"
        )
    return None


def check_fx_and_amounts(silver_df: pd.DataFrame) -> str | None:
    """No negative, zero, or FX-corrupted post-transform amounts in `silver_payments`."""
    if silver_df.empty:
        return "fx_amount: silver_payments is empty"
    non_pos = int(((silver_df["amount_usd"] <= 0) | (silver_df["net_amount_usd"] <= 0)).sum())
    mismatched = 0
    if {"amount", "fx_rate_to_usd", "amount_usd"} <= set(silver_df.columns):
        expected = (silver_df["amount"].astype(float) * silver_df["fx_rate_to_usd"].astype(float)).round(2)
        mismatched = int(((silver_df["amount_usd"].astype(float) - expected).abs() > 0.01).sum())
    bad_total = max(non_pos, mismatched)
    if bad_total > 0:
        return (
            f"fx_amount: {bad_total} row(s) have corrupted or non-positive post-FX amounts "
            f"(non_positive={non_pos}, fx_mismatch={mismatched})"
        )
    return None


def check_quarantine_routed(silver_df: pd.DataFrame, dlq_df: pd.DataFrame) -> str | None:
    """Poison-pill payloads must be routed to `quarantine_dlq`, never into `silver_payments`."""
    missing_acct = int((silver_df["account_id"].astype(str).str.strip() == "").sum())
    bad_status = 0
    if "payload_status" in silver_df.columns:
        bad_status = int((silver_df["payload_status"] != "VALID").sum())
    leaked = max(missing_acct, bad_status)
    if leaked > 0:
        return (
            f"poison_pill_leak: {leaked} malformed / missing-account payload(s) leaked into "
            f"silver_payments instead of quarantine_dlq (dlq_rows={len(dlq_df)})"
        )
    return None


def run_all_checks(
    silver_df: pd.DataFrame,
    dlq_df: pd.DataFrame,
    *,
    raw_count: int,
    duplicates_dropped: int,
    card: dict[str, Any],
) -> list[str]:
    """Run all 6 reconciliation and contract checks and return a list of failure messages."""
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
