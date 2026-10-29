"""Deterministic generator for Part 2's payment event feed.

Produces 600 payment events across a midnight settlement cutoff (2026-10-25 -> 2026-10-26):
  - 555 unique valid card & ACH events (including 45 late-arriving pre-midnight swipes
    that arrive after 00:00 UTC, and 142 multi-currency / fee-sensitive rows)
  - 30 gateway duplicate retries (same txn_id delivered twice after an ACK timeout)
  - 15 poison-pill / malformed payloads (8 missing account_id, 7 corrupt payload tokens)

Re-running this script always writes the exact same bytes.
"""
from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
RAW_PATH = Path(__file__).resolve().parent / "raw" / "payment_events.csv"

CURRENCIES = [
    ("USD", 1.0000),
    ("EUR", 1.0800),
    ("GBP", 1.2700),
    ("CAD", 0.7400),
]
RAILS = [
    ("CARD", 150),  # 150 bps = 1.50% interchange fee
    ("ACH", 25),    # 25 bps  = 0.25% clearing fee
]
MERCHANTS = [
    "M-NORTHSTAR-AIR",
    "M-HARBOR-GROCERY",
    "M-APEX-CLOUD",
    "M-METRO-TRANSIT",
    "M-VERDANT-POWER",
    "M-SUMMIT-HOTEL",
]
FIELDS = [
    "event_seq",
    "txn_id",
    "account_id",
    "merchant_id",
    "rail",
    "amount",
    "currency",
    "fx_rate_to_usd",
    "fee_bps",
    "event_time",
    "arrived_at",
    "payload_status",
]


