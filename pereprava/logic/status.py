"""Combine systemctl output into a JobStatus for one job."""

from __future__ import annotations

import re
from datetime import datetime

from pereprava.logic.units import unit_basename
from pereprava.model.job import JobType
from pereprava.model.status import JobStatus, RunState
from pereprava.storage import systemctl

_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})")


def _parse_systemd_timestamp(value: str) -> datetime | None:
    """Best-effort parse of systemd's human timestamp string, as local time."""
    if not value:
        return None
    match = _TIMESTAMP_RE.search(value)
    if not match:
        return None
    try:
        return datetime.strptime(f"{match.group(1)} {match.group(2)}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _parse_epoch_field(entry: dict, *keys: str) -> datetime | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, (int, float)) and value > 0:
            try:
                return datetime.fromtimestamp(value / 1_000_000)
            except (OverflowError, OSError, ValueError):
                return None
    return None


def _condition_unmet(props: dict) -> bool:
    """True if the unit's last start attempt was silently skipped by a Run
    Condition (ConditionACPower= or the Wi-Fi SSID ExecCondition=) — systemd
    treats this as a routine skip, not a failure: no error, no exec attempt,
    ActiveState/ExecMain* stay exactly as they were before, and Result is
    either untouched (plain Condition=) or set to the specific value
    "exec-condition" (ExecCondition=) — never "success" or a real failure
    code. Folded directly into `state` as RunState.SKIPPED rather than a
    separate flag, so every consumer that already switches on `state` (the
    tray icon, desktop notifications, run history) handles this correctly by
    construction instead of needing to separately learn a new field exists."""
    return props.get("ConditionResult") == "no" or props.get("Result") == "exec-condition"


def _get_mount_status(service_unit: str) -> JobStatus:
    """Mount jobs have no timer — the service itself is the enabled/running unit,
    and its steady state (mounted and idle) is what other job types call OK."""
    service_props = systemctl.show_properties(
        service_unit,
        ["ActiveState", "SubState", "Result", "ActiveEnterTimestamp", "UnitFileState", "ConditionResult"],
    )
    enabled = service_props.get("UnitFileState") == "enabled"
    active_state = service_props.get("ActiveState", "")
    result = service_props.get("Result", "")
    mounted_since = _parse_systemd_timestamp(service_props.get("ActiveEnterTimestamp", ""))

    if active_state == "activating":
        state = RunState.RUNNING
    elif not enabled:
        state = RunState.PAUSED
    elif _condition_unmet(service_props):
        state = RunState.SKIPPED
    elif active_state == "failed" or (result and result != "success"):
        state = RunState.FAILED
    elif active_state == "active":
        state = RunState.OK
    else:
        state = RunState.IDLE

    return JobStatus(
        state=state,
        timer_enabled=enabled,
        next_run=None,
        last_run=mounted_since,
        last_result=result or None,
    )


def get_job_status(slug: str, job_type: JobType) -> JobStatus:
    base = unit_basename(slug)
    service_unit = f"{base}.service"

    if job_type == JobType.RCLONE_MOUNT:
        return _get_mount_status(service_unit)

    timer_unit = f"{base}.timer"

    service_props = systemctl.show_properties(
        service_unit,
        ["ActiveState", "SubState", "Result", "ExecMainStartTimestamp", "ExecMainExitTimestamp", "ConditionResult"],
    )
    timer_props = systemctl.show_properties(timer_unit, ["UnitFileState"])

    timer_enabled = timer_props.get("UnitFileState") == "enabled"

    active_state = service_props.get("ActiveState", "")
    sub_state = service_props.get("SubState", "")
    result = service_props.get("Result", "")
    started = _parse_systemd_timestamp(service_props.get("ExecMainStartTimestamp", ""))
    exited = _parse_systemd_timestamp(service_props.get("ExecMainExitTimestamp", ""))
    duration_seconds = (exited - started).total_seconds() if started and exited and exited >= started else None

    timers = systemctl.list_timers_json(timer_unit)
    next_run: datetime | None = None
    last_run: datetime | None = None
    if timers:
        entry = timers[0]
        next_run = _parse_epoch_field(entry, "next", "next_usec", "next_elapse_usec_realtime")
        last_run = _parse_epoch_field(entry, "last", "last_usec", "last_trigger_usec")

    if last_run is None:
        last_run = started

    if active_state in ("activating", "reloading") or sub_state == "start":
        state = RunState.RUNNING
    elif not timer_enabled:
        state = RunState.PAUSED
    elif _condition_unmet(service_props):
        state = RunState.SKIPPED
    elif last_run is None:
        state = RunState.IDLE
    elif result == "success":
        state = RunState.OK
    elif result:
        state = RunState.FAILED
    else:
        state = RunState.IDLE

    return JobStatus(
        state=state,
        timer_enabled=timer_enabled,
        next_run=next_run if timer_enabled else None,
        last_run=last_run,
        last_result=result or None,
        last_run_duration_seconds=duration_seconds,
    )
