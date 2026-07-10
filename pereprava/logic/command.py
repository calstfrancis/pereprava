"""Turn a Job into the argv that actually gets executed. No GTK imports."""

from __future__ import annotations

from pereprava.model.job import Job, JobType

RCLONE_BIN = "/usr/bin/rclone"
RSYNC_BIN = "/usr/bin/rsync"


def build_argv(job: Job) -> list[str]:
    """Build the full command argv for a job. Pure function — no side effects."""
    if job.job_type == JobType.RCLONE_COPY:
        return [RCLONE_BIN, "copy", job.source, job.destination, *job.extra_args]
    if job.job_type == JobType.RCLONE_SYNC:
        return [RCLONE_BIN, "sync", job.source, job.destination, *job.extra_args]
    if job.job_type == JobType.RCLONE_BISYNC:
        return [RCLONE_BIN, "bisync", job.source, job.destination, *job.extra_args]
    if job.job_type == JobType.RSYNC:
        argv = [RSYNC_BIN, "-a"]
        if job.rsync_delete:
            argv.append("--delete")
        argv += [job.source, job.destination, *job.extra_args]
        return argv
    if job.job_type == JobType.CUSTOM:
        return list(job.custom_command or [])
    raise ValueError(f"Unhandled job type: {job.job_type}")
