"""Warm-up: the pipeline card answers all five questions."""

import pytest

from week1.card import find_todos, parse_card

pytestmark = pytest.mark.warmup


def test_card_has_no_todos_left(target):
    todos = find_todos(target.card)
    assert not todos, f"fill these in {target.card_path.name}: {todos}"


def test_card_answers_all_five_questions(target):
    card = target.card
    for section in ("source", "freshness", "on_failure", "on_call", "correctness"):
        assert section in card, f"missing section {section!r}"
    assert card["source"]["owner"], "Q1: who owns the source?"


def test_freshness_and_row_floor_are_numbers(target):
    card = target.card
    assert isinstance(card["freshness"]["max_lag_days"], int), "Q2: max_lag_days should be a whole number"
    assert isinstance(card["correctness"]["min_rows"], int), "Q5: min_rows should be a whole number"
    assert card["correctness"]["min_rows"] > 0


def test_failure_action_is_a_decision(target):
    assert target.card["on_failure"]["action"] in ("stop", "warn"), "Q3: pick stop or warn"


def test_someone_specific_gets_paged(target):
    primary = str(target.card["on_call"]["primary"]).strip().lower()
    assert primary not in ("everyone", "all", "the team", "team", "nobody", "todo", ""), (
        "Q4: if the answer is everyone, it's no one. Name one person or rota."
    )


def test_card_parser_handles_the_subset():
    card = parse_card("a:\n  b: 1  # comment\n  c: [x, y]\n  d: 'quoted # not a comment'\ne: 2.5\n")
    assert card == {"a": {"b": 1, "c": ["x", "y"], "d": "quoted # not a comment"}, "e": 2.5}
