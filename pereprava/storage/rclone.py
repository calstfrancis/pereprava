"""Browse rclone remotes directly via the API (lsjson), never through a FUSE mount.

Also wraps rclone's own headless OAuth recipe (`rclone authorize` -> `rclone config
create ... token ...`) for guided pCloud remote setup — this is rclone's documented
way to finish an OAuth flow without an interactive `rclone config` session."""

from __future__ import annotations

import json
import re
import subprocess

_TIMEOUT = 20
_AUTHORIZE_TIMEOUT = 300  # generous: waiting on the user to approve in their browser
_TOKEN_RE = re.compile(r"\{.*\}")


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


def start_pcloud_authorize() -> subprocess.Popen:
    """Start `rclone authorize pcloud`. This opens the user's default browser for
    pCloud's OAuth consent screen and blocks until it's approved, then prints a
    JSON token blob to stdout. Caller runs this off the GTK main thread and can
    terminate() the returned process to cancel."""
    return subprocess.Popen(
        ["rclone", "authorize", "pcloud"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def extract_token(authorize_stdout: str) -> str | None:
    """Pull the JSON token blob out of `rclone authorize`'s output."""
    match = _TOKEN_RE.search(authorize_stdout)
    return match.group(0) if match else None


def create_pcloud_remote(name: str, token: str) -> tuple[bool, str]:
    """Finish setup non-interactively with a token from start_pcloud_authorize()."""
    try:
        result = subprocess.run(
            ["rclone", "config", "create", name, "pcloud", "token", token],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not run rclone: {exc}"
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or "rclone config create failed."
    return True, "Remote created."


def obscure_password(password: str) -> tuple[bool, str]:
    """Run `rclone obscure` — rclone config's password fields must be given
    already-obscured when created non-interactively via `config create`."""
    try:
        result = subprocess.run(
            ["rclone", "obscure", password], capture_output=True, text=True, timeout=_TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not run rclone: {exc}"
    if result.returncode != 0:
        return False, result.stderr.strip() or "rclone obscure failed."
    return True, result.stdout.strip()


def create_crypt_remote(
    name: str, wrapped_remote: str, obscured_password: str, obscured_password2: str = ""
) -> tuple[bool, str]:
    """Wrap an existing remote:path in an rclone crypt remote for client-side
    encryption. Passwords must already be obscure_password()'d."""
    args = ["rclone", "config", "create", name, "crypt", "remote", wrapped_remote, "password", obscured_password]
    if obscured_password2:
        args += ["password2", obscured_password2]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Could not run rclone: {exc}"
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or "rclone config create failed."
    return True, "Remote created."


def get_about(remote: str) -> dict | None:
    """`rclone about remote: --json` — total/used/free bytes, or None if the
    backend doesn't support it (some remotes don't) or the call fails."""
    try:
        result = subprocess.run(
            ["rclone", "about", remote, "--json"], capture_output=True, text=True, timeout=_TIMEOUT
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
