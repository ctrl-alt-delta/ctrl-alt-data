"""CLI entry point for Part 2: Batches, Streams & Screams.

Examples:
    python part2/run.py                       # run the working ELT + event-time watermark solution
    python part2/run.py --fresh               # wipe local DuckDB first, then run cleanly
    python part2/run.py --mode etl-bug        # see ETL overwrite raw data with a buggy FX rule
    python part2/run.py --mode elt-replay     # see ELT rebuild clean Silver from immutable Bronze
    python part2/run.py --break arrival-time-cut
    python part2/run.py --break duplicate-retry
    python part2/run.py --break etl-fx-bug
    python part2/run.py --break watermark-stall
    python part2/run.py --break poison-pill
    python part2/run.py --break silent-drop
    python part2/run.py --target starter      # run your work-in-progress in part2/starter/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from part2.runner import BREAK_SCENARIOS, DEFAULT_DB, MODES, PART2_DIR, collect_starter_todos, run_pipeline

C_TEAL = "\033[38;2;94;234;212m"
C_SKY = "\033[38;2;186;230;253m"
C_GREEN = "\033[38;2;134;239;172m"
C_RED = "\033[38;2;224;122;107m"
C_AMBER = "\033[38;2;252;211;77m"
C_MUTED = "\033[38;2;148;163;184m"
C_RESET = "\033[0m"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Part 2 event-time watermark + DuckDB ELT settlement pipeline."
    )
    parser.add_argument(
        "--target",
        choices=("solution", "starter"),
        default="solution",
        help="Which implementation to run (default: solution).",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default="elt",
        help="Pipeline architecture mode: 'elt' (default), 'etl-bug', or 'elt-replay'.",
    )
    parser.add_argument(
        "--break",
        dest="break_scenario",
        choices=BREAK_SCENARIOS,
        default=None,
        help="Inject a realistic streaming/batch failure to see the check gate stop it.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Delete part2/warehouse.duckdb before running.",
    )
    args = parser.parse_args(argv)

    if args.fresh and DEFAULT_DB.exists():
        DEFAULT_DB.unlink()

    scenario_label = args.break_scenario or "normal"
    print(
        f"{C_TEAL}CTRL+ALT+DATA part 2{C_RESET} | "
        f"target={C_SKY}{args.target}{C_RESET} | "
        f"mode={C_SKY}{args.mode}{C_RESET} | "
        f"scenario={C_SKY}{scenario_label}{C_RESET}"
    )
    print(f"{C_MUTED}{'-' * 78}{C_RESET}")

    try:
        report = run_pipeline(
            target=args.target,
            mode=args.mode,
            break_scenario=args.break_scenario,
        )
    except NotImplementedError as exc:
        print(f"{C_AMBER}! NOT IMPLEMENTED YET:{C_RESET} {exc}")
        todos = collect_starter_todos(PART2_DIR / args.target)
        if todos:
            print(f"\nRemaining TODOs in part2/{args.target}/ ({len(todos)} items):")
            for item in todos:
                print(item)
        print("\nComplete the TODOs above and re-run `python part2/run.py --target starter`.")
        return 2

    if args.mode == "etl-bug" and args.break_scenario is None:
        print(
            f"ETL RUN (no bronze): wrote {report.silver_count} rows to silver_payments "
            f"with {C_RED}{report.corrupted_rows} corrupted post-FX row(s){C_RESET}."
        )
        print(f"REPLAY ATTEMPT:      {C_RED}✕ FAILED — {report.replay_note}{C_RESET}")
        print(
            f"{C_RED}✕ STOPPED:{C_RESET} ETL discarded raw amounts before loading; historical rows cannot be "
            "repaired from local storage."
        )
        return 1

    if args.mode == "elt-replay" and args.break_scenario is None:
        print(
            f"BRONZE LANDED:  {C_SKY}{report.bronze_count} immutable raw rows{C_RESET} in bronze_payments | "
            f"{C_AMBER}! {report.quarantine_count} poison pills{C_RESET} in quarantine_dlq"
        )
        print(f"ELT REPLAY:     {C_GREEN}✓ {report.replay_note}{C_RESET}")
        if report.quarantine_notice:
            print(f"{C_AMBER}! {report.quarantine_notice}{C_RESET}")
        print(
            f"{C_GREEN}✓ LOADED:{C_RESET} {report.silver_count} rows (2026-10-25: 300 | 2026-10-26: 255) | "
            f"bronze preserved ({report.bronze_count} rows) | "
            f"{report.duplicates_dropped} duplicates dropped | {report.quarantine_count} quarantined | "
            "0 unrecorded drops"
        )
        return 0

    if report.ok:
        print(
            f"INGEST:  {C_SKY}{report.raw_count} raw events -> {report.silver_count} valid{C_RESET} | "
            f"{report.duplicates_dropped} gateway retries dropped | "
            f"{C_AMBER}! {report.quarantine_count} poison pills routed to quarantine_dlq{C_RESET}"
        )
        print(
            f"WINDOW:  event-time watermark booked {C_SKY}{report.late_arrivals_booked} late-arriving "
            f"pre-midnight swipes{C_RESET} into their true settlement date (2026-10-25: 300 | 2026-10-26: 255)"
        )
        if report.quarantine_notice:
            print(f"{C_AMBER}! {report.quarantine_notice}{C_RESET}")
        print(
            f"GATE:    {C_GREEN}✓ 6/6 reconciliation checks PASSED{C_RESET} "
            "(schema, pk_unique, watermark_180m, fx_positive, volume_conservation,cutoff_300_255)"
        )
        print(
            f"{C_GREEN}✓ LOADED:{C_RESET} {report.silver_count} rows | bronze preserved ({report.bronze_count} rows) | "
            "0 unrecorded drops"
        )
        return 0

    print(f"{C_RED}{report.page}{C_RESET}")
    print(
        f"{C_RED}✕ STOPPED:{C_RESET} {len(report.problems)} problem(s) found at check gate. "
        f"Warehouse silver_payments kept at last good state ({C_GREEN}✓ {report.silver_count} rows preserved{C_RESET})."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
