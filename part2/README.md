# Track I · Part 2: Batches, Streams & Screams

**The exercise:** build an event-time watermarked ELT payments pipeline that lands immutable raw events into `bronze_payments`, routes malformed poison pills to a dead-letter quarantine table, deduplicates gateway retries, transforms multi-currency amounts in DuckDB SQL into `silver_payments` and `gold_daily_settlement`, and proves instant replayability when an FX/interchange bug hits production.

**Time:** about 25 minutes for the main path (exercise, break, fix, replay).

**You need:** Python 3.10+ and the packages in [`requirements.txt`](../requirements.txt). No cloud account, no Kafka cluster, no network. Set up once from the repo root ([quickstart](../README.md#quickstart)), then run every command below from the repo root.

```bash
python part2/run.py
```

That runs the finished ELT + event-time watermark solution end to end and verifies instant replay from `bronze_payments`.

---

## Five questions before you pick streaming or ETL

The Part 2 article closes with five questions to answer before you wire up a stream processor or overwrite raw payloads during ingestion. Each one maps directly to code you can inspect, break, and fix in this folder.

| Question | Where it lives in this exercise |
|---|---|
| 1. What is the real freshness SLA, and who acts on it? | `freshness.sla_tier` in [`pipeline_card.yaml`](starter/pipeline_card.yaml) |
| 2. Are you windowing by `event_time` or `arrived_at`? | `ingest_events(..., window_mode="event_time")` in `ingest.py` and `check_settlement_date_alignment` in `checks.py` |
| 3. Can your sink survive at-least-once duplicate retries? | `deduplicate_retries()` in `ingest.py` and `check_unique_txn_id` in `checks.py` |
| 4. Where do malformed poison-pill payloads go? | `dlq_quarantine` routing in `ingest_events()` and `check_row_conservation` (`raw = silver + duplicates_dropped + quarantined_dlq`) |
| 5. When a transform bug ships, can you replay from immutable raw? | `land_bronze()` + `transform_elt_from_bronze()` in `transform.py` vs destructive `run_etl_transform_before_load()` |

<p align="center">
  <img src="../assets/part2-batches-streams-checklist.png" alt="Before you pick streaming or ETL: five questions" width="420">
</p>

## Architecture & data flow

```
payment_events.csv (600 raw events across 00:00 UTC cutoff)
   |
   +--> land_bronze() ---------> DuckDB: bronze_payments (600 immutable raw rows)
   |
   +--> ingest_events() -------> DuckDB: dlq_quarantine (15 poison-pill rows)
          |                      (30 gateway retry duplicates dropped idempotently)
          v
   event-time watermark (180m) + DuckDB SQL ELT transform
          |
          +--> check gate (conservation, unique txn_id, event_time date, watermark lag, positive FX)
          |      |
          |      +-- any check fails? --> STOP before publish; previous silver_payments stays intact
          v
   DuckDB: silver_payments (555 clean rows) & gold_daily_settlement (2026-10-25: 300, 2026-10-26: 255)
```

<p align="center">
  <img src="../assets/part2-architecture.gif" alt="Part 2 Architecture: Bronze Landing, Quarantine DLQ, Event-Time Watermark & Dedup, Silver DuckDB SQL & Instant Replay" width="760">
</p>

---

## Walkthrough commands

### 1. Run the clean ELT + event-time watermark pipeline

```bash
python part2/run.py --fresh
```

Expected output ends with:

```text
LOADED: 555 rows | bronze preserved (600 raw) | 0 unrecorded drops | replay verified
```

### 2. Compare destructive ETL vs replayable ELT when a bug ships

In **ETL mode** (`--mode etl-bug`), a planted FX/interchange bug (`fx_rate` divided instead of multiplied and `$25.00` subtracted per non-USD row) runs *before* loading into DuckDB and discards the raw payload. The check gate stops the corrupted table, and the raw payload is gone forever:

```bash
python part2/run.py --mode etl-bug
```

In **ELT mode** (`--mode elt-replay`), all 600 raw events land untouched in `bronze_payments` first. Even after the buggy transform runs, fixing the SQL rule and replaying from `bronze_payments` rebuilds all 555 clean `silver_payments` rows in milliseconds:

```bash
python part2/run.py --mode elt-replay
```

<p align="center">
  <img src="../assets/part2-walkthrough.gif" alt="Live VS Code and terminal walkthrough of Part 2 environment setup, code traversal, ELT replay, and check gate" width="760">
</p>


### 3. Break it on purpose (six failure modes)

First load a clean baseline, then trigger each failure mode and watch the check gate stop the bad batch while keeping the 555 clean rows in `silver_payments` untouched:

```bash
python part2/run.py --fresh
python part2/run.py --break arrival-time-cut   # 45 pre-midnight swipes misbooked into 2026-10-26
python part2/run.py --break duplicate-retry    # 30 gateway retry duplicates double-counted
python part2/run.py --break etl-fx-bug         # FX/interchange bug produces negative net_amount_usd
python part2/run.py --break watermark-stall    # 360-minute mobile queue lag exceeds 180m watermark
python part2/run.py --break poison-pill        # malformed payload crashes unguarded parser
python part2/run.py --break silent-drop        # 18 rows dropped without DLQ record breaks conservation
```

### 4. Build it yourself in `part2/starter/`

Run against `starter/` to see the 11 structured `TODO`s:

```bash
python part2/run.py --target starter
```

 Implement `part2/starter/pipeline_card.yaml`, `ingest.py`, `transform.py`, `checks.py`, and `alerts.py`, then verify with pytest:

```bash
python part2/run.py --check --target starter
```

---

## Planted problems in `part2/data/raw/payment_events.csv`

Generated deterministically by `part2/data/generate.py` (`SEED = 42`). All accounts, merchants, and amounts are made up:

- **600 raw events** spanning the `2026-10-25` → `2026-10-26` midnight UTC settlement cutoff.
- **45 late-arriving events:** swiped before `2026-10-25T23:59:59Z` (`event_time`), delivered after `2026-10-26T00:00:00Z` (`arrived_at`) within the 180-minute watermark window. Naive arrival-time batching books only `255` rows on `2026-10-25` instead of `300`.
- **30 gateway duplicate retries:** identical `txn_id` sent a second time after an ACK timeout (`is_retry=1`).
- **15 poison-pill rows:** `8` rows missing `account_id` and `7` rows with corrupt amount strings (`CORRUPT_PAYLOAD`, `NaN_ERR`, `<<BROKEN_JSON>>`).
- **160 multi-currency rows (`CAD`, `EUR`, `GBP`):** exposed when the planted FX/interchange fee bug runs.
