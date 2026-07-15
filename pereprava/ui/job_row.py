"""Build one list row per job, Nautilus-list-view styled: icon left, name/subtitle
left, status + timing right-aligned, actions in a hand-built popover menu."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from pereprava.logic.discovery import JobEntry
from pereprava.logic.rc import RC_CAPABLE_TYPES
from pereprava.model.job import Job, JobType
from pereprava.model.status import Discrepancy, DiscrepancyKind, RunState
from pereprava.storage.rc_client import fetch_stats

_RC_POLL_INTERVAL_MS = 1500

_TYPE_ICON = {
    JobType.RCLONE_COPY: "folder-remote-symbolic",
    JobType.RCLONE_SYNC: "view-refresh-symbolic",
    JobType.RCLONE_BISYNC: "emblem-synchronizing-symbolic",
    JobType.RCLONE_CHECK: "edit-find-symbolic",
    JobType.RSYNC: "folder-symbolic",
    JobType.CUSTOM: "utilities-terminal-symbolic",
    JobType.RCLONE_MOUNT: "drive-harddisk-symbolic",
}

_STATE_CSS = {
    RunState.OK: "pereprava-status-ok",
    RunState.FAILED: "pereprava-status-failed",
    RunState.RUNNING: "pereprava-status-running",
    RunState.PAUSED: "pereprava-status-paused",
    RunState.IDLE: "pereprava-status-paused",
}


def _relative(dt: datetime, *, future: bool) -> str:
    now = datetime.now()
    delta = (dt - now) if future else (now - dt)
    seconds = delta.total_seconds()
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        span = "under a minute"
    elif seconds < 3600:
        span = f"{int(seconds // 60)}m"
    elif seconds < 86400:
        span = f"{int(seconds // 3600)}h"
    else:
        span = f"{int(seconds // 86400)}d"
    return f"in {span}" if future else f"{span} ago"


def _elide_middle(text: str, max_len: int = 40) -> str:
    """Elide the middle of a long path, keeping both ends visible — the default
    single-direction ellipsis on a combined "source → destination" string can
    otherwise hide an entire side depending on which one runs long."""
    if len(text) <= max_len:
        return text
    keep = (max_len - 1) // 2
    return f"{text[:keep]}…{text[-keep:]}"


def status_text(entry: JobEntry) -> str:
    status = entry.status
    if entry.job.job_type == JobType.RCLONE_MOUNT:
        if status.state == RunState.RUNNING:
            return "Mounting…"
        if status.state == RunState.PAUSED:
            return "Unmounted"
        if status.state == RunState.FAILED:
            when = _relative(status.last_run, future=False) if status.last_run else ""
            return f"Mount failed {when}".strip()
        if status.state == RunState.OK:
            if status.last_run:
                return f"Mounted · since {_relative(status.last_run, future=False)}"
            return "Mounted"
        return "Not mounted"
    if status.state == RunState.RUNNING:
        return "Running…"
    if status.state == RunState.PAUSED:
        return "Paused"
    if status.state == RunState.FAILED:
        when = _relative(status.last_run, future=False) if status.last_run else ""
        return f"Failed {when}".strip()
    if status.state == RunState.OK:
        base = "OK"
        if status.next_run:
            base += f" · next {_relative(status.next_run, future=True)}"
        return base
    return "Never run"


def _format_speed(bytes_per_sec: float) -> str:
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if abs(bytes_per_sec) < 1024 or unit == "GB/s":
            return f"{bytes_per_sec:.1f} {unit}"
        bytes_per_sec /= 1024
    return f"{bytes_per_sec:.1f} GB/s"


def _format_eta(seconds) -> str:
    if not seconds or seconds <= 0:
        return ""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def _build_progress_widget(job: Job) -> Gtk.Box:
    """Live progress for a running rclone job, polled from its --rc server
    (see logic/rc.py, storage/rc_client.py) — real transfer stats, not a
    guess. Self-contained: owns its own poll timer and cleans it up when the
    row is destroyed (the whole list gets rebuilt on every refresh tick)."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.set_valign(Gtk.Align.CENTER)
    box.set_size_request(120, -1)

    label = Gtk.Label(label="Starting…")
    label.add_css_class("caption")
    label.add_css_class("dim-label")
    label.set_xalign(1.0)
    box.append(label)

    bar = Gtk.ProgressBar()
    bar.set_show_text(False)
    bar.add_css_class("pereprava-progress-bar")
    box.append(bar)

    in_flight = [False]

    def apply_stats(stats: dict | None) -> bool:
        in_flight[0] = False
        if stats is None:
            return GLib.SOURCE_REMOVE
        if job.job_type == JobType.RCLONE_CHECK:
            done, total = stats.get("checks", 0), stats.get("totalChecks", 0)
            if total:
                bar.set_fraction(min(done / total, 1.0))
                label.set_text(f"{done}/{total} checked")
            else:
                bar.pulse()
                label.set_text(f"{done} checked")
            return GLib.SOURCE_REMOVE
        done, total = stats.get("bytes", 0), stats.get("totalBytes", 0)
        speed = stats.get("speed", 0)
        if total:
            pct = done / total * 100
            bar.set_fraction(min(done / total, 1.0))
            eta_text = _format_eta(stats.get("eta"))
            suffix = f" · ETA {eta_text}" if eta_text else ""
            label.set_text(f"{pct:.0f}% · {_format_speed(speed)}{suffix}")
        else:
            bar.pulse()
            label.set_text(_format_speed(speed) if speed else "Starting…")
        return GLib.SOURCE_REMOVE

    def poll() -> bool:
        if in_flight[0]:
            return GLib.SOURCE_CONTINUE
        in_flight[0] = True

        def worker() -> None:
            stats = fetch_stats(job.rc_port)
            GLib.idle_add(apply_stats, stats)

        threading.Thread(target=worker, daemon=True).start()
        return GLib.SOURCE_CONTINUE

    timer_id = GLib.timeout_add(_RC_POLL_INTERVAL_MS, poll)
    poll()
    box.connect("destroy", lambda *_a: GLib.source_remove(timer_id))
    return box


