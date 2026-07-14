"""Run a job's command in a mode that touches nothing, so the Add/Edit form can
show the user what would happen before they save. Never executed as a systemd
unit — this is purely for the form's "Test" button."""

from __future__ import annotations

import json
import subprocess

from pereprava.logic.command import RCLONE_BIN, build_argv
from pereprava.model.job import Job, JobType

_TIMEOUT = 30

_DRY_RUN_SUPPORTED = {JobType.RCLONE_COPY, JobType.RCLONE_SYNC, JobType.RCLONE_BISYNC, JobType.RSYNC}


def test_job(job: Job) -> tuple[bool, str]:
    """Best-effort dry run. Returns (ok, message) — never raises."""
    if job.job_type == JobType.CUSTOM:
        return False, "Dry-run isn't supported for custom commands — nothing to safely preview."

    if job.job_type == JobType.RCLONE_MOUNT:
        argv = [RCLONE_BIN, "lsjson", job.source, "--max-depth", "1"]
    elif job.job_type in _DRY_RUN_SUPPORTED:
        argv = build_argv(job) + ["--dry-run"]
    else:
        return False, f"Dry-run isn't supported for job type: {job.job_type.value}"

    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {_TIMEOUT}s."
    except OSError as exc:
        return False, f"Could not run: {exc}"

    if result.returncode != 0:
        return False, (result.stderr.strip() or result.stdout.strip() or "Command failed.")

    if job.job_type == JobType.RCLONE_MOUNT:
        try:
            entries = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            entries = []
        return True, f"Remote is reachable — {len(entries)} item(s) at top level."

    output = result.stdout.strip()
    return True, output if output else "Dry run completed — no changes would be made."
