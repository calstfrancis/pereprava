"""Export/import job definitions as a single JSON file. Per-job JSON files under
~/.config/pereprava/jobs/ remain the source of truth — this just bundles them for
backup/migration."""

from __future__ import annotations

import json
from pathlib import Path

from pereprava.logic import actions
from pereprava.logic.slug import unique_slug
from pereprava.model.job import Job
from pereprava.storage import jobs_store

EXPORT_SCHEMA_VERSION = 1


def export_jobs(dest_path: Path) -> int:
    """Write every job definition to `dest_path`. Returns the number exported."""
    jobs = jobs_store.load_all_jobs()
    payload = {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "jobs": [job.to_dict() for job in jobs],
    }
    dest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(jobs)


def import_jobs(src_path: Path) -> tuple[int, list[str]]:
    """Import job definitions from an exported file, regenerating and enabling
    systemd units for each. A name clash with an existing job gets a new slug
    rather than silently overwriting it. Returns (imported_count, errors)."""
    payload = json.loads(src_path.read_text(encoding="utf-8"))
    jobs_data = payload.get("jobs", []) if isinstance(payload, dict) else payload

    existing_slugs = set(jobs_store.list_job_slugs())
    imported = 0
    errors: list[str] = []

    for entry in jobs_data:
        try:
            job = Job.from_dict(entry)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            errors.append(f"Skipped an invalid job entry: {exc}")
            continue
        if job.slug in existing_slugs:
            job.slug = unique_slug(job.name, existing_slugs)
        existing_slugs.add(job.slug)
        actions.save_and_apply(job)
        imported += 1

    return imported, errors
