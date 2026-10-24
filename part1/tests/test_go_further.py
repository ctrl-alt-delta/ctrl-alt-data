"""Go further: schema contract, allowed values, and a real alert hook."""

import json

import pytest

from part1.runner import run_pipeline

from .conftest import AS_OF

pytestmark = pytest.mark.further

CONTRACT = ["txn_id", "txn_date", "account_id", "amount", "currency", "merchant_category"]


def test_schema_check_names_the_missing_column(target, feed):
    raw = target.pipeline.extract(feed("rename"))
    message = target.checks.check_schema(list(raw.columns), CONTRACT)
    assert message and "txn_date" in message
    assert target.checks.check_schema(list(target.pipeline.extract(feed()).columns), CONTRACT) is None


def test_schema_check_ignores_header_case_and_spaces(target):
    assert target.checks.check_schema([" TXN_ID", *CONTRACT[1:]], CONTRACT) is None


def test_renamed_column_fails_on_the_contract_not_a_crash(target, feed, tmp_path):
    result = run_pipeline(target, feed("rename"), tmp_path / "w.duckdb", AS_OF, tmp_path)
    assert result.status == "stopped"
    assert any("txn_date" in f and "crashed" not in f for f in result.failures), result.failures


def test_allowed_values_check(target, cleaned):
    df = cleaned()
    allowed = ["INR", "USD", "EUR", "GBP"]
    assert target.checks.check_allowed_values(df, "currency", allowed) is None
    df.loc[0, "currency"] = "XYZ"
    message = target.checks.check_allowed_values(df, "currency", allowed)
    assert message and "XYZ" in message


def test_alert_hook_pages_the_on_call_from_the_card(target, tmp_path):
    card = target.card
    alert = target.alerts.notify(card, ["row count: 1 clean rows, expected at least 450"], tmp_path)
    log = tmp_path / "alerts.log"
    assert log.exists(), "notify() should append a line to workdir/alerts.log"
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert line["to"] == card["on_call"]["primary"]
    assert line["failures"] and line["pipeline"] == card["name"]
    assert alert == line or alert["to"] == line["to"]
