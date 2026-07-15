"""Read the tail of a job's log file, and keep it from growing unbounded."""

from __future__ import annotations

import os
from pathlib import Path

_MAX_BYTES = 5_000_000
_KEEP_BYTES = 1_000_000


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


def rotate_if_needed(path: str, max_bytes: int = _MAX_BYTES, keep_bytes: int = _KEEP_BYTES) -> None:
    """Shrink a log file in place once it passes max_bytes, keeping the last
    keep_bytes (rounded to a line boundary).

    A mount job's unit restarts on failure every 10s forever and appends to
    this file each time — with no cap it can grow indefinitely if a mount
    keeps flapping. Truncated in place (same inode, not replaced) so a
    running unit's O_APPEND file descriptor stays valid and just keeps
    appending after the new, shorter end of file.
    """
    p = Path(path)
    try:
        size = p.stat().st_size
    except OSError:
        return
    if size <= max_bytes:
        return
    try:
        with open(p, "r+b") as f:
            f.seek(-keep_bytes, os.SEEK_END)
            tail = f.read()
            newline = tail.find(b"\n")
            if newline != -1:
                tail = tail[newline + 1 :]
            f.seek(0)
            f.truncate(0)
            f.write(
                b"(earlier log entries truncated to keep this file from growing unbounded)\n"
            )
            f.write(tail)
    except OSError:
        return
