"""Check/enable user lingering, so `systemd --user` mount services can start at
boot without an interactive login (otherwise they only start on first login)."""

from __future__ import annotations

import getpass
import subprocess

_TIMEOUT = 5


def is_enabled() -> bool:
    try:
        result = subprocess.run(
            ["loginctl", "show-user", getpass.getuser(), "-p", "Linger", "--value"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip() == "yes"


def enable() -> bool:
    """Enable lingering for the current user. Returns whether it succeeded."""
    try:
        result = subprocess.run(
            ["loginctl", "enable-linger"], capture_output=True, text=True, timeout=_TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
