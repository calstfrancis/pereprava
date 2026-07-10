"""Reconcile app-owned job JSON files against systemd units on disk."""

from __future__ import annotations

from dataclasses import dataclass

from pereprava.logic.status import get_job_status
from pereprava.logic.units import UNIT_PREFIX
from pereprava.model.job import Job
from pereprava.model.status import Discrepancy, DiscrepancyKind, JobStatus
from pereprava.storage import jobs_store, systemctl

UNIT_GLOB = f"{UNIT_PREFIX}*.timer"


@dataclass
class JobEntry:
    job: Job
    status: JobStatus


def _slug_from_unit_name(unit_name: str) -> str:
    stem = unit_name.removesuffix(".timer")
    return stem.removeprefix(UNIT_PREFIX)


def scan() -> tuple[list[JobEntry], list[Discrepancy]]:
    unit_entries = systemctl.list_units_json(UNIT_GLOB)
    unit_slugs = {
        _slug_from_unit_name(entry["unit"])
        for entry in unit_entries
        if "unit" in entry
    }

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
        entries.append(JobEntry(job=job, status=get_job_status(slug)))

    discrepancies: list[Discrepancy] = []
    for slug in sorted(unmanaged):
        discrepancies.append(
            Discrepancy(kind=DiscrepancyKind.UNMANAGED_UNIT, slug=slug, unit_name=f"{UNIT_PREFIX}{slug}.timer")
        )
    for slug in sorted(needs_repair):
        discrepancies.append(Discrepancy(kind=DiscrepancyKind.NEEDS_REPAIR, slug=slug))

    return entries, discrepancies
