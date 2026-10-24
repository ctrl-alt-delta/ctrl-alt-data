"""Part 1 solution: Q4, who gets paged.

A real hook would call your paging or chat tool. This one writes a JSON line
to alerts.log and prints it, which is enough to test and easy to swap out.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def notify(card: dict, failures: list[str], workdir: Path) -> dict:
    alert = {
        "to": card["on_call"]["primary"],
        "escalation": card["on_call"].get("escalation"),
        "pipeline": card["name"],
        "action": card["on_failure"]["action"],
        "failures": failures,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    Path(workdir).mkdir(parents=True, exist_ok=True)
    with (Path(workdir) / "alerts.log").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(alert) + "\n")
    print(f"PAGE -> {alert['to']}: {card['name']} failed {len(failures)} check(s)")
    return alert
