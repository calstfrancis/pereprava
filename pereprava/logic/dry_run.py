"""Run a job's command in a mode that touches nothing, so the Add/Edit form can
show the user what would happen before they save. Never executed as a systemd
unit — this is purely for the form's "Test" button.

No fixed timeout: listing a large or deeply-nested remote (a big photo library
on pCloud, say) can legitimately take minutes, and there's no size threshold
that's right for every job. Instead this hands back the Popen so the caller
can run it off the GTK main thread and let the user cancel if it's taking too
long — same shape as the pCloud authorize flow in ui/pcloud_setup.py."""

from __future__ import annotations

import json
import re
import subprocess

from pereprava.logic.command import RCLONE_BIN, build_argv
from pereprava.model.job import Job, JobType

# rclone's own stats footer (always printed at -v, which build_argv always
# sets — see logic/command.py) includes a "Transferred:  N / M" file-count
# line; "0 / 0" is rclone's own stable, long-standing way of saying nothing
# needed transferring. Matched narrowly (only replaces the raw output with
# the friendly fallback when this specific count is confirmed zero) so a
# genuine diff — any other text on this line — always still shows through.
_ZERO_TRANSFER_RE = re.compile(r"Transferred:\s+0\s*[A-Za-z]*\s*/\s*0\b")

_DRY_RUN_SUPPORTED = {
    JobType.RCLONE_COPY,
    JobType.RCLONE_SYNC,
    JobType.RCLONE_BISYNC,
    JobType.RCLONE_CHECK,
    JobType.RSYNC,
}


def unsupported_reason(job: Job) -> str | None:
    """None if a dry run can be started for this job, otherwise why not."""
    if job.job_type == JobType.CUSTOM:
        return "Dry-run isn't supported for custom commands — nothing to safely preview."
    if job.job_type != JobType.RCLONE_MOUNT and job.job_type not in _DRY_RUN_SUPPORTED:
        return f"Dry-run isn't supported for job type: {job.job_type.value}"
    return None


def start_test(job: Job) -> subprocess.Popen:
    """Launch a job's dry run. Caller must have already checked unsupported_reason().
    Runs until it exits naturally or the caller terminate()s it — no timeout."""
    if job.job_type == JobType.RCLONE_MOUNT:
        argv = [RCLONE_BIN, "lsjson", job.source, "--max-depth", "1"]
    elif job.job_type == JobType.RCLONE_CHECK:
        argv = build_argv(job)  # check never writes anything — it IS already a dry run
    else:
        argv = build_argv(job) + ["--dry-run"]
    return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def interpret_result(job: Job, returncode: int, stdout: str, stderr: str) -> tuple[bool, str]:
    if returncode != 0:
        return False, (stderr.strip() or stdout.strip() or "Command failed.")

    if job.job_type == JobType.RCLONE_MOUNT:
        try:
            entries = json.loads(stdout or "[]")
        except json.JSONDecodeError:
            entries = []
        return True, f"Remote is reachable — {len(entries)} item(s) at top level."

    # rclone (with -v) and rsync both write their actual per-file/dry-run
    # notices to stderr, not stdout — stdout is typically empty for these
    # commands. Checking stdout alone meant a real, non-trivial diff still
    # reported the generic "no changes" fallback because nothing was ever
    # looking at the stream the output was actually on.
    output = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    if not output or _ZERO_TRANSFER_RE.search(output):
        return True, "Dry run completed — no changes would be made."
    return True, output
