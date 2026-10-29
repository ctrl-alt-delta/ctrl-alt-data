"""Ingestion stage for Part 2: Batches, Streams & Screams (Starter).

Complete the TODOs below so `pytest part2 --target=starter` passes.
Compare with `part2/solution/ingest.py` if you get stuck.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_raw_events(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path, dtype=str, keep_default_na=False)


def route_poison_pills(
    raw_df: pd.DataFrame,
    *,
    route_to_dlq: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    # TODO(part2-ingest-1): Route rows with missing `account_id`, non-numeric/non-positive `amount`,
    # or `payload_status != 'VALID'` into `dlq_df` with a `quarantine_reason` column, and return `(valid_df, dlq_df)`.
    raise NotImplementedError("TODO(part2-ingest-1): implement route_poison_pills in part2/starter/ingest.py")


def deduplicate_retries(
    df: pd.DataFrame,
    *,
    drop_duplicates: bool = True,
) -> tuple[pd.DataFrame, int]:
    # TODO(part2-ingest-2): Sort by `['arrived_at', 'event_seq']` and drop duplicate `txn_id` rows
    # (keeping the first delivery), returning `(deduped_df, duplicates_dropped_count)`.
    raise NotImplementedError("TODO(part2-ingest-2): implement deduplicate_retries in part2/starter/ingest.py")


def assign_settlement_window(
    df: pd.DataFrame,
    *,
    window_mode: str = "event_time",
    watermark_minutes: int = 180,
) -> pd.DataFrame:
    # TODO(part2-ingest-3): Parse `event_time` and `arrived_at` as UTC timestamps, compute `lag_minutes`,
    # `is_late_arrival`, and `within_watermark`, and set `settlement_date` from `event_date` (when
    # `window_mode == 'event_time'`) or `arrived_date` (when `window_mode == 'arrival_time'`).
    raise NotImplementedError("TODO(part2-ingest-3): implement assign_settlement_window in part2/starter/ingest.py")
