"""Main application window: job list + status polling."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from pereprava.logic import actions, discovery
from pereprava.ui.job_form import JobFormDialog
from pereprava.ui.job_row import build_discrepancy_row, build_job_row
from pereprava.ui.log_view import LogViewDialog
from pereprava.storage.jobs_store import load_job

REFRESH_INTERVAL_SECONDS = 8


class AppWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_title("Pereprava")
        self.set_default_size(760, 600)

        self._is_active = True
        self.connect("notify::is-active", self._on_is_active_changed)

        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Adw.WindowTitle(title="Pereprava", subtitle=""))

        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.set_tooltip_text("Add Job")
        add_button.connect("clicked", self._on_add_job)
        header.pack_start(add_button)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh")
        refresh_button.connect("clicked", lambda _b: self.refresh())
        header.pack_end(refresh_button)

        toolbar_view.add_top_bar(header)

        self._stack = Gtk.Stack()
        toolbar_view.set_content(self._stack)
        self._toast_overlay.set_child(toolbar_view)

        self._empty_state = Adw.StatusPage(
            title="No backup jobs yet",
            description="Add a job to start backing something up.",
            icon_name="folder-remote-symbolic",
        )
        empty_add_button = Gtk.Button(label="Add Job")
        empty_add_button.add_css_class("suggested-action")
        empty_add_button.add_css_class("pill")
        empty_add_button.set_halign(Gtk.Align.CENTER)
        empty_add_button.connect("clicked", self._on_add_job)
        self._empty_state.set_child(empty_add_button)
        self._stack.add_named(self._empty_state, "empty")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("pereprava-job-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self._list_box)
        self._stack.add_named(scrolled, "list")

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self._on_refresh_tick)

    def _on_is_active_changed(self, *_args) -> None:
        self._is_active = self.is_active()

    def _on_refresh_tick(self) -> bool:
        if self._is_active:
            self.refresh()
        return True  # keep the timeout registered

    def refresh(self) -> None:
        entries, discrepancies = discovery.scan()

        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        if not entries and not discrepancies:
            self._stack.set_visible_child_name("empty")
            return
        self._stack.set_visible_child_name("list")

        callbacks = {
            "on_run_now": self._on_run_now,
            "on_view_log": self._on_view_log,
            "on_toggle_pause": self._on_toggle_pause,
            "on_edit": self._on_edit,
            "on_delete": self._on_delete,
        }
        for entry in entries:
            self._list_box.append(build_job_row(entry, callbacks))

        disc_callbacks = {
            "on_remove_unmanaged": self._on_remove_unmanaged,
            "on_repair": self._on_repair,
        }
        for disc in discrepancies:
            self._list_box.append(build_discrepancy_row(disc, disc_callbacks))

    def _toast(self, message: str) -> None:
        self._toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))

    # --- row actions ---
    def _on_run_now(self, slug: str) -> None:
        actions.run_now(slug)
        self._toast("Job started")
        self.refresh()

    def _on_view_log(self, slug: str) -> None:
        job = load_job(slug)
        LogViewDialog(job.name, job.log_path).present(self)

    def _on_toggle_pause(self, slug: str) -> None:
        job = load_job(slug)
        actions.set_enabled(job, not job.enabled)
        self._toast("Job paused" if not job.enabled else "Job resumed")
        self.refresh()

    def _on_edit(self, slug: str) -> None:
        job = load_job(slug)
        JobFormDialog(self._on_job_saved, job=job).present(self)

    def _on_delete(self, slug: str) -> None:
        job = load_job(slug)
        dialog = Adw.AlertDialog(
            heading=f"Delete “{job.name}”?",
            body="This removes the scheduled job and its systemd units. "
            "Nothing already backed up is touched.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dlg, response):
            if response == "delete":
                actions.delete_job_and_units(slug)
                self._toast("Job deleted")
                self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_remove_unmanaged(self, slug: str) -> None:
        actions.remove_unmanaged_unit(slug)
        self._toast("Unit removed")
        self.refresh()

    def _on_repair(self, slug: str) -> None:
        job = load_job(slug)
        actions.repair_units(job)
        self._toast("Units regenerated")
        self.refresh()

    def _on_add_job(self, _button) -> None:
        JobFormDialog(self._on_job_saved).present(self)

    def _on_job_saved(self, job, _acknowledged: bool) -> None:
        actions.save_and_apply(job)
        self._toast("Job saved")
        self.refresh()
