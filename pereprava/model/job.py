"""Job and Schedule dataclasses — the in-memory form of a job's JSON definition."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

SCHEMA_VERSION = 1


class JobType(Enum):
    RCLONE_COPY = "rclone_copy"
    RCLONE_SYNC = "rclone_sync"
    RCLONE_BISYNC = "rclone_bisync"
    RCLONE_CHECK = "rclone_check"
    RSYNC = "rsync"
    CUSTOM = "custom"
    RCLONE_MOUNT = "rclone_mount"


# Human-facing labels, in the order they should appear in the job-type combo.
JOB_TYPE_LABELS: dict[JobType, str] = {
    JobType.RCLONE_COPY: "rclone copy (never deletes)",
    JobType.RCLONE_SYNC: "rclone sync (can delete at destination)",
    JobType.RCLONE_BISYNC: "rclone bisync (can delete on either side)",
    JobType.RCLONE_CHECK: "rclone check (verify only, never transfers)",
    JobType.RSYNC: "rsync",
    JobType.CUSTOM: "Custom command",
    JobType.RCLONE_MOUNT: "rclone mount (persistent mount point)",
}

SCHEDULE_PRESETS: dict[str, str] = {
    "hourly": "hourly",
    "every6h": "0/6:00",
    "daily": "daily",
    "weekly": "weekly",
}

DEFAULT_RANDOMIZED_DELAY_SEC = 900


@dataclass
class Schedule:
    preset: str = "daily"  # one of SCHEDULE_PRESETS keys, or "custom"
    on_calendar: str = "daily"  # actual systemd OnCalendar= value
    randomized_delay_sec: int = DEFAULT_RANDOMIZED_DELAY_SEC

    def to_dict(self) -> dict:
        return {
            "preset": self.preset,
            "on_calendar": self.on_calendar,
            "randomized_delay_sec": self.randomized_delay_sec,
        }

    @staticmethod
    def from_dict(data: dict) -> "Schedule":
        return Schedule(
            preset=data.get("preset", "daily"),
            on_calendar=data.get("on_calendar", "daily"),
            randomized_delay_sec=data.get("randomized_delay_sec", DEFAULT_RANDOMIZED_DELAY_SEC),
        )


@dataclass
class Job:
    slug: str
    name: str
    job_type: JobType
    source: str
    destination: str
    schedule: Schedule
    log_path: str
    extra_args: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
    bwlimit: str = ""
    pre_hook: str = ""
    post_hook: str = ""
    condition_ac_power: bool = False
    condition_ssid: str = ""
    rc_port: int = 0  # >0 means rclone --rc live-progress is enabled on this port
    custom_command: list[str] | None = None
    rsync_delete: bool = False
    enabled: bool = True
    schema_version: int = SCHEMA_VERSION

    @property
    def destructive(self) -> bool:
        """Whether this job can delete files at its destination.

        Derived from job_type, never a free-standing user-settable flag —
        rclone copy structurally cannot delete, sync/bisync/custom always can.
        A mount or a check doesn't copy/delete anything itself, so neither is
        ever destructive.
        """
        if self.job_type in (JobType.RCLONE_COPY, JobType.RCLONE_MOUNT, JobType.RCLONE_CHECK):
            return False
        if self.job_type == JobType.RSYNC:
            return self.rsync_delete
        # rclone_sync, rclone_bisync, custom
        return True

    @property
    def is_mount(self) -> bool:
        return self.job_type == JobType.RCLONE_MOUNT

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "slug": self.slug,
            "name": self.name,
            "job_type": self.job_type.value,
            "source": self.source,
            "destination": self.destination,
            "extra_args": self.extra_args,
            "excludes": self.excludes,
            "includes": self.includes,
            "bwlimit": self.bwlimit,
            "pre_hook": self.pre_hook,
            "post_hook": self.post_hook,
            "condition_ac_power": self.condition_ac_power,
            "condition_ssid": self.condition_ssid,
            "rc_port": self.rc_port,
            "custom_command": self.custom_command,
            "rsync_delete": self.rsync_delete,
            "schedule": self.schedule.to_dict(),
            "log_path": self.log_path,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data: dict) -> "Job":
        return Job(
            slug=data["slug"],
            name=data["name"],
            job_type=JobType(data["job_type"]),
            source=data["source"],
            destination=data["destination"],
            extra_args=list(data.get("extra_args", [])),
            excludes=list(data.get("excludes", [])),
            includes=list(data.get("includes", [])),
            bwlimit=data.get("bwlimit", ""),
            pre_hook=data.get("pre_hook", ""),
            post_hook=data.get("post_hook", ""),
            condition_ac_power=data.get("condition_ac_power", False),
            condition_ssid=data.get("condition_ssid", ""),
            rc_port=data.get("rc_port", 0),
            custom_command=data.get("custom_command"),
            rsync_delete=data.get("rsync_delete", False),
            schedule=Schedule.from_dict(data.get("schedule", {})),
            log_path=data["log_path"],
            enabled=data.get("enabled", True),
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )
