"""Part 1 solution: CSV -> clean -> DuckDB."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

CONTRACT_COLUMNS = ["txn_id", "txn_date", "account_id", "amount", "currency", "merchant_category"]
TABLE = "transactions"


def extract(csv_path: Path) -> pd.DataFrame:
    """Read the raw file exactly as delivered: every column as text, nothing guessed."""
    return pd.read_csv(csv_path, dtype=str, keep_default_na=False)


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn the raw feed into one trustworthy row per transaction."""
    df = raw.copy()

    # Step 1: tidy the headers and keep only the columns we agreed on.
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[CONTRACT_COLUMNS].copy()

    # Step 2: trim whitespace and normalise currency codes to upper case.
    for col in CONTRACT_COLUMNS:
        df[col] = df[col].str.strip()
    df["currency"] = df["currency"].str.upper()

    # Step 3: parse dates with an explicit format and amounts as numbers.
    # Anything that does not fit becomes NaT/NaN instead of being guessed.
    df["txn_date"] = pd.to_datetime(df["txn_date"], format="%Y-%m-%d", errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Step 4: drop rows we cannot use, then de-duplicate on the business key.
    df = df.dropna(subset=["txn_date", "amount"])
    df = df.drop_duplicates(subset="txn_id", keep="first")

    return df.reset_index(drop=True)


def load(df: pd.DataFrame, db_path: Path, table: str = TABLE) -> int:
    """Replace the table with this batch and return its row count.

    CREATE OR REPLACE makes the load idempotent: run it twice, get the same table.
    """
    con = duckdb.connect(str(db_path))
    try:
        con.register("clean_batch", df)
        # Step 5: one statement, so a rerun replaces instead of appending.
        con.execute(
            f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT
                txn_id,
                CAST(txn_date AS DATE)          AS txn_date,
                account_id,
                CAST(amount AS DECIMAL(12, 2))  AS amount,
                currency,
                merchant_category
            FROM clean_batch
            """
        )
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        con.close()
