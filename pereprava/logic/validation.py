"""Validate a Job before it's written to disk. Never trust UI-only checks."""

from __future__ import annotations

from pereprava.logic.schedule import validate_on_calendar
from pereprava.logic.slug import is_valid_slug
from pereprava.model.job import Job, JobType


def validate_job(job: Job, destructive_acknowledged: bool = False) -> list[str]:
    """Return a list of human-readable errors. Empty list means the job is valid."""
    errors: list[str] = []

    if not job.name.strip():
        errors.append("Name cannot be empty.")

    if not is_valid_slug(job.slug):
        errors.append("Internal slug is invalid — this is a bug, please rename the job.")

    if not job.source.strip():
        errors.append("Source cannot be empty.")

    if job.job_type == JobType.CUSTOM:
        if not job.custom_command:
            errors.append("Custom command cannot be empty.")
    else:
        if not job.destination.strip():
            errors.append("Destination cannot be empty.")

    if not job.log_path.strip():
        errors.append("Log path cannot be empty.")

    ok, message = validate_on_calendar(job.schedule.on_calendar)
    if not ok:
        errors.append(f"Invalid schedule: {message}")

    if job.destructive and not destructive_acknowledged:
        errors.append(
            "This job can delete files at the destination — "
            "you must acknowledge this before saving."
        )

    return errors
