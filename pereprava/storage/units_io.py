"""Write/remove the generated systemd unit files for a job."""

from __future__ import annotations

from pathlib import Path

from pereprava.logic.units import render_service_unit, render_timer_unit, unit_basename
from pereprava.model.job import Job, JobType

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"


def service_path(slug: str) -> Path:
    return SYSTEMD_USER_DIR / f"{unit_basename(slug)}.service"


def timer_path(slug: str) -> Path:
    return SYSTEMD_USER_DIR / f"{unit_basename(slug)}.timer"


def write_units(job: Job) -> None:
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    service_path(job.slug).write_text(render_service_unit(job), encoding="utf-8")
    if job.job_type == JobType.RCLONE_MOUNT:
        # Persistent mounts run off their service's own [Install] section —
        # no timer, so make sure a stale one from an earlier edit doesn't linger.
        timer_path(job.slug).unlink(missing_ok=True)
    else:
        timer_path(job.slug).write_text(render_timer_unit(job), encoding="utf-8")


def remove_units(slug: str) -> None:
    service_path(slug).unlink(missing_ok=True)
    timer_path(slug).unlink(missing_ok=True)


def units_exist(job: Job) -> bool:
    if job.job_type == JobType.RCLONE_MOUNT:
        return service_path(job.slug).exists()
    return service_path(job.slug).exists() and timer_path(job.slug).exists()
