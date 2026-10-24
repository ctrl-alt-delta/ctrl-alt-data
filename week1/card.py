"""Read pipeline_card.yaml.

The card is plain YAML, but only a small subset of it: nested mappings,
``key: value`` scalars, ``[a, b]`` inline lists and ``#`` comments. This
loader handles exactly that subset so Part 1 needs no YAML library.
In a real project, use PyYAML (``yaml.safe_load``) instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

TODO = "TODO"


def _scalar(text: str) -> Any:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [_scalar(part) for part in inner.split(",")] if inner else []
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return text


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if ch in "'\"":
            quote = None if quote == ch else (quote or ch)
        elif ch == "#" and quote is None and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def parse_card(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, value = line.strip().partition(":")
        if not sep:
            raise ValueError(f"line {lineno}: expected 'key: value', got {raw!r}")
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value.strip():
            parent[key.strip()] = _scalar(value)
        else:
            child: dict = {}
            parent[key.strip()] = child
            stack.append((indent, child))
    return root


def load_card(path: Path) -> dict:
    return parse_card(Path(path).read_text(encoding="utf-8"))


def find_todos(card: dict, prefix: str = "") -> list[str]:
    """Return the dotted paths of every value that is still TODO (or empty)."""
    todos = []
    for key, value in card.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            todos += find_todos(value, dotted + ".") if value else [dotted]
        elif value == "" or (isinstance(value, str) and value.upper().startswith(TODO)):
            todos.append(dotted)
    return todos
