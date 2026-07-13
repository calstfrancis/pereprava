"""Reconcile app-owned job JSON files against systemd units on disk."""

from __future__ import annotations

from dataclasses import dataclass

from pereprava.logic.status import get_job_status
from pereprava.logic.units import UNIT_PREFIX
from pereprava.model.job import Job
from pereprava.model.status import Discrepancy, DiscrepancyKind, JobStatus
from pereprava.storage import jobs_store, systemctl

TIMER_GLOB = f"{UNIT_PREFIX}*.timer"
# Mount jobs have no timer — their .service is the always-installed unit, same
# role a .timer plays for periodic jobs (see logic/units.py, logic/actions.py).
MOUNT_SERVICE_GLOB = f"{UNIT_PREFIX}*.service"


@dataclass
class JobEntry:
    job: Job
    status: JobStatus


def _slug_from_unit_name(unit_name: str) -> str:
    stem = unit_name.removesuffix(".timer").removesuffix(".service")
    return stem.removeprefix(UNIT_PREFIX)


def scan() -> tuple[list[JobEntry], list[Discrepancy]]:
    timer_entries = systemctl.list_units_json(TIMER_GLOB)
    mount_service_entries = systemctl.list_units_json(MOUNT_SERVICE_GLOB)

    # unit_name per slug, preferring the timer if somehow both showed up —
    # this is what a discrepancy would disable/remove if the job turns out unmanaged.
    unit_name_by_slug: dict[str, str] = {}
    for entry in mount_service_entries:
        if "unit" in entry:
            unit_name_by_slug[_slug_from_unit_name(entry["unit"])] = entry["unit"]
    for entry in timer_entries:
        if "unit" in entry:
            unit_name_by_slug[_slug_from_unit_name(entry["unit"])] = entry["unit"]

    unit_slugs = set(unit_name_by_slug)
    job_slugs = set(jobs_store.list_job_slugs())

    matched = job_slugs & unit_slugs
    unmanaged = unit_slugs - job_slugs
    needs_repair = job_slugs - unit_slugs

    entries: list[JobEntry] = []
    for slug in sorted(matched):
        try:
            job = jobs_store.load_job(slug)
        except (OSError, ValueError, KeyError):
            continue
        entries.append(JobEntry(job=job, status=get_job_status(slug, job.job_type)))

    discrepancies: list[Discrepancy] = []
    for slug in sorted(unmanaged):
        discrepancies.append(
            Discrepancy(kind=DiscrepancyKind.UNMANAGED_UNIT, slug=slug, unit_name=unit_name_by_slug[slug])
        )
    for slug in sorted(needs_repair):
        discrepancies.append(Discrepancy(kind=DiscrepancyKind.NEEDS_REPAIR, slug=slug))

    return entries, discrepancies
