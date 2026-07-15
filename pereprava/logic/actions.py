"""Job mutation actions: every create/edit/delete/toggle goes through here.

Each mutation follows the same order: write JSON -> regenerate units -> daemon-reload.
"""

from __future__ import annotations

import subprocess

from pereprava.logic.units import unit_basename
from pereprava.model.job import Job, JobType
from pereprava.storage import history, jobs_store, systemctl, units_io


def _managed_unit(job: Job) -> str:
    """The unit systemctl enable/disable/start acts on: the service itself for a
    persistent mount, or the timer for a periodic job (the oneshot service is
    only ever started transiently via run_now)."""
    base = unit_basename(job.slug)
    return f"{base}.service" if job.job_type == JobType.RCLONE_MOUNT else f"{base}.timer"


def _result_error(result: subprocess.CompletedProcess) -> str | None:
    """None if the systemctl call succeeded, otherwise its stderr/stdout."""
    if result.returncode == 0:
        return None
    return result.stderr.strip() or result.stdout.strip() or "systemctl failed with no output."


def save_and_apply(job: Job) -> tuple[bool, str]:
    """Persist a job's JSON and (re)generate + (re)enable its systemd units.

    Returns (True, "") on success, or (False, error) if the enable/disable step
    failed — the JSON and unit files are still written either way, since a job
    that fails to start is still a job the user asked to exist.
    """
    jobs_store.save_job(job)
    units_io.write_units(job)
    systemctl.daemon_reload()
    unit = _managed_unit(job)
    result = systemctl.enable_now(unit) if job.enabled else systemctl.disable_now(unit)
    error = _result_error(result)
    if error:
        return False, error
    return True, ""


def delete_job_and_units(job: Job) -> tuple[bool, str]:
    result = systemctl.disable_now(_managed_unit(job))
    units_io.remove_units(job.slug)
    systemctl.daemon_reload()
    jobs_store.delete_job(job.slug)
    history.delete_history(job.slug)
    error = _result_error(result)
    if error:
        return False, error
    return True, ""


def set_enabled(job: Job, enabled: bool) -> tuple[bool, str]:
    job.enabled = enabled
    return save_and_apply(job)


def run_now(slug: str) -> tuple[bool, str]:
    base = unit_basename(slug)
    result = systemctl.start_now(f"{base}.service")
    error = _result_error(result)
    if error:
        return False, error
    return True, ""


def repair_units(job: Job) -> tuple[bool, str]:
    """Regenerate units for a job whose JSON exists but whose units went missing.

    Forces enabled=True regardless of the job's stored state. A job showing up
    as "needs repair" is being surfaced as broken and in need of fixing — if
    it was previously paused and its unit had since been garbage-collected by
    systemd (so "needs repair" is how a paused-then-GC'd job actually
    presents), respecting the stored disabled state here would just call
    disable_now on a unit that isn't loaded — a no-op that reports success
    while changing nothing, leaving the discrepancy stuck forever with no way
    out via this button. Pause it again from the normal row afterward if you
    didn't want it running.
    """
    job.enabled = True
    return save_and_apply(job)


def remove_unmanaged_unit(slug: str, unit_name: str) -> None:
    """Disable and delete a unit that has no matching job JSON.

    `unit_name` is the actual unit discovery found (.timer for a periodic job,
    .service for a mount) — disabling the wrong one would silently no-op.
    """
    systemctl.disable_now(unit_name)
    units_io.remove_units(slug)
    systemctl.daemon_reload()
