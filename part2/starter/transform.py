"""Transformation & Replay stage for Part 2: Batches, Streams & Screams (Starter).

Complete the TODOs below to land raw payloads in `bronze_payments`, transform into `silver_payments`
and `gold_daily_settlement`, and support instant replay from Bronze.
"""
from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd


def compute_fx_and_fees(df: pd.DataFrame, *, fx_bug: bool = False) -> pd.DataFrame:
    # TODO(part2-transform-1): Compute `amount_usd = round(amount * fx_rate_to_usd, 2)`,
    # `fee_usd = round(amount_usd * (fee_bps / 10000.0), 2)`, and `net_amount_usd = round(amount_usd - fee_usd, 2)`.
    raise NotImplementedError("TODO(part2-transform-1): implement compute_fx_and_fees in part2/starter/transform.py")


def land_bronze(
    con: duckdb.DuckDBPyConnection,
    valid_df: pd.DataFrame,
    dlq_df: pd.DataFrame,
    *,
    bronze_table: str = "bronze_payments",
    quarantine_table: str = "quarantine_dlq",
) -> dict[str, int]:
    # TODO(part2-transform-2): Persist immutable raw `valid_df` into `bronze_payments` and `dlq_df` into `quarantine_dlq`.
    raise NotImplementedError("TODO(part2-transform-2): implement land_bronze in part2/starter/transform.py")


def transform_elt_sql(
    con: duckdb.DuckDBPyConnection,
    *,
    bronze_table: str = "bronze_payments",
    silver_table: str = "silver_payments",
    gold_table: str = "gold_daily_settlement",
    fx_bug: bool = False,
) -> pd.DataFrame:
    # TODO(part2-transform-3): Build `silver_payments` and `gold_daily_settlement` from `bronze_payments` using DuckDB SQL.
    raise NotImplementedError("TODO(part2-transform-3): implement transform_elt_sql in part2/starter/transform.py")


def run_etl_without_bronze(
    con: duckdb.DuckDBPyConnection,
    valid_df: pd.DataFrame,
    *,
    silver_table: str = "silver_payments",
    fx_bug: bool = True,
) -> pd.DataFrame:
    # TODO(part2-transform-4): Simulate classic ETL (transform before load without landing `bronze_payments`).
    raise NotImplementedError("TODO(part2-transform-4): implement run_etl_without_bronze in part2/starter/transform.py")


def replay_silver_from_bronze(
    con: duckdb.DuckDBPyConnection,
    *,
    bronze_table: str = "bronze_payments",
    silver_table: str = "silver_payments",
    gold_table: str = "gold_daily_settlement",
) -> dict[str, Any]:
    # TODO(part2-transform-5): Rebuild `silver_payments` and `gold_daily_settlement` from `bronze_payments`.
    raise NotImplementedError("TODO(part2-transform-5): implement replay_silver_from_bronze in part2/starter/transform.py")
