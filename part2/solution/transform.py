"""Transformation & Replay stage for Part 2: Batches, Streams & Screams (Solution).

Shows the operational difference between:
- **ETL (Transform-Before-Load):** computes `amount_usd` and `net_amount_usd` in memory and writes only
  the transformed columns into the warehouse (no raw `bronze_payments` table). When a bug in the FX/fee
  calculation corrupts all 160 non-USD rows, the original raw amounts and FX rates are gone from local storage.
- **ELT (Load-Raw-Then-Transform in DuckDB):** lands immutable raw payloads in `bronze_payments` first,
  then derives `silver_payments` and `gold_daily_settlement` via SQL. When the FX/fee bug is fixed,
  replaying from `bronze_payments` restores all 555 rows in milliseconds.
"""
from __future__ import annotations

import time
from typing import Any

import duckdb
import pandas as pd


def compute_fx_and_fees(df: pd.DataFrame, *, fx_bug: bool = False) -> pd.DataFrame:
    """Compute `amount_usd`, `fee_usd`, and `net_amount_usd` in Python.

    When `fx_bug=True`, simulates a realistic production bug where `fee_bps` (basis points, e.g. 150)
    is subtracted as raw dollars (`amount_usd - fee_bps`) on non-USD transactions instead of
    `amount_usd * (fee_bps / 10000.0)`, corrupting all 160 non-USD rows (the CAD/EUR/GBP rows among
    the 555 deduplicated valid events), driving many negative.
    """
    out = df.copy()
    amt = out["amount"].astype(float)
    fx = out["fx_rate_to_usd"].astype(float)
    bps = out["fee_bps"].astype(float)

    amount_usd = (amt * fx).round(2)
    if fx_bug:
        is_non_usd = out["currency"] != "USD"
        fee_usd = (amount_usd * (bps / 10000.0)).round(2)
        # Bug: subtracts fee_bps as whole dollars on non-USD rows and inverts FX
        buggy_net = ((amt / fx) - bps).round(2)
        clean_net = (amount_usd - fee_usd).round(2)
        out["amount_usd"] = amount_usd.where(~is_non_usd, (amt / fx).round(2))
        out["fee_usd"] = fee_usd.where(~is_non_usd, bps.round(2))
        out["net_amount_usd"] = clean_net.where(~is_non_usd, buggy_net)
    else:
        fee_usd = (amount_usd * (bps / 10000.0)).round(2)
        out["amount_usd"] = amount_usd
        out["fee_usd"] = fee_usd
        out["net_amount_usd"] = (amount_usd - fee_usd).round(2)

    return out


def land_bronze(
    con: duckdb.DuckDBPyConnection,
    valid_df: pd.DataFrame,
    dlq_df: pd.DataFrame,
    *,
    bronze_table: str = "bronze_payments",
    quarantine_table: str = "quarantine_dlq",
) -> dict[str, int]:
    """Land immutable raw valid events into `bronze_payments` and poison pills into `quarantine_dlq`."""
    con.register("_tmp_bronze_df", valid_df)
    con.execute(f"CREATE OR REPLACE TABLE {bronze_table} AS SELECT * FROM _tmp_bronze_df")
    con.unregister("_tmp_bronze_df")

    con.register("_tmp_dlq_df", dlq_df)
    con.execute(f"CREATE OR REPLACE TABLE {quarantine_table} AS SELECT * FROM _tmp_dlq_df")
    con.unregister("_tmp_dlq_df")

    b_cnt = con.execute(f"SELECT COUNT(*) FROM {bronze_table}").fetchone()[0]
    q_cnt = con.execute(f"SELECT COUNT(*) FROM {quarantine_table}").fetchone()[0]
    return {"bronze_rows": int(b_cnt), "quarantine_rows": int(q_cnt)}


