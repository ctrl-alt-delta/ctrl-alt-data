"""Generate the synthetic Week 1 transactions feed.

Everything here is made up: random account ids, random amounts, a fictional
"partner payments" feed. No real customer, bank or company data.

The output is fully determined by SEED. Only ``random.Random.random()`` is used,
because that is the one method Python guarantees to reproduce for a given seed
across versions, so the sample CSV is the same on every machine.

Usage:
    python week1/data/generate.py                 # rewrite data/sample/transactions.csv
    python week1/data/generate.py --break late    # print a broken feed to stdout
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = 20260302
BUSINESS_DAYS = [date(2026, 3, 2) + timedelta(days=i) for i in range(5)]  # Mon..Fri
ROWS_PER_DAY = 100
HEADER = [
    "txn_id",
    "txn_date",
    "account_id",
    "amount",
    "currency",
    "merchant_category",
    "legacy_branch_code",  # the extra column nobody asked for
]
CURRENCIES = ["INR", "INR", "INR", "USD", "EUR", "GBP"]
CATEGORIES = ["grocery", "fuel", "travel", "dining", "utilities", "online"]
BAD_DATES = ["2026-02-30", "N/A", "", "2026-03-32", "unknown", "2026-13-01"]
N_NULL_AMOUNTS = 8
N_DUPLICATES = 15
BREAK_MODES = ("rename", "date-format", "late")

SAMPLE_PATH = Path(__file__).resolve().parent / "sample" / "transactions.csv"


def _pick(rng: random.Random, seq):
    return seq[int(rng.random() * len(seq))]


def _shuffled(rng: random.Random, items: list) -> list:
    items = list(items)
    for i in range(len(items) - 1, 0, -1):  # Fisher-Yates using random() only
        j = int(rng.random() * (i + 1))
        items[i], items[j] = items[j], items[i]
    return items


def _messy_currency(rng: random.Random, code: str) -> str:
    roll = rng.random()
    if roll < 0.15:
        return code.lower()
    if roll < 0.25:
        return code.title()
    if roll < 0.32:
        return f" {code} "
    return code


def generate(seed: int = SEED, break_mode: str | None = None) -> list[list[str]]:
    """Return the feed as a list of rows, header first."""
    if break_mode not in (None, *BREAK_MODES):
        raise ValueError(f"unknown break mode {break_mode!r}; choose from {BREAK_MODES}")
    rng = random.Random(seed)

    rows: list[list[str]] = []
    for i in range(len(BUSINESS_DAYS) * ROWS_PER_DAY):
        day = BUSINESS_DAYS[i // ROWS_PER_DAY]
        rows.append(
            [
                f"T{i + 1:05d}",
                day.isoformat(),
                f"ACC-{1000 + int(rng.random() * 9000)}",
                f"{5 + rng.random() * 495:.2f}",
                _messy_currency(rng, _pick(rng, CURRENCIES)),
                _pick(rng, CATEGORIES),
                f"BR-{int(rng.random() * 90) + 10:03d}" if rng.random() < 0.1 else "",
            ]
        )

    # Pick disjoint rows for each kind of mess.
    order = _shuffled(rng, range(len(rows)))
    bad_date_idx = order[: len(BAD_DATES)]
    null_amount_idx = order[len(BAD_DATES) : len(BAD_DATES) + N_NULL_AMOUNTS]
    dup_source_idx = order[len(BAD_DATES) + N_NULL_AMOUNTS :][:N_DUPLICATES]

    for idx, bad in zip(bad_date_idx, BAD_DATES):
        rows[idx][1] = bad
    for idx in null_amount_idx:
        rows[idx][3] = ""

    # Duplicates: the same transaction delivered twice. Some copies differ only
    # in currency casing, so a naive "drop exact duplicates" misses them.
    # Copies are made first and inserted from the bottom up, so inserting one
    # never shifts the position of a row we still have to copy.
    copies = []
    for n, idx in enumerate(sorted(dup_source_idx)):
        copy = list(rows[idx])
        if n % 2:
            copy[4] = copy[4].strip().lower()
        copies.append((idx + 1 + int(rng.random() * 20), copy))
    for insert_at, copy in sorted(copies, key=lambda pair: pair[0], reverse=True):
        rows.insert(min(insert_at, len(rows)), copy)

    header = list(HEADER)
    if break_mode == "rename":
        # Upstream "tidied up" a column name without telling anyone.
        header[1] = "transaction_date"
    elif break_mode == "date-format":
        # Upstream switched to DD/MM/YYYY for the two most recent days.
        recent = {d.isoformat(): d for d in BUSINESS_DAYS[-2:]}
        for row in rows:
            if row[1] in recent:
                row[1] = recent[row[1]].strftime("%d/%m/%Y")
    elif break_mode == "late":
        # The feed landed on time, but Friday's rows never made it in.
        last = BUSINESS_DAYS[-1].isoformat()
        rows = [row for row in rows if row[1] != last]

    return [header, *rows]


def to_csv_text(rows: list[list[str]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def write_csv(path: Path, seed: int = SEED, break_mode: str | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(to_csv_text(generate(seed, break_mode)))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--break", dest="break_mode", choices=BREAK_MODES)
    parser.add_argument("--out", type=Path, help="write here instead of the default")
    args = parser.parse_args(argv)
    if args.break_mode and not args.out:
        sys.stdout.write(to_csv_text(generate(args.seed, args.break_mode)))
        return 0
    out = write_csv(args.out or SAMPLE_PATH, args.seed, args.break_mode)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
