"""Browse rclone remotes directly via the API (lsjson), never through a FUSE mount."""

from __future__ import annotations

import json
import subprocess

_TIMEOUT = 20


def list_remotes() -> list[str]:
    """Return configured remote names, e.g. ["pcloud:"]."""
    try:
        result = subprocess.run(
            ["rclone", "listremotes"], capture_output=True, text=True, timeout=_TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def list_dirs(remote: str, path: str) -> list[str]:
    """List subfolder names under remote:path (dirs only), sorted."""
    target = f"{remote}{path}"
    try:
        result = subprocess.run(
            ["rclone", "lsjson", target, "--dirs-only"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    try:
        entries = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return sorted(entry["Name"] for entry in entries if "Name" in entry)
