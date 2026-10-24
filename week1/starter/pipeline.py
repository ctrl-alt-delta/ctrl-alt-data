"""Part 1 starter: CSV -> clean -> DuckDB.

Fill in TODO 1-5, then run:
    python week1/run.py --target starter
    python week1/run.py --check --stage core --target starter
"""

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

    # TODO 1: tidy the headers (strip spaces, lower case) and keep only
    #         CONTRACT_COLUMNS. That also drops the extra legacy_branch_code column.
    #         Hint: df.columns = [c.strip().lower() for c in df.columns]

    # TODO 2: strip whitespace from every column, then upper-case `currency`
    #         so " usd", "Usd" and "USD" become one code.
    #         Hint: df[col].str.strip(), df["currency"].str.upper()

    # TODO 3: parse txn_date with an explicit format, and amount as a number.
    #         Values that don't fit should become NaT/NaN, not a guess.
    #         Hint: pd.to_datetime(..., format="%Y-%m-%d", errors="coerce")
    #               pd.to_numeric(..., errors="coerce")

    # TODO 4: drop rows with no txn_date or no amount, then keep one row per
    #         txn_id. Some duplicates only differ in currency casing, which is
    #         why this comes after TODO 2.
    #         Hint: df.dropna(subset=[...]), df.drop_duplicates(subset="txn_id")

    raise NotImplementedError("TODO 1-4: finish clean() in week1/starter/pipeline.py")  # delete me
    return df.reset_index(drop=True)


def load(df: pd.DataFrame, db_path: Path, table: str = TABLE) -> int:
    """Replace the table with this batch and return its row count."""
    con = duckdb.connect(str(db_path))
    try:
        con.register("clean_batch", df)

        # TODO 5: write ONE SQL statement that builds `table` from clean_batch,
        #         with txn_date cast to DATE and amount cast to DECIMAL(12, 2).
        #         Running the pipeline twice must NOT double the rows.
        #         Hint: CREATE OR REPLACE TABLE ... AS SELECT ... FROM clean_batch
        #         con.execute(f"""...""")

        raise NotImplementedError("TODO 5: finish load() in week1/starter/pipeline.py")  # delete me
        return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    finally:
        con.close()