def build_menu_button(
    slug: str,
    *,
    on_run_now: Callable[[str], None],
    on_view_log: Callable[[str], None],
    on_toggle_pause: Callable[[str], None],
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
    on_duplicate: Callable[[str], None],
    on_restore: Callable[[str], None],
    on_view_history: Callable[[str], None],
    is_paused: bool,
    is_mount: bool = False,
    can_restore: bool = False,
) -> Gtk.MenuButton:
    popover = Gtk.Popover()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    box.set_margin_start(6)
    box.set_margin_end(6)

    def make_item(label: str, callback: Callable[[], None]) -> Gtk.Button:
        button = Gtk.Button(label=label)
        button.add_css_class("flat")
        button.set_halign(Gtk.Align.FILL)
        child = button.get_child()
        if isinstance(child, Gtk.Label):
            child.set_xalign(0.0)

        def _clicked(_btn):
            popover.popdown()
            callback()

        button.connect("clicked", _clicked)
        return button

    if is_mount:
        # A mount has no "run once" concept — Mount/Unmount (toggle_pause) already
        # covers start/stop.
        box.append(make_item("Unmount" if not is_paused else "Mount", lambda: on_toggle_pause(slug)))
    else:
        box.append(make_item("Run Now", lambda: on_run_now(slug)))
        box.append(make_item("View Log", lambda: on_view_log(slug)))
        box.append(make_item("Resume" if is_paused else "Pause", lambda: on_toggle_pause(slug)))
    if is_mount:
        box.append(make_item("View Log", lambda: on_view_log(slug)))
    else:
        box.append(make_item("View History", lambda: on_view_history(slug)))
    box.append(Gtk.Separator())
    box.append(make_item("Duplicate…", lambda: on_duplicate(slug)))
    if can_restore:
        box.append(make_item("Restore…", lambda: on_restore(slug)))
    box.append(Gtk.Separator())
    box.append(make_item("Edit…", lambda: on_edit(slug)))
    box.append(make_item("Delete…", lambda: on_delete(slug)))

    popover.set_child(box)
    menu_button = Gtk.MenuButton()
    menu_button.set_icon_name("view-more-symbolic")
    menu_button.set_popover(popover)
    menu_button.add_css_class("flat")
    menu_button.set_tooltip_text("Job actions")
    return menu_button


