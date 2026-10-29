"""End-to-end pipeline & fault-injection tests for Part 2: Batches, Streams & Screams."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from part2.run import main as cli_main
from part2.runner import BREAK_SCENARIOS, run_pipeline


@pytest.mark.core
def test_normal_elt_pipeline_run_commits_555_rows_and_preserves_bronze(target_name: str, tmp_path: Path):
    db_path = tmp_path / "warehouse.duckdb"
    report = run_pipeline(target=target_name, mode="elt", db_path=db_path)

    assert report.ok is True
    assert report.raw_count == 600
    assert report.silver_count == 555
    assert report.bronze_count == 555
    assert report.duplicates_dropped == 30
    assert report.quarantine_count == 15
    assert report.late_arrivals_booked == 45
    assert report.problems == []


@pytest.mark.fix
@pytest.mark.parametrize("scenario", BREAK_SCENARIOS)
def test_every_break_scenario_stops_at_gate_and_preserves_last_good_silver(
    target_name: str,
    scenario: str,
    tmp_path: Path,
):
    db_path = tmp_path / "warehouse.duckdb"
    # 1. Seed a clean baseline in the warehouse
    clean = run_pipeline(target=target_name, mode="elt", db_path=db_path)
    assert clean.ok is True and clean.silver_count == 555

    # 2. Run the fault-injected scenario against the same warehouse
    broken = run_pipeline(
        target=target_name,
        mode="elt",
        break_scenario=scenario,
        db_path=db_path,
    )
    assert broken.ok is False
    assert len(broken.problems) >= 1
    assert broken.page is not None and "PAGE -> data-platform-oncall" in broken.page
    assert broken.silver_count == 555

    # Verify the underlying DuckDB table was never overwritten by the broken run
    con = duckdb.connect(str(db_path))
    try:
        cnt = con.execute("SELECT COUNT(*) FROM silver_payments").fetchone()[0]
        min_net = con.execute("SELECT MIN(net_amount_usd) FROM silver_payments").fetchone()[0]
        assert cnt == 555
        assert min_net > 0
    finally:
        con.close()


@pytest.mark.further
def test_mode_etl_bug_vs_mode_elt_replay_end_to_end(target_name: str, tmp_path: Path):
    etl_db = tmp_path / "etl.duckdb"
    etl_report = run_pipeline(target=target_name, mode="etl-bug", db_path=etl_db)
    assert etl_report.ok is False
    assert etl_report.replayed is False
    assert etl_report.bronze_count == 0
    assert etl_report.corrupted_rows == 160

    elt_db = tmp_path / "elt.duckdb"
    elt_report = run_pipeline(target=target_name, mode="elt-replay", db_path=elt_db)
    assert elt_report.ok is True
    assert elt_report.replayed is True
    assert elt_report.bronze_count == 555
    assert elt_report.silver_count == 555
    assert elt_report.corrupted_rows == 0


@pytest.mark.further
def test_cli_starter_exits_with_code_2():
    code = cli_main(["--target", "starter"])
    assert code == 2
