"""The feed itself. These tests do not depend on --target."""

import csv

from week1.data import generate as gen


def read(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def test_committed_raw_file_matches_the_seed():
    assert read(gen.RAW_PATH) == gen.generate(gen.SEED), (
        "week1/data/raw/transactions.csv is out of date; run python week1/data/generate.py"
    )


def test_feed_has_the_promised_mess():
    header, *rows = gen.generate()
    assert "legacy_branch_code" in header  # extra column
    ids = [r[0] for r in rows]
    assert len(ids) - len(set(ids)) == gen.N_DUPLICATES  # duplicates
    assert sum(r[1] in gen.BAD_DATES for r in rows) == len(gen.BAD_DATES)  # bad dates
    assert sum(r[3] == "" for r in rows) == gen.N_NULL_AMOUNTS  # nulls
    assert any(r[4] != r[4].strip().upper() for r in rows)  # mixed-case codes


def test_break_modes_change_what_they_say():
    normal = gen.generate()
    assert gen.generate(break_mode="rename")[0][1] == "transaction_date"
    assert any(r[1] == "06/03/2026" for r in gen.generate(break_mode="date-format"))
    late = gen.generate(break_mode="late")
    assert len(late) < len(normal) and not any(r[1] == "2026-03-06" for r in late)
