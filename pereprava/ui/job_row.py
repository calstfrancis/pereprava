"""Build one list row per job, Nautilus-list-view styled: icon left, name/subtitle
left, status + timing right-aligned, actions in a hand-built popover menu."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from pereprava.logic.discovery import JobEntry
from pereprava.model.job import JobType
from pereprava.model.status import Discrepancy, DiscrepancyKind, RunState

_TYPE_ICON = {
    JobType.RCLONE_COPY: "folder-remote-symbolic",
    JobType.RCLONE_SYNC: "folder-remote-symbolic",
    JobType.RCLONE_BISYNC: "emblem-synchronizing-symbolic",
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


def build_menu_button(
    slug: str,
    *,
    on_run_now: Callable[[str], None],
    on_view_log: Callable[[str], None],
    on_toggle_pause: Callable[[str], None],
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
    is_paused: bool,
    is_mount: bool = False,
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
    row.set_subtitle(f"{job.source} → {job.destination}")
    row.add_prefix(Gtk.Image.new_from_icon_name(_TYPE_ICON[job.job_type]))

    suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    suffix.set_valign(Gtk.Align.CENTER)

    if job.destructive:
        warn = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        warn.add_css_class("pereprava-warning-icon")
        warn.set_tooltip_text("This job can delete files at the destination")
        suffix.append(warn)

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
            is_paused=not job.enabled,
            is_mount=job.job_type == JobType.RCLONE_MOUNT,
        )
    )

    row.add_suffix(suffix)
    row.set_activatable(False)
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
        button = Gtk.Button(label="Repair")
        button.add_css_class("flat")
        button.connect("clicked", lambda _b: callbacks["on_repair"](disc.slug))
        row.add_suffix(button)
    row.set_activatable(False)
    return row
