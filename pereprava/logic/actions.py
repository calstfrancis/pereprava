"""Job mutation actions: every create/edit/delete/toggle goes through here.

Each mutation follows the same order: write JSON -> regenerate units -> daemon-reload.
"""

from __future__ import annotations

from pereprava.logic.units import unit_basename
from pereprava.model.job import Job, JobType
from pereprava.storage import jobs_store, systemctl, units_io


def _managed_unit(job: Job) -> str:
    """The unit systemctl enable/disable/start acts on: the service itself for a
    persistent mount, or the timer for a periodic job (the oneshot service is
    only ever started transiently via run_now)."""
    base = unit_basename(job.slug)
    return f"{base}.service" if job.job_type == JobType.RCLONE_MOUNT else f"{base}.timer"


def save_and_apply(job: Job) -> None:
    """Persist a job's JSON and (re)generate + (re)enable its systemd units."""
    jobs_store.save_job(job)
    units_io.write_units(job)
    systemctl.daemon_reload()
    unit = _managed_unit(job)
    if job.enabled:
        systemctl.enable_now(unit)
    else:
        systemctl.disable_now(unit)


def delete_job_and_units(job: Job) -> None:
    systemctl.disable_now(_managed_unit(job))
    units_io.remove_units(job.slug)
    systemctl.daemon_reload()
    jobs_store.delete_job(job.slug)


def set_enabled(job: Job, enabled: bool) -> None:
    job.enabled = enabled
    save_and_apply(job)


def run_now(slug: str) -> None:
    base = unit_basename(slug)
    systemctl.start_now(f"{base}.service")


def repair_units(job: Job) -> None:
    """Regenerate units for a job whose JSON exists but whose units went missing."""
    save_and_apply(job)


def remove_unmanaged_unit(slug: str, unit_name: str) -> None:
    """Disable and delete a unit that has no matching job JSON.

    `unit_name` is the actual unit discovery found (.timer for a periodic job,
    .service for a mount) — disabling the wrong one would silently no-op.
    """
    systemctl.disable_now(unit_name)
    units_io.remove_units(slug)
    systemctl.daemon_reload()
