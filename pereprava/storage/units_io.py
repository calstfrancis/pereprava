"""Write/remove the generated systemd unit files for a job."""

from __future__ import annotations

from pathlib import Path

from pereprava.logic.units import render_service_unit, render_timer_unit, unit_basename
from pereprava.model.job import Job

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"


def service_path(slug: str) -> Path:
    return SYSTEMD_USER_DIR / f"{unit_basename(slug)}.service"


def timer_path(slug: str) -> Path:
    return SYSTEMD_USER_DIR / f"{unit_basename(slug)}.timer"


def write_units(job: Job) -> None:
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    service_path(job.slug).write_text(render_service_unit(job), encoding="utf-8")
    timer_path(job.slug).write_text(render_timer_unit(job), encoding="utf-8")


def remove_units(slug: str) -> None:
    service_path(slug).unlink(missing_ok=True)
    timer_path(slug).unlink(missing_ok=True)


def units_exist(slug: str) -> bool:
    return service_path(slug).exists() and timer_path(slug).exists()
