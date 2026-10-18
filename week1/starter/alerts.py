"""Week 1 starter: Q4, who gets paged."""

from __future__ import annotations

from pathlib import Path


def notify(card: dict, failures: list[str], workdir: Path) -> dict | None:
    """Called by the runner whenever a check fails.

    Right now it shouts into the terminal, which pages nobody.

    TODO 10 (go further): page the person the card names. Append one JSON line
    to workdir / "alerts.log" with at least {"to": card["on_call"]["primary"],
    "pipeline": card["name"], "failures": failures}, and return that dict.
    """
    print(f"ALERT: {len(failures)} check(s) failed, but nobody was told.")
    return None
