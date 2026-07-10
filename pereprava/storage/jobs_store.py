"""Load/save Job definitions as JSON under ~/.config/pereprava/jobs/."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pereprava.model.job import Job

CONFIG_DIR = Path.home() / ".config" / "pereprava"
JOBS_DIR = CONFIG_DIR / "jobs"


def ensure_jobs_dir() -> Path:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    return JOBS_DIR


def job_path(slug: str) -> Path:
    return JOBS_DIR / f"{slug}.json"


def list_job_slugs() -> list[str]:
    if not JOBS_DIR.exists():
        return []
    return sorted(p.stem for p in JOBS_DIR.glob("*.json"))


def load_job(slug: str) -> Job:
    with open(job_path(slug), "r", encoding="utf-8") as f:
        return Job.from_dict(json.load(f))


def load_all_jobs() -> list[Job]:
    jobs = []
    for slug in list_job_slugs():
        try:
            jobs.append(load_job(slug))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return jobs


def save_job(job: Job) -> None:
    ensure_jobs_dir()
    target = job_path(job.slug)
    tmp = target.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(job.to_dict(), f, indent=2)
    os.replace(tmp, target)


def delete_job(slug: str) -> None:
    job_path(slug).unlink(missing_ok=True)
