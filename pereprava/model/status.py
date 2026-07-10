"""Live status of a job, as read from systemd — never persisted."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RunState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    OK = "ok"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class JobStatus:
    state: RunState
    timer_enabled: bool
    next_run: datetime | None = None
    last_run: datetime | None = None
    last_result: str | None = None  # "success" | "failed" | None


class DiscrepancyKind(Enum):
    """A job/unit pairing that doesn't line up cleanly."""

    UNMANAGED_UNIT = "unmanaged_unit"  # unit exists, no matching job JSON
    NEEDS_REPAIR = "needs_repair"  # job JSON exists, no matching unit


@dataclass
class Discrepancy:
    kind: DiscrepancyKind
    slug: str
    unit_name: str | None = None
