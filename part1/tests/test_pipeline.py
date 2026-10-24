"""Main exercise: clean() and load()."""

import duckdb
import pandas as pd
import pytest

from .conftest import CLEAN_ROWS

pytestmark = pytest.mark.core

CONTRACT = ["txn_id", "txn_date", "account_id", "amount", "currency", "merchant_category"]


def test_clean_keeps_only_contract_columns(cleaned):
    assert list(cleaned().columns) == CONTRACT  # legacy_branch_code is gone


def test_clean_normalises_currency_codes(cleaned):
    assert set(cleaned()["currency"]) == {"INR", "USD", "EUR", "GBP"}


def test_clean_parses_dates_and_amounts(cleaned):
    df = cleaned()
    assert pd.api.types.is_datetime64_any_dtype(df["txn_date"])
    assert pd.api.types.is_numeric_dtype(df["amount"])
    assert df["txn_date"].notna().all() and df["amount"].notna().all()


def test_clean_removes_duplicates_including_case_variants(cleaned):
    assert cleaned()["txn_id"].is_unique


def test_clean_row_count_is_exact(cleaned):
    assert len(cleaned()) == CLEAN_ROWS


def test_load_writes_typed_table(target, cleaned, tmp_path):
    db = tmp_path / "w.duckdb"
    assert target.pipeline.load(cleaned(), db) == CLEAN_ROWS
    con = duckdb.connect(str(db), read_only=True)
    types = dict(con.execute("SELECT column_name, data_type FROM information_schema.columns "
                             "WHERE table_name = 'transactions'").fetchall())
    con.close()
    assert types["txn_date"] == "DATE"
    assert types["amount"].startswith("DECIMAL")


def test_load_twice_does_not_double_rows(target, cleaned, tmp_path):
    db = tmp_path / "w.duckdb"
    df = cleaned()
    target.pipeline.load(df, db)
    assert target.pipeline.load(df, db) == CLEAN_ROWS
