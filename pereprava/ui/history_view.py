"""Read-only run history dialog: when a job last ran, how long it took, and
whether it succeeded — sourced from storage/history.py."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from pereprava.storage import history


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown duration"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _build_row(entry: dict) -> Adw.ActionRow:
    started_at = history.parse_started_at(entry)
    row = Adw.ActionRow()
    row.set_title(started_at.strftime("%Y-%m-%d %H:%M") if started_at else "(unknown time)")
    row.set_subtitle(_format_duration(entry.get("duration_seconds")))

    result = entry.get("result")
    ok = result == "success"
    label = Gtk.Label(label="OK" if ok else f"Failed ({result})" if result else "Failed")
    label.add_css_class("pereprava-status-ok" if ok else "pereprava-status-failed")
    label.add_css_class("dim-label")
    row.add_suffix(label)
    row.set_activatable(False)
    return row


class HistoryViewDialog(Adw.Dialog):
    def __init__(self, job_name: str, slug: str):
        super().__init__()
        self.set_title(f"History — {job_name}")
        self.set_content_width(480)
        self.set_content_height(560)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        toolbar_view.add_top_bar(header)

        entries = history.load_history(slug)

        if not entries:
            status_page = Adw.StatusPage(
                title="No runs recorded yet",
                description="History is recorded the next time this job runs.",
                icon_name="document-open-recent-symbolic",
            )
            toolbar_view.set_content(status_page)
        else:
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_vexpand(True)
            list_box = Gtk.ListBox()
            list_box.set_selection_mode(Gtk.SelectionMode.NONE)
            list_box.add_css_class("boxed-list")
            list_box.set_margin_start(12)
            list_box.set_margin_end(12)
            list_box.set_margin_top(12)
            list_box.set_margin_bottom(12)
            for entry in entries:
                list_box.append(_build_row(entry))
            scrolled.set_child(list_box)
            toolbar_view.set_content(scrolled)

        self.set_child(toolbar_view)
