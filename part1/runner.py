"""The Part 1 orchestration: extract -> schema check -> clean -> checks -> load.

This file is shared by starter/ and solution/ and is not part of the exercise.
It reads the pipeline card, runs the checks BEFORE loading, and does what the
card says when a check fails (stop, or warn and load anyway).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from types import ModuleType

import duckdb
import pandas as pd

from part1.card import find_todos, load_card

PART_DIR = Path(__file__).resolve().parent
TARGETS = ("solution", "starter")


@dataclass
class Target:
    name: str
    pipeline: ModuleType
    checks: ModuleType
    alerts: ModuleType
    card_path: Path

    @property
    def card(self) -> dict:
        return load_card(self.card_path)


@dataclass
class RunResult:
    status: str  # "loaded", "loaded-with-warnings" or "stopped"
    raw_rows: int = 0
    clean_rows: int | None = None
    rows_loaded: int | None = None
    latest_date: date | None = None
    failures: list[str] = field(default_factory=list)
    todo_checks: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    echo: object = None  # e.g. print, to stream the log as it happens

    def say(self, line: str) -> None:
        self.log.append(line)
        if self.echo:
            self.echo(line)


def load_target(name: str) -> Target:
    if name not in TARGETS:
        raise ValueError(f"target must be one of {TARGETS}, got {name!r}")
    mods = {m: importlib.import_module(f"part1.{name}.{m}") for m in ("pipeline", "checks", "alerts")}
    return Target(name, mods["pipeline"], mods["checks"], mods["alerts"], PART_DIR / name / "pipeline_card.yaml")


def table_count(db_path: Path, table: str = "transactions") -> int | None:
    if not Path(db_path).exists():
        return None
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        exists = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
        ).fetchone()[0]
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] if exists else None
    finally:
        con.close()


def _check(result: RunResult, checks: ModuleType, name: str, *args) -> None:
    fn = getattr(checks, name)
    try:
        message = fn(*args)
    except NotImplementedError:
        result.todo_checks.append(name)
        result.say(f"  TODO  {name} (not written yet, so it can't catch anything)")
        return
    except Exception as exc:  # a crashing check is a failing check
        message = f"{name} could not run: {type(exc).__name__}: {exc}"
    if message:
        result.failures.append(message)
        result.say(f"  FAIL  {message}")
    else:
        result.say(f"  ok    {name}")


def run_pipeline(
    target: Target, csv_path: Path, db_path: Path, as_of: date, workdir: Path, echo=None
) -> RunResult:
    """Run one batch. NotImplementedError from clean()/load() is passed up to the caller."""
    card = target.card
    pipeline, checks = target.pipeline, target.checks
    result = RunResult(status="stopped", echo=echo)

    todos = find_todos(card)
    if todos:
        result.say(f"note  pipeline_card.yaml still has TODO in: {', '.join(todos)}")
    action = card.get("on_failure", {}).get("action", "stop")
    if action not in ("stop", "warn"):
        result.say(f"note  on_failure.action is {action!r}; treating it as 'stop'")
        action = "stop"
    correctness = card.get("correctness", {})

    raw = pipeline.extract(csv_path)
    result.raw_rows = len(raw)
    result.say(f"extract  {len(raw)} raw rows from {csv_path.name}")

    result.say("checks on the raw file")
    _check(result, checks, "check_schema", list(raw.columns), card["source"]["contract_columns"])

    clean = None
    if not result.failures:
        try:
            clean = pipeline.clean(raw)
        except NotImplementedError:
            raise
        except Exception as exc:
            result.failures.append(f"clean() crashed: {type(exc).__name__}: {exc}")
            result.say(f"  FAIL  {result.failures[-1]}")

    if clean is not None:
        result.clean_rows = len(clean)
        if len(clean) and "txn_date" in clean:
            result.latest_date = pd.Timestamp(clean["txn_date"].max()).date()
        result.say(f"clean    {len(clean)} rows kept, {len(raw) - len(clean)} dropped")
        result.say("checks on the clean batch (before anyone sees it)")
        _check(result, checks, "check_row_count", clean, correctness.get("min_rows"))
        _check(result, checks, "check_freshness", clean, as_of, card.get("freshness", {}).get("max_lag_days"))
        _check(result, checks, "check_unique", clean, correctness.get("unique_key", "txn_id"))
        _check(result, checks, "check_not_null", clean, correctness.get("not_null", []))
        _check(result, checks, "check_allowed_values", clean, "currency", correctness.get("allowed_currencies", []))

    if result.failures:
        target.alerts.notify(card, result.failures, workdir)
        if action == "stop" or clean is None:
            result.status = "stopped"
            return result
        result.status = "loaded-with-warnings"
    else:
        result.status = "loaded"

    result.rows_loaded = pipeline.load(clean, db_path)
    result.say(f"load     {result.rows_loaded} rows -> {db_path.name} (table: transactions)")
    return result
