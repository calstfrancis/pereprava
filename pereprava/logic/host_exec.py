"""Run host binaries that don't live inside the flatpak sandbox.

Pereprava is distributed both as a plain venv install (install.sh) and as a
flatpak. `systemctl`, `systemd-analyze`, `loginctl`, `rclone`, and `rsync`
aren't part of org.gnome.Platform, and systemd itself is a host daemon
regardless of the GUI's sandbox — so every call to one of them is routed
through `flatpak-spawn --host`, which asks the Flatpak portal to run it as a
real host process. Outside a sandbox this prefix is simply omitted, so the
same code path serves both distributions. See the finish-args comment in
io.github.calstfrancis.pereprava.yml for the corresponding permission.

This only covers commands launched directly by the GUI process (remote
browsing, dry-run "Test", systemctl calls, binary discovery). A job's actual
ExecStart always runs as a normal host process via systemd, outside the
sandbox entirely — that part needs no wrapping at all.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

IS_FLATPAK = os.path.exists("/.flatpak-info")


def host_argv(argv: list[str]) -> list[str]:
    """Prefix argv with flatpak-spawn --host when running sandboxed."""
    if IS_FLATPAK:
        return ["flatpak-spawn", "--host", *argv]
    return list(argv)


def which(name: str, timeout: float = 5) -> str | None:
    """shutil.which, but resolved against the host's PATH when sandboxed."""
    if not IS_FLATPAK:
        return shutil.which(name)
    try:
        result = subprocess.run(
            host_argv(["which", name]), capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def host_file_exists(path: Path, timeout: float = 5) -> bool:
    """path.is_file(), but checked against the host's filesystem when
    sandboxed — used for the non-PATH fallback binary locations in
    logic/command.py, which live outside the --filesystem=home grant."""
    if not IS_FLATPAK:
        return path.is_file()
    try:
        result = subprocess.run(
            host_argv(["test", "-f", str(path)]), timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0
