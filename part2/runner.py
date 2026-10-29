"""Orchestrator for Part 2: Batches, Streams & Screams.

Wires together `pipeline_card.yaml`, `ingest.py`, `transform.py`, `checks.py`, and `alerts.py`
for either `part2.solution` or `part2.starter`, and supports:
  - Normal ELT + event-time watermark run
  - `--mode etl-bug` vs `--mode elt-replay` comparison
  - 6 `--break` fault-injection scenarios stopped at the check gate before overwriting `silver_payments`
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from part2.card import load_card, validate_card
from part2.data.generate import RAW_PATH, generate

PART2_DIR = Path(__file__).resolve().parent
DEFAULT_DB = PART2_DIR / "warehouse.duckdb"

BREAK_SCENARIOS = (
    "arrival-time-cut",
    "duplicate-retry",
    "etl-fx-bug",
    "watermark-stall",
    "poison-pill",
    "silent-drop",
)
MODES = ("elt", "etl-bug", "elt-replay")


@dataclass
class RunReport:
    ok: bool
    target: str
    mode: str
    break_scenario: str | None
    raw_count: int = 0
    silver_count: int = 0
    bronze_count: int = 0
    duplicates_dropped: int = 0
    quarantine_count: int = 0
    late_arrivals_booked: int = 0
    corrupted_rows: int = 0
    replayed: bool = False
    replay_elapsed_ms: float = 0.0
    replay_note: str = ""
    problems: list[str] = field(default_factory=list)
    page: str | None = None
    quarantine_notice: str | None = None


def _load_target_modules(target: str):
    pkg = f"part2.{target}"
    ingest = importlib.import_module(f"{pkg}.ingest")
    transform = importlib.import_module(f"{pkg}.transform")
    checks = importlib.import_module(f"{pkg}.checks")
    alerts = importlib.import_module(f"{pkg}.alerts")
    card_path = PART2_DIR / target / "pipeline_card.yaml"
    return ingest, transform, checks, alerts, card_path


def collect_starter_todos(target_dir: Path) -> list[str]:
    """Scan a target folder for remaining TODO markers so `--target starter` lists them clearly."""
    todos: list[str] = []
    for path in sorted(target_dir.glob("*.yaml")) + sorted(target_dir.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if "TODO" in stripped and not stripped.startswith("raise NotImplementedError"):
                todos.append(f"  - {path.name}:{lineno}: {stripped.lstrip('# ').strip()}")
    return todos


def run_pipeline(
    *,
    target: str = "solution",
    mode: str = "elt",
    break_scenario: str | None = None,
    db_path: Path = DEFAULT_DB,
    csv_path: Path = RAW_PATH,
) -> RunReport:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if break_scenario is not None and break_scenario not in BREAK_SCENARIOS:
        raise ValueError(f"break_scenario must be one of {BREAK_SCENARIOS}, got {break_scenario!r}")

    if not csv_path.exists():
        generate(csv_path)

    ingest, transform, checks, alerts, card_path = _load_target_modules(target)
    card = load_card(card_path)
    card_errors = validate_card(card)

    raw_df = ingest.load_raw_events(csv_path)
    raw_count = len(raw_df)

    # 1. Ingestion: poison-pill routing, retry deduplication, and settlement window assignment
    # Calling these before returning card_errors ensures unimplemented starter functions raise NotImplementedError
    route_to_dlq = break_scenario != "poison-pill"
    valid_df, dlq_df = ingest.route_poison_pills(raw_df, route_to_dlq=route_to_dlq)

    drop_dups = break_scenario != "duplicate-retry"
    dedup_df, dups_dropped = ingest.deduplicate_retries(valid_df, drop_duplicates=drop_dups)

    watermark_minutes = int(card.get("watermark_minutes") or 180)
    win_mode = "arrival_time" if break_scenario == "arrival-time-cut" else "event_time"
    windowed_df = ingest.assign_settlement_window(
        dedup_df,
        window_mode=win_mode,
        watermark_minutes=watermark_minutes,
    )

    if card_errors:
        return RunReport(
            ok=False,
            target=target,
            mode=mode,
            break_scenario=break_scenario,
            problems=card_errors,
            page="\n".join(card_errors),
        )

    if break_scenario == "watermark-stall":
        windowed_df = windowed_df.copy()
        stall_idx = windowed_df.index[:12]
        windowed_df.loc[stall_idx, "lag_minutes"] = windowed_df.loc[stall_idx, "lag_minutes"] + 240.0
        windowed_df.loc[stall_idx, "within_watermark"] = False

    # 2. Candidate Silver transform (staged in memory so the check gate runs BEFORE overwriting warehouse tables)
    fx_bug = (break_scenario == "etl-fx-bug") or (mode == "etl-bug")
    candidate_silver = transform.compute_fx_and_fees(windowed_df, fx_bug=fx_bug)

    if break_scenario == "silent-drop":
        candidate_silver = candidate_silver.iloc[:-18].reset_index(drop=True)

    con = duckdb.connect(str(db_path))
    try:
        # Mode: ETL-BUG (shows why transforming before load without Bronze loses raw values)
        if mode == "etl-bug" and break_scenario is None:
            etl_df = transform.run_etl_without_bronze(con, windowed_df, fx_bug=True)
            corrupted = int((etl_df["currency"] != "USD").sum())
            replay_info = transform.replay_silver_from_bronze(con)
            return RunReport(
                ok=False,
                target=target,
                mode=mode,
                break_scenario=None,
                raw_count=raw_count,
                silver_count=len(etl_df),
                bronze_count=0,
                duplicates_dropped=dups_dropped,
                quarantine_count=len(dlq_df),
                late_arrivals_booked=int(etl_df["is_late_arrival"].sum()),
                corrupted_rows=corrupted,
                replayed=bool(replay_info["replayed"]),
                replay_elapsed_ms=float(replay_info["elapsed_ms"]),
                replay_note=str(replay_info["reason"]),
                problems=[
                    f"etl_no_bronze: {corrupted} non-USD rows corrupted by FX/fee bug, and raw amounts were discarded before load",
                    str(replay_info["reason"]),
                ],
            )

        # Mode: ELT-REPLAY (lands Bronze first, runs buggy SQL transform, then replays clean Silver from Bronze)
        if mode == "elt-replay" and break_scenario is None:
            counts = transform.land_bronze(con, windowed_df, dlq_df)
            transform.transform_elt_sql(con, fx_bug=True)
            replay_info = transform.replay_silver_from_bronze(con)
            rebuilt_df = con.execute("SELECT * FROM silver_payments").df()
            problems = checks.run_all_checks(
                rebuilt_df,
                dlq_df,
                raw_count=raw_count,
                duplicates_dropped=dups_dropped,
                card=card,
            )
            q_notice = alerts.format_quarantine_notice(card, len(dlq_df))
            return RunReport(
                ok=len(problems) == 0,
                target=target,
                mode=mode,
                break_scenario=None,
                raw_count=raw_count,
                silver_count=len(rebuilt_df),
                bronze_count=counts["bronze_rows"],
                duplicates_dropped=dups_dropped,
                quarantine_count=counts["quarantine_rows"],
                late_arrivals_booked=int(rebuilt_df["is_late_arrival"].sum()),
                corrupted_rows=0,
                replayed=bool(replay_info["replayed"]),
                replay_elapsed_ms=float(replay_info["elapsed_ms"]),
                replay_note=(
                    f"{replay_info['reason']} (repaired {replay_info.get('corrupted_fixed', 0)} corrupted rows)"
                ),
                problems=problems,
                quarantine_notice=q_notice,
            )

        # 3. Standard ELT + Check Gate (runs on normal run and all `--break` scenarios)
        problems = checks.run_all_checks(
            candidate_silver,
            dlq_df,
            raw_count=raw_count,
            duplicates_dropped=dups_dropped,
            card=card,
        )
        if problems:
            page = alerts.format_page(card, problems)
            existing_tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            existing_silver = (
                int(con.execute("SELECT COUNT(*) FROM silver_payments").fetchone()[0])
                if "silver_payments" in existing_tables
                else 0
            )
            existing_bronze = (
                int(con.execute("SELECT COUNT(*) FROM bronze_payments").fetchone()[0])
                if "bronze_payments" in existing_tables
                else 0
            )
            return RunReport(
                ok=False,
                target=target,
                mode=mode,
                break_scenario=break_scenario,
                raw_count=raw_count,
                silver_count=existing_silver,
                bronze_count=existing_bronze,
                duplicates_dropped=dups_dropped,
                quarantine_count=len(dlq_df),
                problems=problems,
                page=page,
            )

        counts = transform.land_bronze(con, windowed_df, dlq_df)
        silver_df = transform.transform_elt_sql(con, fx_bug=False)
        q_notice = alerts.format_quarantine_notice(card, len(dlq_df))
        return RunReport(
            ok=True,
            target=target,
            mode=mode,
            break_scenario=None,
            raw_count=raw_count,
            silver_count=len(silver_df),
            bronze_count=counts["bronze_rows"],
            duplicates_dropped=dups_dropped,
            quarantine_count=counts["quarantine_rows"],
            late_arrivals_booked=int(silver_df["is_late_arrival"].sum()),
            corrupted_rows=0,
            replayed=False,
            replay_note="Bronze payload table preserved for zero-loss replay",
            problems=[],
            quarantine_notice=q_notice,
        )
    finally:
        con.close()
