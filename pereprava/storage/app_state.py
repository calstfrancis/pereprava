"""Track state that isn't a job — currently just which version's changelog
the user has already seen, so the app can pop "What's New" once after an
update instead of only showing it on demand via the version button."""

from __future__ import annotations

import json
from pathlib import Path

STATE_PATH = Path.home() / ".config" / "pereprava" / "state.json"


def get_last_seen_version() -> str | None:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data.get("last_seen_version")


def set_last_seen_version(version: str) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"last_seen_version": version}), encoding="utf-8")
