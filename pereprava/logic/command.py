"""Turn a Job into the argv that actually gets executed. No GTK imports."""

from __future__ import annotations

from pereprava.model.job import Job, JobType

RCLONE_BIN = "/usr/bin/rclone"
RSYNC_BIN = "/usr/bin/rsync"


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


def _filter_flags(job: Job) -> list[str]:
    return [*_exclude_flags(job), *_include_flags(job), *_bwlimit_flags(job)]


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
