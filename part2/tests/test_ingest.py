"""Tests for Part 2 ingestion: poison-pill DLQ routing, idempotent retry dedup, and event-time windowing."""
from __future__ import annotations

from pathlib import Path

import pytest

from part2.data.generate import generate


@pytest.mark.warmup
def test_deterministic_generator_counts(tmp_path: Path):
    p1 = generate(tmp_path / "one.csv")
    p2 = generate(tmp_path / "two.csv")
    assert p1.read_bytes() == p2.read_bytes()
    lines = p1.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 601  # 1 header + 600 payment events


@pytest.mark.core
def test_route_poison_pills_separates_15_malformed_rows(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    assert len(raw_df) == 600

    valid_df, dlq_df = ingest.route_poison_pills(raw_df, route_to_dlq=True)
    assert len(valid_df) == 585
    assert len(dlq_df) == 15
    assert set(dlq_df["quarantine_reason"].unique()) == {"missing_account_id", "corrupt_amount_payload"}
    assert (valid_df["account_id"].str.strip() != "").all()
    assert (valid_df["amount"] > 0).all()


@pytest.mark.core
def test_route_poison_pills_disabled_leaks_rows_into_stream(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    leaked_df, dlq_df = ingest.route_poison_pills(raw_df, route_to_dlq=False)
    assert len(leaked_df) == 600
    assert len(dlq_df) == 0


@pytest.mark.core
def test_deduplicate_retries_is_idempotent_and_keeps_earliest_arrival(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, _ = ingest.route_poison_pills(raw_df, route_to_dlq=True)

    dedup_1, dropped_1 = ingest.deduplicate_retries(valid_df, drop_duplicates=True)
    assert len(dedup_1) == 555
    assert dropped_1 == 30
    assert dedup_1["txn_id"].is_unique

    # Running deduplication a second time is a no-op (idempotent)
    dedup_2, dropped_2 = ingest.deduplicate_retries(dedup_1, drop_duplicates=True)
    assert len(dedup_2) == 555
    assert dropped_2 == 0


@pytest.mark.core
def test_deduplicate_retries_disabled_retains_duplicates(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, _ = ingest.route_poison_pills(raw_df, route_to_dlq=True)

    kept_df, dropped = ingest.deduplicate_retries(valid_df, drop_duplicates=False)
    assert len(kept_df) == 585
    assert dropped == 0
    assert int(kept_df["txn_id"].duplicated().sum()) == 30


@pytest.mark.core
def test_event_time_window_books_45_late_arrivals_into_true_settlement_day(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, _ = ingest.route_poison_pills(raw_df, route_to_dlq=True)
    dedup_df, _ = ingest.deduplicate_retries(valid_df, drop_duplicates=True)

    ev_df = ingest.assign_settlement_window(dedup_df, window_mode="event_time", watermark_minutes=180)
    assert int(ev_df["is_late_arrival"].sum()) == 45
    assert bool(ev_df["within_watermark"].all())
    by_day = ev_df["settlement_date"].value_counts().to_dict()
    assert by_day == {"2026-10-25": 300, "2026-10-26": 255}


@pytest.mark.core
def test_arrival_time_window_misbooks_45_late_events_across_midnight(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, _ = ingest.route_poison_pills(raw_df, route_to_dlq=True)
    dedup_df, _ = ingest.deduplicate_retries(valid_df, drop_duplicates=True)

    arr_df = ingest.assign_settlement_window(dedup_df, window_mode="arrival_time", watermark_minutes=180)
    by_day = arr_df["settlement_date"].value_counts().to_dict()
    # All 45 pre-midnight swipes that arrived after 00:00 UTC are misbooked into 2026-10-26
    assert by_day == {"2026-10-25": 255, "2026-10-26": 300}
    assert int((arr_df["settlement_date"] != arr_df["event_date"]).sum()) == 45


@pytest.mark.core
def test_invalid_window_mode_raises_value_error(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, _ = ingest.route_poison_pills(raw_df, route_to_dlq=True)
    with pytest.raises(ValueError):
        ingest.assign_settlement_window(valid_df, window_mode="invalid_mode")
