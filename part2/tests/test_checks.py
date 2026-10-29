"""Tests for Part 2 reconciliation checks, contract validation, and alert formatting."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import pytest

from part2.card import validate_card


def _clean_silver_and_dlq(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    transform = target_pkg["transform"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, dlq_df = ingest.route_poison_pills(raw_df, route_to_dlq=True)
    dedup_df, dropped = ingest.deduplicate_retries(valid_df, drop_duplicates=True)
    windowed_df = ingest.assign_settlement_window(dedup_df, window_mode="event_time", watermark_minutes=180)
    silver_df = transform.compute_fx_and_fees(windowed_df, fx_bug=False)
    return silver_df, dlq_df, dropped


@pytest.mark.warmup
def test_pipeline_card_is_complete(target_pkg):
    errors = validate_card(target_pkg["card"])
    assert errors == [], f"pipeline_card.yaml has validation errors: {errors}"


@pytest.mark.core
def test_all_checks_pass_on_clean_silver(target_pkg, raw_csv_path: Path):
    checks = target_pkg["checks"]
    silver_df, dlq_df, dropped = _clean_silver_and_dlq(target_pkg, raw_csv_path)
    problems = checks.run_all_checks(
        silver_df,
        dlq_df,
        raw_count=600,
        duplicates_dropped=dropped,
        card=target_pkg["card"],
    )
    assert problems == []


@pytest.mark.core
def test_check_row_conservation_catches_silent_drop(target_pkg):
    checks = target_pkg["checks"]
    assert checks.check_row_conservation(600, 555, 30, 15) is None
    msg = checks.check_row_conservation(600, 537, 30, 15)
    assert msg is not None and "18 unrecorded row drop" in msg


@pytest.mark.core
def test_check_unique_txn_id_catches_duplicate_retries(target_pkg, raw_csv_path: Path):
    checks = target_pkg["checks"]
    silver_df, _, _ = _clean_silver_and_dlq(target_pkg, raw_csv_path)
    assert checks.check_unique_txn_id(silver_df) is None

    with_dups = pd.concat([silver_df, silver_df.iloc[:5]], ignore_index=True)
    msg = checks.check_unique_txn_id(with_dups)
    assert msg is not None and "5 duplicate retry" in msg


@pytest.mark.core
def test_check_settlement_cutoff_catches_arrival_time_misbooking(target_pkg, raw_csv_path: Path):
    checks = target_pkg["checks"]
    silver_df, _, _ = _clean_silver_and_dlq(target_pkg, raw_csv_path)
    assert checks.check_settlement_cutoff(silver_df) is None

    misbooked = silver_df.copy()
    misbooked.loc[misbooked["is_late_arrival"], "settlement_date"] = misbooked.loc[
        misbooked["is_late_arrival"], "arrived_date"
    ]
    msg = checks.check_settlement_cutoff(misbooked)
    assert msg is not None and "45 late-arriving" in msg


@pytest.mark.core
def test_check_watermark_lag_catches_stalled_queue(target_pkg, raw_csv_path: Path):
    checks = target_pkg["checks"]
    silver_df, _, _ = _clean_silver_and_dlq(target_pkg, raw_csv_path)
    assert checks.check_watermark_lag(silver_df, max_watermark_minutes=180) is None

    stalled = silver_df.copy()
    stalled.loc[stalled.index[:4], "lag_minutes"] = 245.0
    msg = checks.check_watermark_lag(stalled, max_watermark_minutes=180)
    assert msg is not None and "4 event(s) exceeded" in msg


@pytest.mark.core
def test_check_fx_and_amounts_catches_corrupted_fx(target_pkg, raw_csv_path: Path):
    checks = target_pkg["checks"]
    transform = target_pkg["transform"]
    silver_df, _, _ = _clean_silver_and_dlq(target_pkg, raw_csv_path)
    assert checks.check_fx_and_amounts(silver_df) is None

    buggy_df = transform.compute_fx_and_fees(silver_df, fx_bug=True)
    msg = checks.check_fx_and_amounts(buggy_df)
    assert msg is not None and "160 row(s)" in msg


@pytest.mark.core
def test_check_quarantine_routed_catches_leaked_poison_pills(target_pkg, raw_csv_path: Path):
    checks = target_pkg["checks"]
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    leaked_df, empty_dlq = ingest.route_poison_pills(raw_df, route_to_dlq=False)
    msg = checks.check_quarantine_routed(leaked_df, empty_dlq)
    assert msg is not None and "15 malformed" in msg


@pytest.mark.core
def test_alerts_format_page_and_quarantine_notice(target_pkg):
    alerts = target_pkg["alerts"]
    card = target_pkg["card"]
    page = alerts.format_page(card, ["fx_amount: 160 rows corrupted"])
    assert "PAGE ->" in page and "payment_settlement" in page and "fx_amount" in page

    notice = alerts.format_quarantine_notice(card, 15)
    assert "QUARANTINE ->" in notice and "15 malformed" in notice and "quarantine_dlq" in notice