def generate(out_path: Path = RAW_PATH) -> Path:
    rng = random.Random(SEED)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    valid_rows: list[dict[str, str]] = []

    # 1. 255 on-time events on 2026-10-25 (event_time and arrived_at both on 2026-10-25)
    base_day1 = datetime(2026, 10, 25, 8, 0, 0)
    for i in range(1, 256):
        ev_time = base_day1 + timedelta(seconds=i * 180 + rng.randint(0, 40))
        lag_sec = rng.randint(4, 180)
        arr_time = ev_time + timedelta(seconds=lag_sec)
        curr, fx = CURRENCIES[0] if i % 4 != 0 else CURRENCIES[(i // 4) % 3 + 1]
        rail, fee_bps = RAILS[0] if i % 3 != 0 else RAILS[1]
        amt = round(rng.uniform(18.0, 95.0) if rail == "CARD" else rng.uniform(110.0, 640.0), 2)
        valid_rows.append({
            "txn_id": f"TXN-20261025-{i:04d}",
            "account_id": f"ACC-{1001 + (i % 90):04d}",
            "merchant_id": MERCHANTS[i % len(MERCHANTS)],
            "rail": rail,
            "amount": f"{amt:.2f}",
            "currency": curr,
            "fx_rate_to_usd": f"{fx:.4f}",
            "fee_bps": str(fee_bps),
            "event_time": ev_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "arrived_at": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload_status": "VALID",
        })

    # 2. 45 late-arriving events: swiped on 2026-10-25 before midnight, arrived on 2026-10-26 after midnight
    late_base = datetime(2026, 10, 25, 23, 35, 0)
    for j in range(1, 46):
        idx = 255 + j
        ev_time = late_base + timedelta(seconds=j * 30 + rng.randint(0, 8))
        # Arrives on 2026-10-26 between 00:02:00 and 01:35:00 (lag 15 to 115 minutes, within 180m watermark)
        arr_time = datetime(2026, 10, 26, 0, 2, 0) + timedelta(seconds=j * 115 + rng.randint(0, 25))
        curr, fx = CURRENCIES[j % len(CURRENCIES)]
        rail, fee_bps = ("CARD", 150)
        amt = round(rng.uniform(22.0, 120.0), 2)
        valid_rows.append({
            "txn_id": f"TXN-20261025-{idx:04d}",
            "account_id": f"ACC-{1001 + (idx % 90):04d}",
            "merchant_id": MERCHANTS[idx % len(MERCHANTS)],
            "rail": rail,
            "amount": f"{amt:.2f}",
            "currency": curr,
            "fx_rate_to_usd": f"{fx:.4f}",
            "fee_bps": str(fee_bps),
            "event_time": ev_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "arrived_at": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload_status": "VALID",
        })

    # 3. 255 on-time events on 2026-10-26 (event_time and arrived_at both on 2026-10-26)
    base_day2 = datetime(2026, 10, 26, 0, 15, 0)
    for k in range(1, 256):
        ev_time = base_day2 + timedelta(seconds=k * 175 + rng.randint(0, 35))
        lag_sec = rng.randint(3, 150)
        arr_time = ev_time + timedelta(seconds=lag_sec)
        curr, fx = CURRENCIES[0] if k % 4 != 0 else CURRENCIES[(k // 4) % 3 + 1]
        rail, fee_bps = RAILS[0] if k % 3 != 0 else RAILS[1]
        amt = round(rng.uniform(19.0, 115.0) if rail == "CARD" else rng.uniform(125.0, 720.0), 2)
        valid_rows.append({
            "txn_id": f"TXN-20261026-{k:04d}",
            "account_id": f"ACC-{1001 + (k % 90):04d}",
            "merchant_id": MERCHANTS[k % len(MERCHANTS)],
            "rail": rail,
            "amount": f"{amt:.2f}",
            "currency": curr,
            "fx_rate_to_usd": f"{fx:.4f}",
            "fee_bps": str(fee_bps),
            "event_time": ev_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "arrived_at": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload_status": "VALID",
        })

    # 4. 30 gateway duplicate retries (same txn_id sent again 5-12 seconds later when ACK timed out)
    retry_rows: list[dict[str, str]] = []
    for r_idx in range(30):
        src = dict(valid_rows[r_idx * 15])
        orig_arr = datetime.strptime(src["arrived_at"], "%Y-%m-%dT%H:%M:%SZ")
        retry_arr = orig_arr + timedelta(seconds=5 + (r_idx % 8))
        src["arrived_at"] = retry_arr.strftime("%Y-%m-%dT%H:%M:%SZ")
        retry_rows.append(src)

    # 5. 15 poison-pill / malformed payloads (8 missing account_id, 7 corrupt unparseable amount/payload)
    poison_rows: list[dict[str, str]] = []
    for p_idx in range(1, 16):
        ev_time = datetime(2026, 10, 26, 1, 0, 0) + timedelta(minutes=p_idx * 12)
        arr_time = ev_time + timedelta(seconds=9)
        if p_idx <= 8:
            poison_rows.append({
                "txn_id": f"TXN-POISON-{p_idx:03d}",
                "account_id": "",
                "merchant_id": MERCHANTS[p_idx % len(MERCHANTS)],
                "rail": "CARD",
                "amount": "49.95",
                "currency": "USD",
                "fx_rate_to_usd": "1.0000",
                "fee_bps": "150",
                "event_time": ev_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "arrived_at": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "payload_status": "MISSING_ACCOUNT",
            })
        else:
            poison_rows.append({
                "txn_id": f"TXN-POISON-{p_idx:03d}",
                "account_id": f"ACC-{1050 + p_idx:04d}",
                "merchant_id": MERCHANTS[p_idx % len(MERCHANTS)],
                "rail": "CARD",
                "amount": "CORRUPT_PAYLOAD",
                "currency": "USD",
                "fx_rate_to_usd": "1.0000",
                "fee_bps": "150",
                "event_time": ev_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "arrived_at": arr_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "payload_status": "CORRUPT_JSON",
            })

    all_rows = valid_rows + retry_rows + poison_rows
    # Sort by arrived_at so the raw feed reflects physical arrival order at the ingestion gateway
    all_rows.sort(key=lambda r: (r["arrived_at"], r["txn_id"]))

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for seq, row in enumerate(all_rows, 1):
            row_out = {"event_seq": f"EV-{seq:04d}", **row}
            writer.writerow(row_out)

    return out_path


if __name__ == "__main__":
    p = generate()
    print(f"wrote {p}")
