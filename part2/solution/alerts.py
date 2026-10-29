"""Actionable alert and quarantine notice formatters for Part 2 (Solution)."""
from __future__ import annotations

from typing import Any


def format_page(card: dict[str, Any], problems: list[str]) -> str:
    """Format an actionable on-call page naming the owner, pipeline, failed checks, and policy."""
    owner = card.get("owner", "unknown-owner")
    name = card.get("name", "unknown-pipeline")
    policy = card.get("bad_run_policy", "keep_last_good")
    tables = card.get("tables", {})
    silver = tables.get("silver", "silver_payments") if isinstance(tables, dict) else "silver_payments"

    lines = [
        f"PAGE -> {owner}: pipeline '{name}' failed {len(problems)} check(s) [policy={policy}, target={silver}]"
    ]
    for p in problems:
        lines.append(f"  - {p}")
    return "\n".join(lines)


def format_quarantine_notice(card: dict[str, Any], dlq_count: int) -> str:
    """Format a structured notice when poison-pill rows are safely isolated in `quarantine_dlq`."""
    owner = card.get("owner", "unknown-owner")
    tables = card.get("tables", {})
    q_table = tables.get("quarantine", "quarantine_dlq") if isinstance(tables, dict) else "quarantine_dlq"
    return (
        f"QUARANTINE -> {owner}: {dlq_count} malformed event(s) isolated in '{q_table}' "
        "(stream continued without crashing)"
    )
