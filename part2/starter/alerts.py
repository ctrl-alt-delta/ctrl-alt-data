"""Actionable alert and quarantine notice formatters for Part 2 (Starter)."""
from __future__ import annotations

from typing import Any


def format_page(card: dict[str, Any], problems: list[str]) -> str:
    # TODO(part2-alerts-1): Format an actionable page naming owner, pipeline name, policy, and failed checks.
    raise NotImplementedError("TODO(part2-alerts-1): implement format_page in part2/starter/alerts.py")


def format_quarantine_notice(card: dict[str, Any], dlq_count: int) -> str:
    # TODO(part2-alerts-2): Format a quarantine notice naming owner, dlq_count, and quarantine table.
    raise NotImplementedError("TODO(part2-alerts-2): implement format_quarantine_notice in part2/starter/alerts.py")