def build_job_row(entry: JobEntry, callbacks: dict) -> Adw.ActionRow:
    job = entry.job
    row = Adw.ActionRow()
    row.set_title(job.name)
    row.set_subtitle(f"{_elide_middle(job.source)} → {_elide_middle(job.destination)}")
    row.set_tooltip_text(f"{job.source} → {job.destination}")
    row.add_prefix(Gtk.Image.new_from_icon_name(_TYPE_ICON[job.job_type]))

    suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    suffix.set_valign(Gtk.Align.CENTER)

    if job.destructive:
        warn = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warn.add_css_class("pereprava-warning-icon")
        warn.set_tooltip_text("This job can delete files at the destination")
        suffix.append(warn)

    show_progress = (
        job.rc_port > 0 and job.job_type in RC_CAPABLE_TYPES and entry.status.state == RunState.RUNNING
    )
    if show_progress:
        suffix.append(_build_progress_widget(job))
    else:
        status_label = Gtk.Label(label=status_text(entry))
        status_label.add_css_class(_STATE_CSS[entry.status.state])
        status_label.add_css_class("dim-label")
        suffix.append(status_label)

    suffix.append(
        build_menu_button(
            job.slug,
            on_run_now=callbacks["on_run_now"],
            on_view_log=callbacks["on_view_log"],
            on_toggle_pause=callbacks["on_toggle_pause"],
            on_edit=callbacks["on_edit"],
            on_delete=callbacks["on_delete"],
            on_duplicate=callbacks["on_duplicate"],
            on_restore=callbacks["on_restore"],
            on_view_history=callbacks["on_view_history"],
            is_paused=not job.enabled,
            is_mount=job.job_type == JobType.RCLONE_MOUNT,
            can_restore=job.job_type
            in (JobType.RCLONE_COPY, JobType.RCLONE_SYNC, JobType.RCLONE_BISYNC, JobType.RSYNC),
        )
    )

    row.add_suffix(suffix)
    row.set_activatable(False)
    return row


def build_section_header(text: str) -> Gtk.ListBoxRow:
    """A plain, non-interactive heading row — so discrepancies read as a
    distinct group instead of just more rows tacked onto the job list."""
    row = Gtk.ListBoxRow()
    row.set_selectable(False)
    row.set_activatable(False)
    row.add_css_class("pereprava-section-header")
    label = Gtk.Label(label=text)
    label.add_css_class("heading")
    label.add_css_class("dim-label")
    label.set_xalign(0.0)
    label.set_margin_start(12)
    label.set_margin_top(12)
    label.set_margin_bottom(4)
    row.set_child(label)
    return row


def build_discrepancy_row(disc: Discrepancy, callbacks: dict) -> Adw.ActionRow:
    row = Adw.ActionRow()
    if disc.kind == DiscrepancyKind.UNMANAGED_UNIT:
        row.set_title(disc.unit_name or disc.slug)
        row.set_subtitle("Unit exists but isn't managed by Pereprava")
        row.add_prefix(Gtk.Image.new_from_icon_name("dialog-question-symbolic"))
        button = Gtk.Button(label="Remove")
        button.add_css_class("flat")
        button.connect("clicked", lambda _b: callbacks["on_remove_unmanaged"](disc.slug, disc.unit_name))
        row.add_suffix(button)
    else:
        row.set_title(disc.slug)
        row.set_subtitle("Job definition exists but its systemd units are missing")
        row.add_prefix(Gtk.Image.new_from_icon_name("dialog-warning-symbolic"))

        suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        repair_button = Gtk.Button(label="Repair")
        repair_button.add_css_class("flat")
        repair_button.connect("clicked", lambda _b: callbacks["on_repair"](disc.slug))
        suffix.append(repair_button)

        # Repair alone used to be a dead end for a job whose JSON still exists
        # but that can't be fixed by re-enabling it (e.g. a bad path/remote) —
        # there was no way to change or give up on it from this row at all.
        edit_button = Gtk.Button(icon_name="document-edit-symbolic")
        edit_button.add_css_class("flat")
        edit_button.set_tooltip_text("Edit")
        edit_button.connect("clicked", lambda _b: callbacks["on_edit"](disc.slug))
        suffix.append(edit_button)

        delete_button = Gtk.Button(icon_name="user-trash-symbolic")
        delete_button.add_css_class("flat")
        delete_button.set_tooltip_text("Delete")
        delete_button.connect("clicked", lambda _b: callbacks["on_delete"](disc.slug))
        suffix.append(delete_button)

        row.add_suffix(suffix)
    row.set_activatable(False)
    return row
