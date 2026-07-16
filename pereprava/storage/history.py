"""Persist a per-job run history: when each run finished, how long it took,
and whether it succeeded — sourced from systemd's own ExecMainStartTimestamp/
ExecMainExitTimestamp (see logic/status.py), not by parsing log text, since
rclone/rsync's own log format isn't a stable contract to parse against.

Deliberately not tracked for mount jobs — a mount doesn't have discrete
"runs" the way a periodic job does."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pereprava.model.status import JobStatus, RunState

HISTORY_DIR = Path.home() / ".local" / "share" / "pereprava" / "history"
MAX_ENTRIES = 50


def _history_path(slug: str) -> Path:
    return HISTORY_DIR / f"{slug}.json"


def load_history(slug: str) -> list[dict]:
    """Most-recent-first list of {started_at, result, duration_seconds}."""
    try:
        return json.loads(_history_path(slug).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(slug: str, entries: list[dict]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    _history_path(slug).write_text(json.dumps(entries, indent=2), encoding="utf-8")


def record_if_new(slug: str, status: JobStatus) -> None:
    """Append a history entry if `status.last_run` is a run we haven't recorded
    yet for this job. Safe to call on every poll — a no-op once a run's
    already been recorded."""
    if status.state == RunState.SKIPPED:
        return  # a Run Condition skip isn't a run — nothing actually executed
    if status.last_run is None or status.last_result is None:
        return  # never run yet, or still running with no result to record
    started_at = status.last_run.isoformat()
    history = load_history(slug)
    if history and history[0].get("started_at") == started_at:
        return
    history.insert(
        0,
        {
            "started_at": started_at,
            "result": status.last_result,
            "duration_seconds": status.last_run_duration_seconds,
        },
    )
    _save_history(slug, history[:MAX_ENTRIES])


def delete_history(slug: str) -> None:
    _history_path(slug).unlink(missing_ok=True)


def parse_started_at(entry: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(entry["started_at"])
    except (KeyError, ValueError):
        return None
