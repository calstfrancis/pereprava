"""Thin subprocess wrappers around `systemctl --user` and friends."""

from __future__ import annotations

import json
import subprocess

_TIMEOUT = 10


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT)


def daemon_reload() -> None:
    _run(["systemctl", "--user", "daemon-reload"])


def enable_now(unit: str) -> subprocess.CompletedProcess:
    return _run(["systemctl", "--user", "enable", "--now", unit])


def disable_now(unit: str) -> subprocess.CompletedProcess:
    return _run(["systemctl", "--user", "disable", "--now", unit])


def start_now(unit: str) -> subprocess.CompletedProcess:
    # --no-block: return immediately rather than waiting for a oneshot job to
    # finish (which can take minutes for a large rclone/rsync transfer) — this
    # call happens on the GTK main thread via a button click.
    return _run(["systemctl", "--user", "start", "--no-block", unit])


def show_properties(unit: str, props: list[str]) -> dict[str, str]:
    result = _run(
        ["systemctl", "--user", "show", unit, "-p", ",".join(props)]
    )
    parsed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            parsed[key] = value
    return parsed


def list_timers_json(pattern: str) -> list[dict]:
    result = _run(
        ["systemctl", "--user", "list-timers", pattern, "--all", "--output=json"]
    )
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []


def list_units_json(pattern: str) -> list[dict]:
    result = _run(
        [
            "systemctl",
            "--user",
            "list-units",
            pattern,
            "--all",
            "--output=json",
            "--no-legend",
        ]
    )
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
