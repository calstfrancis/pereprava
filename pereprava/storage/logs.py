"""Read the tail of a job's log file."""

from __future__ import annotations

from pathlib import Path


def tail_log(path: str, lines: int = 500) -> str:
    p = Path(path)
    if not p.exists():
        return "(no log yet — this job hasn't run)"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"(could not read log: {exc})"
    all_lines = text.splitlines()
    return "\n".join(all_lines[-lines:])
