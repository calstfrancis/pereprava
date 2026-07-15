"""Main application window: job list + status polling."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from pereprava import __version__ as _APP_VERSION
from pereprava.logic import actions, discovery, import_export
from pereprava.logic.slug import unique_slug
from pereprava.model.status import RunState
from pereprava.ui.changelog_view import show_changelog
from pereprava.ui.history_view import HistoryViewDialog
from pereprava.ui.job_form import JobFormDialog
from pereprava.ui.job_row import build_discrepancy_row, build_job_row, build_section_header
from pereprava.ui.log_view import LogViewDialog
from pereprava.storage import app_state, history, logs
from pereprava.storage.jobs_store import list_job_slugs, load_job

REFRESH_INTERVAL_SECONDS = 8


def _set_toggle_label(button: Gtk.Button, name: str, active: bool) -> None:
    """Name-as-label toggle: state shown by font weight alone, not an icon/switch."""
    label = button.get_child()
    if isinstance(label, Gtk.Label):
        label.set_markup(f"<b>{name}</b>" if active else name)
    button.update_state([Gtk.AccessibleState.PRESSED], [active])


class AppWindow(Adw.ApplicationWindow):
    def __init__(self, application):
        super().__init__(application=application)
        self.set_title("Pereprava")
        self.set_default_size(760, 600)

        self._is_active = True
        self._auto_refresh_enabled = True
        self._last_states: dict[str, RunState] = {}
        self.connect("notify::is-active", self._on_is_active_changed)

        self._toast_overlay = Adw.ToastOverlay()
        self.set_content(self._toast_overlay)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        header.set_title_widget(Adw.WindowTitle(title="Pereprava", subtitle=""))

        add_button = Gtk.Button(icon_name="list-add-symbolic")
        add_button.set_tooltip_text("Add Job (Ctrl+N)")
        add_button.connect("clicked", self._on_add_job)
        header.pack_start(add_button)

        export_button = Gtk.Button(icon_name="document-save-symbolic")
        export_button.set_tooltip_text("Export Jobs…")
        export_button.connect("clicked", self._on_export_jobs)
        header.pack_start(export_button)

        import_button = Gtk.Button(icon_name="document-open-symbolic")
        import_button.set_tooltip_text("Import Jobs…")
        import_button.connect("clicked", self._on_import_jobs)
        header.pack_start(import_button)

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh (Ctrl+R)")
        refresh_button.connect("clicked", lambda _b: self.refresh())
        header.pack_end(refresh_button)

        toolbar_view.add_top_bar(header)

        add_job_action = Gio.SimpleAction.new("add-job", None)
        add_job_action.connect("activate", lambda *_a: self._on_add_job(None))
        self.add_action(add_job_action)
        refresh_action = Gio.SimpleAction.new("refresh", None)
        refresh_action.connect("activate", lambda *_a: self.refresh())
        self.add_action(refresh_action)
        application.set_accels_for_action("win.add-job", ["<Control>n"])
        application.set_accels_for_action("win.refresh", ["<Control>r"])

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

        status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_bar.set_margin_start(12)
        status_bar.set_margin_end(12)
        status_bar.set_margin_top(4)
        status_bar.set_margin_bottom(4)

        self._auto_refresh_btn = Gtk.Button()
        self._auto_refresh_btn.set_child(Gtk.Label(label="auto-refresh"))
        self._auto_refresh_btn.add_css_class("flat")
        self._auto_refresh_btn.add_css_class("status-toggle")
        self._auto_refresh_btn.set_tooltip_text(
            "Automatically refresh job status every 8 seconds while the window is focused"
        )
        self._auto_refresh_btn.connect("clicked", self._on_auto_refresh_clicked)
        _set_toggle_label(self._auto_refresh_btn, "auto-refresh", self._auto_refresh_enabled)
        status_bar.append(self._auto_refresh_btn)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        status_bar.append(spacer)

        version_btn = Gtk.Button(label=f"v{_APP_VERSION}")
        version_btn.add_css_class("flat")
        version_btn.add_css_class("dim-label")
        version_btn.add_css_class("caption")
        version_btn.set_tooltip_text("View changelog")
        version_btn.connect("clicked", lambda _b: show_changelog(self, _APP_VERSION))
        status_bar.append(version_btn)

        toolbar_view.add_bottom_bar(status_bar)

        self.refresh()
        GLib.timeout_add_seconds(REFRESH_INTERVAL_SECONDS, self._on_refresh_tick)
        GLib.idle_add(self._maybe_show_whats_new)

    def _maybe_show_whats_new(self) -> bool:
        last_seen = app_state.get_last_seen_version()
        if last_seen != _APP_VERSION:
            if last_seen is not None:  # skip the very first run — nothing to be "new" against
                show_changelog(self, _APP_VERSION)
            app_state.set_last_seen_version(_APP_VERSION)
        return GLib.SOURCE_REMOVE

    def _on_is_active_changed(self, *_args) -> None:
        self._is_active = self.is_active()

    def _on_refresh_tick(self) -> bool:
        if self._is_active and self._auto_refresh_enabled:
            self.refresh()
        return True  # keep the timeout registered

    def _on_auto_refresh_clicked(self, _button) -> None:
        self._auto_refresh_enabled = not self._auto_refresh_enabled
        _set_toggle_label(self._auto_refresh_btn, "auto-refresh", self._auto_refresh_enabled)

    def refresh(self) -> None:
        entries, discrepancies = discovery.scan()
        self._notify_on_failures(entries)
        for entry in entries:
            logs.rotate_if_needed(entry.job.log_path)
            if not entry.job.is_mount:
                history.record_if_new(entry.job.slug, entry.status)

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
            "on_duplicate": self._on_duplicate,
            "on_restore": self._on_restore,
            "on_view_history": self._on_view_history,
        }
        for entry in entries:
            self._list_box.append(build_job_row(entry, callbacks))

        if discrepancies:
            self._list_box.append(build_section_header(f"Needs attention ({len(discrepancies)})"))
        disc_callbacks = {
            "on_remove_unmanaged": self._on_remove_unmanaged,
            "on_repair": self._on_repair,
        }
        for disc in discrepancies:
            self._list_box.append(build_discrepancy_row(disc, disc_callbacks))

    def _toast(self, message: str) -> None:
        self._toast_overlay.add_toast(Adw.Toast(title=message, timeout=3))

    def _show_error_dialog(self, heading: str, body: str) -> None:
        alert = Adw.AlertDialog(heading=heading, body=body)
        alert.add_response("ok", "OK")
        alert.present(self)

    def _notify_on_failures(self, entries) -> None:
        """Send a desktop notification the moment a job transitions into FAILED,
        not on every refresh tick while it stays failed."""
        seen_slugs = set()
        for entry in entries:
            slug = entry.job.slug
            seen_slugs.add(slug)
            state = entry.status.state
            previous = self._last_states.get(slug)
            if state == RunState.FAILED and previous != RunState.FAILED:
                verb = "Mount failed" if entry.job.is_mount else "Job failed"
                notification = Gio.Notification.new(f"{verb}: {entry.job.name}")
                notification.set_body(entry.job.destination)
                notification.set_priority(Gio.NotificationPriority.HIGH)
                self.get_application().send_notification(f"pereprava-job-{slug}", notification)
            self._last_states[slug] = state
        # Drop tracking for jobs that were deleted since the last refresh.
        for slug in list(self._last_states):
            if slug not in seen_slugs:
                del self._last_states[slug]

    def _on_export_jobs(self, _button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(f"pereprava-jobs-{datetime.now():%Y%m%d}.json")

        def on_response(dlg, result):
            try:
                file = dlg.save_finish(result)
            except GLib.Error:
                return
            if not file:
                return
            try:
                count = import_export.export_jobs(Path(file.get_path()))
            except OSError as exc:
                self._toast(f"Export failed: {exc}")
                return
            self._toast(f"Exported {count} job(s)")

        dialog.save(self, None, on_response)

    def _on_import_jobs(self, _button) -> None:
        dialog = Gtk.FileDialog()

        def on_response(dlg, result):
            try:
                file = dlg.open_finish(result)
            except GLib.Error:
                return
            if not file:
                return
            try:
                imported, errors = import_export.import_jobs(Path(file.get_path()))
            except (OSError, ValueError) as exc:
                self._toast(f"Import failed: {exc}")
                return
            self._toast(f"Imported {imported} job(s)")
            if errors:
                alert = Adw.AlertDialog(
                    heading="Some jobs couldn't be imported",
                    body="\n".join(errors),
                )
                alert.add_response("ok", "OK")
                alert.present(self)
            self.refresh()

        dialog.open(self, None, on_response)

    # --- row actions ---
    def _on_run_now(self, slug: str) -> None:
        job = load_job(slug)
        ok, error = actions.run_now(slug)
        if ok:
            self._toast("Job started")
        else:
            self._show_error_dialog(f"Couldn't start “{job.name}”", error)
        self.refresh()

    def _on_view_log(self, slug: str) -> None:
        job = load_job(slug)
        LogViewDialog(job.name, job.log_path).present(self)

    def _on_view_history(self, slug: str) -> None:
        job = load_job(slug)
        HistoryViewDialog(job.name, slug).present(self)

    @staticmethod
    def _default_log_path(slug: str) -> str:
        return str(Path.home() / ".local" / "state" / "pereprava" / f"{slug}.log")

    def _on_duplicate(self, slug: str) -> None:
        job = load_job(slug)
        new_slug = unique_slug(f"{job.name} (copy)", set(list_job_slugs()))
        duplicate = replace(
            job,
            slug=new_slug,
            name=f"{job.name} (copy)",
            enabled=False,
            log_path=self._default_log_path(new_slug),
        )
        dialog = JobFormDialog(self._on_job_saved, job=duplicate)
        dialog.set_title("Duplicate Job")
        dialog.present(self)

    def _on_restore(self, slug: str) -> None:
        job = load_job(slug)
        new_slug = unique_slug(f"Restore from {job.name}", set(list_job_slugs()))
        restore_job = replace(
            job,
            slug=new_slug,
            name=f"Restore from {job.name}",
            source=job.destination,
            destination=job.source,
            enabled=False,
            log_path=self._default_log_path(new_slug),
        )
        dialog = JobFormDialog(self._on_job_saved, job=restore_job)
        dialog.set_title("Restore — review before saving")
        dialog.present(self)

    def _on_toggle_pause(self, slug: str) -> None:
        job = load_job(slug)
        target_enabled = not job.enabled
        ok, error = actions.set_enabled(job, target_enabled)
        if ok:
            self._toast("Job paused" if not target_enabled else "Job resumed")
        else:
            verb = "resume" if target_enabled else "pause"
            self._show_error_dialog(f"Couldn't {verb} “{job.name}”", error)
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
                ok, error = actions.delete_job_and_units(job)
                if ok:
                    self._toast("Job deleted")
                else:
                    self._toast("Job deleted, but stopping its unit failed")
                    self._show_error_dialog(f"Couldn't stop “{job.name}”'s unit", error)
                self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_remove_unmanaged(self, slug: str, unit_name: str) -> None:
        dialog = Adw.AlertDialog(
            heading=f"Remove “{unit_name}”?",
            body="This unit isn't managed by Pereprava. It will be disabled, "
            "stopped, and its unit file deleted.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("remove", "Remove")
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(_dlg, response):
            if response == "remove":
                actions.remove_unmanaged_unit(slug, unit_name)
                self._toast("Unit removed")
                self.refresh()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _on_repair(self, slug: str) -> None:
        job = load_job(slug)
        ok, error = actions.repair_units(job)
        if ok:
            self._toast("Units regenerated")
        else:
            self._show_error_dialog(f"Couldn't repair “{job.name}”", error)
        self.refresh()

    def _on_add_job(self, _button) -> None:
        JobFormDialog(self._on_job_saved).present(self)

    def _on_job_saved(self, job, _acknowledged: bool) -> None:
        ok, error = actions.save_and_apply(job)
        if ok:
            self._toast("Job saved")
        else:
            self._show_error_dialog(f"“{job.name}” was saved, but couldn't be started", error)
        self.refresh()
