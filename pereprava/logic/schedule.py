"""Schedule presets and OnCalendar= validation."""

from __future__ import annotations

import subprocess

from pereprava.model.job import SCHEDULE_PRESETS

PRESET_LABELS: dict[str, str] = {
    "hourly": "Hourly",
    "every6h": "Every 6 hours",
    "daily": "Daily",
    "weekly": "Weekly",
    "custom": "Custom",
}


def preset_to_on_calendar(preset: str, custom_value: str = "") -> str:
    if preset == "custom":
        return custom_value
    return SCHEDULE_PRESETS[preset]


def validate_on_calendar(value: str) -> tuple[bool, str]:
    """Check an OnCalendar= expression via systemd-analyze. Returns (ok, message).

    `message` holds the next-occurrence preview text on success, or the error
    output from systemd-analyze on failure.
    """
    if not value.strip():
        return False, "Schedule cannot be empty."
    try:
        result = subprocess.run(
            ["systemd-analyze", "calendar", value],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not run systemd-analyze: {exc}"
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or "Invalid schedule."
    return True, result.stdout.strip()
