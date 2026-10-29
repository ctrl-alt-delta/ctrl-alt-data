"""Tests for Part 2 transformations: FX/fee math, Bronze landing, ETL data loss vs. ELT replay."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


def _prepared_df(target_pkg, raw_csv_path: Path):
    ingest = target_pkg["ingest"]
    raw_df = ingest.load_raw_events(raw_csv_path)
    valid_df, dlq_df = ingest.route_poison_pills(raw_df, route_to_dlq=True)
    dedup_df, dropped = ingest.deduplicate_retries(valid_df, drop_duplicates=True)
    windowed_df = ingest.assign_settlement_window(dedup_df, window_mode="event_time", watermark_minutes=180)
    return windowed_df, dlq_df, dropped


@pytest.mark.core
def test_clean_compute_fx_and_fees_all_positive(target_pkg, raw_csv_path: Path):
    transform = target_pkg["transform"]
    windowed_df, _, _ = _prepared_df(target_pkg, raw_csv_path)
    clean_df = transform.compute_fx_and_fees(windowed_df, fx_bug=False)

    assert len(clean_df) == 555
    assert (clean_df["amount_usd"] > 0).all()
    assert (clean_df["net_amount_usd"] > 0).all()
    assert (clean_df["net_amount_usd"] < clean_df["amount_usd"]).all()


@pytest.mark.core
def test_buggy_compute_fx_and_fees_corrupts_non_usd_rows(target_pkg, raw_csv_path: Path):
    transform = target_pkg["transform"]
    windowed_df, _, _ = _prepared_df(target_pkg, raw_csv_path)
    buggy_df = transform.compute_fx_and_fees(windowed_df, fx_bug=True)

    non_usd_count = int((buggy_df["currency"] != "USD").sum())
    assert non_usd_count == 160
    assert int((buggy_df["net_amount_usd"] <= 0).sum()) > 100


@pytest.mark.core
def test_land_bronze_and_elt_sql_builds_silver_and_gold(target_pkg, raw_csv_path: Path, tmp_path: Path):
    transform = target_pkg["transform"]
    windowed_df, dlq_df, _ = _prepared_df(target_pkg, raw_csv_path)

    con = duckdb.connect(str(tmp_path / "elt.duckdb"))
    try:
        counts = transform.land_bronze(con, windowed_df, dlq_df)
        assert counts == {"bronze_rows": 555, "quarantine_rows": 15}

        silver_df = transform.transform_elt_sql(con, fx_bug=False)
        assert len(silver_df) == 555
        assert (silver_df["net_amount_usd"] > 0).all()

        gold_df = con.execute("SELECT * FROM gold_daily_settlement ORDER BY settlement_date, rail").df()
        assert len(gold_df) == 4  # 2 dates x 2 rails (ACH, CARD)
        assert int(gold_df["txn_count"].sum()) == 555
        assert int(gold_df["late_arrivals_booked"].sum()) == 45
    finally:
        con.close()


@pytest.mark.fix
def test_etl_without_bronze_loses_raw_and_cannot_replay(target_pkg, raw_csv_path: Path, tmp_path: Path):
    transform = target_pkg["transform"]
    windowed_df, _, _ = _prepared_df(target_pkg, raw_csv_path)

    con = duckdb.connect(str(tmp_path / "etl_loss.duckdb"))
    try:
        etl_df = transform.run_etl_without_bronze(con, windowed_df, fx_bug=True)
        assert len(etl_df) == 555
        assert "amount" not in etl_df.columns
        assert "fx_rate_to_usd" not in etl_df.columns

        replay = transform.replay_silver_from_bronze(con)
        assert replay["replayed"] is False
        assert replay["rows_rebuilt"] == 0
        assert "bronze_payments" in replay["reason"]
    finally:
        con.close()


@pytest.mark.fix
def test_elt_replay_from_bronze_repairs_all_corrupted_rows(target_pkg, raw_csv_path: Path, tmp_path: Path):
    transform = target_pkg["transform"]
    windowed_df, dlq_df, _ = _prepared_df(target_pkg, raw_csv_path)

    con = duckdb.connect(str(tmp_path / "elt_replay.duckdb"))
    try:
        transform.land_bronze(con, windowed_df, dlq_df)
        buggy_silver = transform.transform_elt_sql(con, fx_bug=True)
        assert int((buggy_silver["net_amount_usd"] <= 0).sum()) > 100

        replay = transform.replay_silver_from_bronze(con)
        assert replay["replayed"] is True
        assert replay["rows_rebuilt"] == 555
        assert replay["corrupted_fixed"] == 160

        repaired_silver = con.execute("SELECT * FROM silver_payments").df()
        assert (repaired_silver["net_amount_usd"] > 0).all()
    finally:
        con.close()
