"""Ingestion stage for Part 2: Batches, Streams & Screams (Solution).

Handles:
1. Routing malformed / poison-pill payloads to a dead-letter quarantine table (DLQ).
2. Idempotent deduplication of gateway retry events by `txn_id`.
3. Event-time windowing with a watermark vs. naive arrival-time batching across a midnight cutoff.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_raw_events(csv_path: Path) -> pd.DataFrame:
    """Load the raw payment event feed preserving string tokens for inspection."""
    return pd.read_csv(csv_path, dtype=str, keep_default_na=False)


def route_poison_pills(
    raw_df: pd.DataFrame,
    *,
    route_to_dlq: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separate malformed / missing-account poison pills from valid payment events.

    When `route_to_dlq=True`, bad payloads are routed to `dlq_df` with a `quarantine_reason`.
    When `route_to_dlq=False` (used by `--break poison-pill`), poison pills leak into `valid_df`.
    """
    df = raw_df.copy()
    missing_acct = df["account_id"].str.strip() == ""
    parsed_amt = pd.to_numeric(df["amount"], errors="coerce")
    bad_amt = parsed_amt.isna() | (parsed_amt <= 0)
    is_poison = missing_acct | bad_amt | (df["payload_status"] != "VALID")

    reasons: list[str] = []
    for idx in df.index:
        if missing_acct.loc[idx]:
            reasons.append("missing_account_id")
        elif bad_amt.loc[idx]:
            reasons.append("corrupt_amount_payload")
        elif df.loc[idx, "payload_status"] != "VALID":
            reasons.append(df.loc[idx, "payload_status"].lower())
        else:
            reasons.append("")
    df["quarantine_reason"] = reasons

    if not route_to_dlq:
        # Fault injection: let poison pills leak into the main stream with coerced 0.0 amount
        leaked = df.copy()
        leaked["amount"] = pd.to_numeric(leaked["amount"], errors="coerce").fillna(0.0)
        leaked["fx_rate_to_usd"] = pd.to_numeric(leaked["fx_rate_to_usd"], errors="coerce").fillna(1.0)
        leaked["fee_bps"] = pd.to_numeric(leaked["fee_bps"], errors="coerce").fillna(0).astype(int)
        empty_dlq = df.iloc[0:0].copy()
        return leaked.reset_index(drop=True), empty_dlq.reset_index(drop=True)

    dlq_df = df[is_poison].copy().reset_index(drop=True)
    valid_df = df[~is_poison].copy().reset_index(drop=True)
    valid_df["amount"] = pd.to_numeric(valid_df["amount"], errors="raise").astype(float)
    valid_df["fx_rate_to_usd"] = pd.to_numeric(valid_df["fx_rate_to_usd"], errors="raise").astype(float)
    valid_df["fee_bps"] = pd.to_numeric(valid_df["fee_bps"], errors="raise").astype(int)
    return valid_df, dlq_df


def deduplicate_retries(
    df: pd.DataFrame,
    *,
    drop_duplicates: bool = True,
) -> tuple[pd.DataFrame, int]:
    """Idempotent deduplication of gateway retry deliveries by `txn_id`.

    Keeps the earliest arrival (`arrived_at`, then `event_seq`) for each `txn_id`.
    """
    ordered = df.sort_values(["arrived_at", "event_seq"], kind="mergesort").reset_index(drop=True)
    if not drop_duplicates:
        return ordered, 0
    before = len(ordered)
    deduped = ordered.drop_duplicates(subset=["txn_id"], keep="first").reset_index(drop=True)
    dropped = before - len(deduped)
    return deduped, dropped


def assign_settlement_window(
    df: pd.DataFrame,
    *,
    window_mode: str = "event_time",
    watermark_minutes: int = 180,
) -> pd.DataFrame:
    """Assign each transaction to its settlement day using event-time or arrival-time windowing.

    - `event_time` mode books every event into the UTC date of `event_time` (when the customer swiped)
      and records `lag_minutes` and `within_watermark`.
    - `arrival_time` mode (naive batch cutoff) books events by `arrived_at` date, which misbooks
      late-arriving pre-midnight swipes into the next day's settlement ledger.
    """
    if window_mode not in ("event_time", "arrival_time"):
        raise ValueError(f"window_mode must be 'event_time' or 'arrival_time', got {window_mode!r}")

    out = df.copy()
    ev_ts = pd.to_datetime(out["event_time"], utc=True)
    arr_ts = pd.to_datetime(out["arrived_at"], utc=True)

    out["event_date"] = ev_ts.dt.strftime("%Y-%m-%d")
    out["arrived_date"] = arr_ts.dt.strftime("%Y-%m-%d")
    out["lag_minutes"] = ((arr_ts - ev_ts).dt.total_seconds() / 60.0).round(2)
    out["is_late_arrival"] = out["event_date"] != out["arrived_date"]
    out["within_watermark"] = out["lag_minutes"] <= float(watermark_minutes)
    out["window_mode"] = window_mode

    if window_mode == "event_time":
        out["settlement_date"] = out["event_date"]
    else:
        out["settlement_date"] = out["arrived_date"]

    return out
