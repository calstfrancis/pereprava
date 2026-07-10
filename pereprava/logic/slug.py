"""Turn a job name into a filesystem/systemd-safe slug."""

from __future__ import annotations

import re

_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "job"


def is_valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


def unique_slug(name: str, existing_slugs: set[str]) -> str:
    base = slugify(name)
    if base not in existing_slugs:
        return base
    n = 2
    while f"{base}-{n}" in existing_slugs:
        n += 1
    return f"{base}-{n}"