def transform_elt_sql(
    con: duckdb.DuckDBPyConnection,
    *,
    bronze_table: str = "bronze_payments",
    silver_table: str = "silver_payments",
    gold_table: str = "gold_daily_settlement",
    fx_bug: bool = False,
) -> pd.DataFrame:
    """Transform `bronze_payments` into `silver_payments` and `gold_daily_settlement` using DuckDB SQL."""
    if fx_bug:
        amount_expr = """
            CASE WHEN currency <> 'USD'
                 THEN ROUND(CAST(amount AS DOUBLE) / CAST(fx_rate_to_usd AS DOUBLE), 2)
                 ELSE ROUND(CAST(amount AS DOUBLE) * CAST(fx_rate_to_usd AS DOUBLE), 2)
            END
        """
        fee_expr = """
            CASE WHEN currency <> 'USD'
                 THEN ROUND(CAST(fee_bps AS DOUBLE), 2)
                 ELSE ROUND(ROUND(CAST(amount AS DOUBLE) * CAST(fx_rate_to_usd AS DOUBLE), 2) * (CAST(fee_bps AS DOUBLE) / 10000.0), 2)
            END
        """
    else:
        amount_expr = "ROUND(CAST(amount AS DOUBLE) * CAST(fx_rate_to_usd AS DOUBLE), 2)"
        fee_expr = f"ROUND(({amount_expr}) * (CAST(fee_bps AS DOUBLE) / 10000.0), 2)"

    con.execute(f"""
        CREATE OR REPLACE TABLE {silver_table} AS
        SELECT
            event_seq,
            txn_id,
            account_id,
            merchant_id,
            rail,
            CAST(amount AS DOUBLE) AS amount,
            currency,
            CAST(fx_rate_to_usd AS DOUBLE) AS fx_rate_to_usd,
            CAST(fee_bps AS INTEGER) AS fee_bps,
            {amount_expr} AS amount_usd,
            {fee_expr} AS fee_usd,
            ROUND(({amount_expr}) - ({fee_expr}), 2) AS net_amount_usd,
            event_time,
            arrived_at,
            event_date,
            arrived_date,
            settlement_date,
            CAST(lag_minutes AS DOUBLE) AS lag_minutes,
            CAST(is_late_arrival AS BOOLEAN) AS is_late_arrival,
            CAST(within_watermark AS BOOLEAN) AS within_watermark,
            window_mode,
            payload_status
        FROM {bronze_table}
        ORDER BY event_time, txn_id
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE {gold_table} AS
        SELECT
            settlement_date,
            rail,
            COUNT(*) AS txn_count,
            SUM(CASE WHEN is_late_arrival THEN 1 ELSE 0 END) AS late_arrivals_booked,
            ROUND(SUM(amount_usd), 2) AS gross_usd,
            ROUND(SUM(fee_usd), 2) AS total_fees_usd,
            ROUND(SUM(net_amount_usd), 2) AS net_settlement_usd
        FROM {silver_table}
        GROUP BY settlement_date, rail
        ORDER BY settlement_date, rail
    """)

    return con.execute(f"SELECT * FROM {silver_table}").df()


def run_etl_without_bronze(
    con: duckdb.DuckDBPyConnection,
    valid_df: pd.DataFrame,
    *,
    silver_table: str = "silver_payments",
    fx_bug: bool = True,
) -> pd.DataFrame:
    """Run classic ETL: transform in memory before loading, discarding raw `amount` and `fx_rate_to_usd`.

    Because `bronze_payments` is never created and raw fields are dropped before load, a buggy transform
    permanently loses the raw values in the warehouse.
    """
    con.execute("DROP TABLE IF EXISTS bronze_payments")
    transformed = compute_fx_and_fees(valid_df, fx_bug=fx_bug)
    # ETL overwrites/drops the raw source columns before loading into the target table
    etl_cols = [
        "event_seq",
        "txn_id",
        "account_id",
        "merchant_id",
        "rail",
        "currency",
        "amount_usd",
        "fee_usd",
        "net_amount_usd",
        "event_time",
        "arrived_at",
        "settlement_date",
        "lag_minutes",
        "is_late_arrival",
        "within_watermark",
    ]
    etl_df = transformed[etl_cols].copy()
    con.register("_tmp_etl_df", etl_df)
    con.execute(f"CREATE OR REPLACE TABLE {silver_table} AS SELECT * FROM _tmp_etl_df")
    con.unregister("_tmp_etl_df")
    return con.execute(f"SELECT * FROM {silver_table}").df()


def replay_silver_from_bronze(
    con: duckdb.DuckDBPyConnection,
    *,
    bronze_table: str = "bronze_payments",
    silver_table: str = "silver_payments",
    gold_table: str = "gold_daily_settlement",
) -> dict[str, Any]:
    """Rebuild `silver_payments` and `gold_daily_settlement` from immutable `bronze_payments`."""
    t0 = time.perf_counter()
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if bronze_table not in tables:
        return {
            "replayed": False,
            "rows_rebuilt": 0,
            "elapsed_ms": 0.0,
            "reason": f"'{bronze_table}' does not exist — ETL discarded raw payloads before loading",
        }

    # Count how many rows in current silver were corrupted (negative or mismatched net_amount_usd)
    corrupted_before = 0
    if silver_table in tables:
        corrupted_before = int(
            con.execute(
                f"""
                SELECT COUNT(*)
                FROM {silver_table} s
                JOIN {bronze_table} b USING (txn_id)
                WHERE s.net_amount_usd <= 0
                   OR ABS(s.amount_usd - ROUND(CAST(b.amount AS DOUBLE) * CAST(b.fx_rate_to_usd AS DOUBLE), 2)) > 0.01
                """
            ).fetchone()[0]
        )

    rebuilt_df = transform_elt_sql(
        con,
        bronze_table=bronze_table,
        silver_table=silver_table,
        gold_table=gold_table,
        fx_bug=False,
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    return {
        "replayed": True,
        "rows_rebuilt": len(rebuilt_df),
        "corrupted_fixed": corrupted_before,
        "elapsed_ms": elapsed_ms,
        "reason": f"Rebuilt {len(rebuilt_df)} clean rows from immutable {bronze_table} in {elapsed_ms} ms",
    }
