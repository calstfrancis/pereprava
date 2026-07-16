"""Turn a Job into the argv that actually gets executed. No GTK imports."""

from __future__ import annotations

import shutil
from pathlib import Path

from pereprava.logic.rc import RC_CAPABLE_TYPES
from pereprava.model.job import Job, JobType


def _resolve_bin(name: str, default: str) -> str:
    """Resolve a binary's absolute path at import time rather than hardcoding
    it, since a hardcoded /usr/bin/X silently breaks on any machine where
    it's installed elsewhere — every job referencing it would fail, and for
    periodic (timer-based) jobs specifically, that failure is structurally
    invisible at save time (logic/actions.py's save_and_apply only validates
    that the *timer* enables, never whether the service's ExecStart binary
    actually exists) and only shows up later once the timer fires.

    Checks PATH first, then a few common non-PATH install locations —
    ~/.local/bin especially, since a GUI-launched app (desktop icon/app
    launcher) often sees a more restricted PATH than an interactive
    terminal: a custom install directory added only via a shell rc file
    (.bashrc) is invisible to a desktop session that never sources it, even
    though `which` from a terminal would find it fine. Falls back to the
    historical hardcoded path if nothing is found, matching prior behavior.
    """
    found = shutil.which(name)
    if found:
        return found
    for candidate in (
        Path.home() / ".local" / "bin" / name,
        Path("/usr/local/bin") / name,
        Path("/opt/homebrew/bin") / name,
        Path("/home/linuxbrew/.linuxbrew/bin") / name,
    ):
        if candidate.is_file():
            return str(candidate)
    return default


RCLONE_BIN = _resolve_bin("rclone", "/usr/bin/rclone")
RSYNC_BIN = _resolve_bin("rsync", "/usr/bin/rsync")


def _exclude_flags(job: Job) -> list[str]:
    """`--exclude PATTERN`, repeated — the flag rclone and rsync both accept for
    each exclude pattern (rsync also accepts `--exclude=PATTERN`, but the
    two-token form needs no quoting since it's never shell-parsed here)."""
    flags = []
    for pattern in job.excludes:
        flags += ["--exclude", pattern]
    return flags


def _include_flags(job: Job) -> list[str]:
    """`--include PATTERN`, repeated. Applied after excludes — if you need both
    together, that's the order rclone/rsync see them in, which matters for how
    their filter rules combine (first match wins)."""
    flags = []
    for pattern in job.includes:
        flags += ["--include", pattern]
    return flags


def _bwlimit_flags(job: Job) -> list[str]:
    if not job.bwlimit.strip():
        return []
    return ["--bwlimit", job.bwlimit.strip()]


def _rc_flags(job: Job) -> list[str]:
    """--rc starts rclone's JSON-RPC control server for this run, loopback-only
    and unauthenticated (127.0.0.1 only — never expose this beyond localhost).
    Lets the UI poll real transfer stats for a live progress display instead
    of guessing from log output."""
    if job.rc_port and job.job_type in RC_CAPABLE_TYPES:
        return ["--rc", "--rc-no-auth", "--rc-addr", f"127.0.0.1:{job.rc_port}"]
    return []


def _filter_flags(job: Job) -> list[str]:
    return [*_exclude_flags(job), *_include_flags(job), *_bwlimit_flags(job), *_rc_flags(job)]


def build_argv(job: Job) -> list[str]:
    """Build the full command argv for a job. Pure function — no side effects.

    Transfer commands always get -v: neither rclone nor rsync prints anything
    on a quiet success when not attached to a terminal (which a systemd unit
    never is) — without it, StandardOutput=append:... faithfully captures
    nothing at all, and the log looks "broken" even though the job ran fine.
    Not added for mount: it runs continuously rather than once, and -v there
    means per-file-access noise instead of a one-time transfer summary.
    """
    if job.job_type == JobType.RCLONE_COPY:
        return [RCLONE_BIN, "copy", "-v", job.source, job.destination, *_filter_flags(job), *job.extra_args]
    if job.job_type == JobType.RCLONE_SYNC:
        return [RCLONE_BIN, "sync", "-v", job.source, job.destination, *_filter_flags(job), *job.extra_args]
    if job.job_type == JobType.RCLONE_BISYNC:
        return [RCLONE_BIN, "bisync", "-v", job.source, job.destination, *_filter_flags(job), *job.extra_args]
    if job.job_type == JobType.RCLONE_CHECK:
        return [RCLONE_BIN, "check", "-v", job.source, job.destination, *_filter_flags(job), *job.extra_args]
    if job.job_type == JobType.RSYNC:
        argv = [RSYNC_BIN, "-a", "-v"]
        if job.rsync_delete:
            argv.append("--delete")
        argv += _filter_flags(job)
        argv += [job.source, job.destination, *job.extra_args]
        return argv
    if job.job_type == JobType.CUSTOM:
        return list(job.custom_command or [])
    if job.job_type == JobType.RCLONE_MOUNT:
        return [RCLONE_BIN, "mount", job.source, job.destination, *_filter_flags(job), *job.extra_args]
    raise ValueError(f"Unhandled job type: {job.job_type}")
