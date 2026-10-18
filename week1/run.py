"""Week 1 quickstart: one command to run, break, query and test the pipeline.

    python week1/run.py                              run the solution on a clean feed
    python week1/run.py --target starter             run YOUR code (week1/starter/)
    python week1/run.py --break date-format          simulate an upstream change
    python week1/run.py --sql "SELECT count(*) FROM transactions"
    python week1/run.py --check --target starter     run the tests against your code

Works the same on macOS, Linux and Windows. Needs no network.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

WEEK_DIR = Path(__file__).resolve().parent
REPO_DIR = WEEK_DIR.parent
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from week1.data.generate import BREAK_MODES, write_csv  # noqa: E402
from week1.runner import TARGETS, load_target, run_pipeline, table_count  # noqa: E402

# The exercise runs on a pinned "today" so everyone sees the same numbers.
# In production this would be date.today().
DEFAULT_AS_OF = "2026-03-07"
STAGES = ("warmup", "core", "fix", "further")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python week1/run.py",
        description="CTRL+ALT+DATA week 1: CSV -> clean -> checks -> DuckDB",
    )
    p.add_argument("--target", choices=TARGETS, default="solution", help="whose code to run (default: solution)")
    p.add_argument("--break", dest="break_mode", choices=BREAK_MODES, help="simulate an upstream change")
    p.add_argument("--as-of", default=DEFAULT_AS_OF, help=f"the pipeline's 'today' (default: {DEFAULT_AS_OF})")
    p.add_argument("--workdir", type=Path, help="where the landing file, DuckDB file and alerts.log go")
    p.add_argument("--fresh", action="store_true", help="delete the workdir first")
    p.add_argument("--sql", help="run one SQL query against the warehouse and exit")
    p.add_argument("--check", action="store_true", help="run the pytest suite for --target and exit")
    p.add_argument("--stage", choices=STAGES, help="with --check: only the tests for one stage")
    return p.parse_args(argv)


def run_tests(target: str, stage: str | None) -> int:
    cmd = [sys.executable, "-m", "pytest", str(WEEK_DIR), "--target", target, "-q"]
    if stage:
        cmd += ["-m", stage]
    print("running: python", " ".join(cmd[1:]), flush=True)
    return subprocess.call(cmd, cwd=REPO_DIR)


def run_sql(db_path: Path, query: str) -> int:
    import duckdb

    if not db_path.exists():
        print(f"No warehouse at {db_path} yet. Run the pipeline first.")
        return 1
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        # to_string keeps the output plain ASCII, which every terminal can print
        print(con.sql(query).df().to_string(index=False))
    finally:
        con.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workdir = (args.workdir or WEEK_DIR / ".work" / args.target).resolve()
    db_path = workdir / "warehouse.duckdb"

    if args.check:
        return run_tests(args.target, args.stage)
    if args.sql:
        return run_sql(db_path, args.sql)

    if args.fresh and workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    as_of = date.fromisoformat(args.as_of)
    landing = write_csv(workdir / "landing" / "transactions.csv", break_mode=args.break_mode)

    print(f"CTRL+ALT+DATA week 1 | target={args.target} | feed={args.break_mode or 'normal'} | as-of={as_of}")
    target = load_target(args.target)
    before = table_count(db_path)
    try:
        result = run_pipeline(target, landing, db_path, as_of, workdir, echo=print)
    except NotImplementedError as exc:
        print(f"\nNot done yet: {exc}")
        print(f"Open week1/{args.target}/ and look for the TODO comments.")
        return 2

    print("-" * 60)
    if result.latest_date:
        print(f"newest txn_date in this batch: {result.latest_date}")
    if result.status == "stopped":
        kept = f"still {before} rows from the last load" if before is not None else "no table yet"
        print(f"STOPPED: {len(result.failures)} problem(s) found, nothing loaded. Warehouse: {kept}.")
        return 1
    print(f"{result.status.upper()}: {result.rows_loaded} rows in table 'transactions' at {db_path}")
    if result.todo_checks:
        print(f"{len(result.todo_checks)} check(s) are still TODO: {', '.join(result.todo_checks)}")
    return 1 if result.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
