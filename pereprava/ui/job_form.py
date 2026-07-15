"""Add/Edit job dialog. Save is gated on validate_job() — never trusts UI-only state."""

from __future__ import annotations

import shlex
import subprocess
import threading
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from pereprava.logic import dry_run
from pereprava.logic.rc import RC_CAPABLE_TYPES, allocate_port
from pereprava.logic.schedule import PRESET_LABELS, preset_to_on_calendar, validate_on_calendar
from pereprava.logic.slug import unique_slug
from pereprava.logic.validation import validate_job
from pereprava.model.job import JOB_TYPE_LABELS, Job, JobType, Schedule
from pereprava.storage import linger
from pereprava.storage.jobs_store import list_job_slugs, load_all_jobs
from pereprava.storage.rclone import list_remotes
from pereprava.ui.remote_browser import RemoteBrowserDialog

_REMOTE_CHECK_DEBOUNCE_MS = 400

_RCLONE_TYPES = {JobType.RCLONE_COPY, JobType.RCLONE_SYNC, JobType.RCLONE_BISYNC, JobType.RCLONE_CHECK}
_NEVER_DESTRUCTIVE_TYPES = {JobType.RCLONE_COPY, JobType.RCLONE_MOUNT, JobType.RCLONE_CHECK}

_JOB_TYPES = list(JOB_TYPE_LABELS.keys())
_PRESETS = ["hourly", "every6h", "daily", "weekly", "custom"]


class JobFormDialog(Adw.Dialog):
    def __init__(self, on_save: Callable[[Job, bool], None], job: Job | None = None):
        super().__init__()
        self._on_save = on_save
        self._editing = job
        self._remote_check_source_id: int | None = None
        self._test_proc: subprocess.Popen | None = None
        self._test_cancelled = False
        self.connect("closed", self._on_dialog_closed)
        self.set_content_width(560)
        self.set_content_height(680)
        self.set_title("Edit Job" if job else "Add Job")

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        self._save_button = Gtk.Button(label="Save")
        self._save_button.add_css_class("suggested-action")
        self._save_button.connect("clicked", self._on_save_clicked)
        header.pack_end(self._save_button)
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda _b: self.close())
        header.pack_start(cancel_button)
        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        page = Adw.PreferencesPage()
        scrolled.set_child(page)
        toolbar_view.set_content(scrolled)
        self.set_child(toolbar_view)

        self._error_banner = Adw.Banner()
        self._error_banner.set_revealed(False)

        # --- Basics ---
        basics = Adw.PreferencesGroup(title="Basics")
        page.add(basics)

        self._name_row = Adw.EntryRow(title="Name")
        basics.add(self._name_row)

        self._type_row = Adw.ComboRow(title="Job type")
        self._type_row.set_model(Gtk.StringList.new([JOB_TYPE_LABELS[t] for t in _JOB_TYPES]))
        self._type_row.connect("notify::selected", self._on_type_changed)
        basics.add(self._type_row)

        # --- Source / destination ---
        paths = Adw.PreferencesGroup(title="Paths")
        page.add(paths)
        self._paths_group = paths

        self._source_row = Adw.EntryRow(title="Source")
        source_pick = Gtk.Button(icon_name="folder-open-symbolic")
        source_pick.set_valign(Gtk.Align.CENTER)
        source_pick.connect("clicked", self._pick_source_folder)
        self._source_row.add_suffix(source_pick)
        self._source_pick_button = source_pick
        source_browse = Gtk.Button(icon_name="folder-remote-symbolic")
        source_browse.set_valign(Gtk.Align.CENTER)
        source_browse.set_tooltip_text("Browse a configured rclone remote")
        source_browse.connect("clicked", self._pick_remote_source)
        source_browse.set_visible(False)
        self._source_row.add_suffix(source_browse)
        self._source_browse_button = source_browse
        self._source_row.connect("changed", self._schedule_remote_check)
        paths.add(self._source_row)

        self._destination_row = Adw.EntryRow(title="Destination (remote:path or local path)")
        dest_browse = Gtk.Button(icon_name="folder-remote-symbolic")
        dest_browse.set_valign(Gtk.Align.CENTER)
        dest_browse.set_tooltip_text("Browse a configured rclone remote")
        dest_browse.connect("clicked", self._pick_remote_destination)
        self._destination_row.add_suffix(dest_browse)
        self._dest_browse_button = dest_browse
        dest_pick = Gtk.Button(icon_name="folder-open-symbolic")
        dest_pick.set_valign(Gtk.Align.CENTER)
        dest_pick.set_tooltip_text("Choose a local mount point folder")
        dest_pick.connect("clicked", self._pick_mount_point)
        dest_pick.set_visible(False)
        self._destination_row.add_suffix(dest_pick)
        self._dest_pick_button = dest_pick
        self._destination_row.connect("changed", self._schedule_remote_check)
        paths.add(self._destination_row)

        self._custom_command_row = Adw.EntryRow(title="Custom command (space-separated)")
        paths.add(self._custom_command_row)

        self._excludes_row = Adw.EntryRow(
            title="Exclude folders/files (space-separated glob patterns)"
        )
        self._excludes_row.set_tooltip_text(
            'e.g. *.tmp "node_modules/**" .cache/** — quote patterns containing spaces'
        )
        paths.add(self._excludes_row)

        self._includes_row = Adw.EntryRow(
            title="Include only folders/files (space-separated glob patterns)"
        )
        self._includes_row.set_tooltip_text(
            "Applied after Exclude — combined per rclone/rsync's normal filter-rule "
            "order (first match wins). Leave blank to include everything not excluded."
        )
        paths.add(self._includes_row)

        self._bwlimit_row = Adw.EntryRow(title="Bandwidth limit (optional)")
        self._bwlimit_row.set_tooltip_text(
            "e.g. 10M for a flat cap, or rclone's own \"08:00,512k 20:00,10M\" "
            "time-of-day schedule (rclone jobs only — rsync only supports a flat rate)"
        )
        paths.add(self._bwlimit_row)

        self._rc_progress_row = Adw.SwitchRow(title="Show live progress")
        self._rc_progress_row.set_tooltip_text(
            "Starts rclone's own --rc control API on a local, loopback-only port "
            "(chosen automatically) so the job list can show real transfer progress"
        )
        paths.add(self._rc_progress_row)

        self._extra_args_row = Adw.EntryRow(title="Extra arguments (space-separated)")
        paths.add(self._extra_args_row)

        self._remote_hint_label = Gtk.Label(label="")
        self._remote_hint_label.add_css_class("pereprava-hint-warning")
        self._remote_hint_label.set_wrap(True)
        self._remote_hint_label.set_xalign(0.0)
        self._remote_hint_label.set_margin_start(8)
        self._remote_hint_label.set_margin_top(4)
        self._remote_hint_label.set_visible(False)
        paths.add(self._remote_hint_label)

        test_job_row = Adw.ActionRow(title="Test (dry run)")
        test_job_row.set_subtitle("Preview what this job would do — nothing is changed")
        self._test_job_button = Gtk.Button(label="Test")
        self._test_job_button.set_valign(Gtk.Align.CENTER)
        self._test_job_button.connect("clicked", self._on_test_job)
        test_job_row.add_suffix(self._test_job_button)
        self._test_cancel_button = Gtk.Button(label="Cancel")
        self._test_cancel_button.set_valign(Gtk.Align.CENTER)
        self._test_cancel_button.connect("clicked", self._on_cancel_test_job)
        self._test_cancel_button.set_visible(False)
        test_job_row.add_suffix(self._test_cancel_button)
        paths.add(test_job_row)

        self._test_result_view = Gtk.TextView()
        self._test_result_view.set_editable(False)
        self._test_result_view.set_monospace(True)
        self._test_result_view.set_cursor_visible(False)
        self._test_result_view.set_left_margin(8)
        self._test_result_view.set_top_margin(6)
        self._test_result_view.set_bottom_margin(6)
        test_result_scroll = Gtk.ScrolledWindow()
        test_result_scroll.set_min_content_height(110)
        test_result_scroll.set_max_content_height(110)
        test_result_scroll.set_child(self._test_result_view)
        test_result_scroll.add_css_class("card")
        test_result_scroll.set_visible(False)
        self._test_result_scroll = test_result_scroll
        paths.add(test_result_scroll)

        # --- Safety ---
        safety = Adw.PreferencesGroup(title="Safety")
        page.add(safety)
        self._safety_group = safety

        self._rsync_delete_row = Adw.SwitchRow(
            title="Delete extraneous files at destination (--delete)",
        )
        self._rsync_delete_row.connect("notify::active", lambda *_a: self._update_destructive_ui())
        safety.add(self._rsync_delete_row)

        self._destructive_banner = Adw.Banner()
        self._destructive_banner.set_title("This job can delete files at the destination")
        self._destructive_banner.set_revealed(False)
        safety.add(self._destructive_banner)

        self._ack_row = Adw.ActionRow(title="I understand this job can delete files")
        self._ack_check = Gtk.CheckButton()
        self._ack_check.connect("toggled", lambda *_a: self._refresh_save_sensitivity())
        self._ack_row.add_prefix(self._ack_check)
        self._ack_row.set_activatable_widget(self._ack_check)
        safety.add(self._ack_row)

        # --- Startup (mount jobs only) ---
        self._startup_group = Adw.PreferencesGroup(title="Startup")
        page.add(self._startup_group)

        self._linger_banner = Adw.Banner()
        self._linger_banner.set_title("Enable lingering to start this mount at boot without logging in")
        self._linger_banner.set_button_label("Enable")
        self._linger_banner.connect("button-clicked", self._on_enable_linger)
        self._startup_group.add(self._linger_banner)

        # --- Hooks ---
        hooks_group = Adw.PreferencesGroup(title="Hooks")
        page.add(hooks_group)

        self._pre_hook_row = Adw.EntryRow(title="Run before (shell command, optional)")
        hooks_group.add(self._pre_hook_row)

        self._post_hook_row = Adw.EntryRow(title="Run after, on success (shell command, optional)")
        self._post_hook_row.set_tooltip_text(
            "Runs only if the main command succeeds — stock systemd ExecStartPost "
            "semantics. For a hook that must always run, build that into the command itself."
        )
        hooks_group.add(self._post_hook_row)

        # --- Run Conditions ---
        conditions_group = Adw.PreferencesGroup(title="Run Conditions")
        page.add(conditions_group)

        self._ac_power_row = Adw.SwitchRow(title="Only run on AC power")
        conditions_group.add(self._ac_power_row)

        self._ssid_row = Adw.EntryRow(title="Only run on this Wi-Fi network (SSID, optional)")
        self._ssid_row.set_tooltip_text("Checked via nmcli — skipped cleanly (not a failure) off that network")
        conditions_group.add(self._ssid_row)

        # --- Schedule ---
        schedule_group = Adw.PreferencesGroup(title="Schedule")
        self._schedule_group = schedule_group
        page.add(schedule_group)

        self._preset_row = Adw.ComboRow(title="Runs")
        self._preset_row.set_model(Gtk.StringList.new([PRESET_LABELS[p] for p in _PRESETS]))
        self._preset_row.set_selected(_PRESETS.index("daily"))
        self._preset_row.connect("notify::selected", self._on_preset_changed)
        schedule_group.add(self._preset_row)

        self._custom_calendar_row = Adw.EntryRow(title="Custom OnCalendar= value")
        schedule_group.add(self._custom_calendar_row)

        test_row = Adw.ActionRow(title="Preview schedule")
        test_button = Gtk.Button(label="Test")
        test_button.set_valign(Gtk.Align.CENTER)
        test_button.connect("clicked", self._on_test_schedule)
        test_row.add_suffix(test_button)
        schedule_group.add(test_row)
        self._schedule_preview_row = Adw.ActionRow(title="")
        self._schedule_preview_row.set_visible(False)
        schedule_group.add(self._schedule_preview_row)

        # --- Logging ---
        log_group = Adw.PreferencesGroup(title="Logging")
        page.add(log_group)
        self._log_path_row = Adw.EntryRow(title="Log file")
        log_pick = Gtk.Button(icon_name="folder-open-symbolic")
        log_pick.set_valign(Gtk.Align.CENTER)
        log_pick.set_tooltip_text("Choose a log file location")
        log_pick.connect("clicked", self._pick_log_file)
        self._log_path_row.add_suffix(log_pick)
        log_group.add(self._log_path_row)

        # --- Errors ---
        errors_group = Adw.PreferencesGroup()
        page.add(errors_group)
        self._errors_label = Gtk.Label(label="")
        self._errors_label.add_css_class("error")
        self._errors_label.set_wrap(True)
        self._errors_label.set_xalign(0.0)
        self._errors_label.set_visible(False)
        errors_group.add(self._errors_label)

        self._existing_slugs = set(list_job_slugs())
        if job:
            self._existing_slugs.discard(job.slug)
            self._populate(job)
        else:
            self._preset_row.set_selected(_PRESETS.index("daily"))

        self._on_type_changed()
        self._on_preset_changed()
        self._update_destructive_ui()

    # --- populate for edit ---
    def _populate(self, job: Job) -> None:
        self._name_row.set_text(job.name)
        self._type_row.set_selected(_JOB_TYPES.index(job.job_type))
        self._source_row.set_text(job.source)
        self._destination_row.set_text(job.destination)
        self._custom_command_row.set_text(shlex.join(job.custom_command or []))
        self._excludes_row.set_text(shlex.join(job.excludes))
        self._includes_row.set_text(shlex.join(job.includes))
        self._bwlimit_row.set_text(job.bwlimit)
        self._rc_progress_row.set_active(job.rc_port > 0)
        self._extra_args_row.set_text(shlex.join(job.extra_args))
        self._pre_hook_row.set_text(job.pre_hook)
        self._post_hook_row.set_text(job.post_hook)
        self._ac_power_row.set_active(job.condition_ac_power)
        self._ssid_row.set_text(job.condition_ssid)
        self._rsync_delete_row.set_active(job.rsync_delete)
        self._log_path_row.set_text(job.log_path)
        preset = job.schedule.preset if job.schedule.preset in _PRESETS else "custom"
        self._preset_row.set_selected(_PRESETS.index(preset))
        self._custom_calendar_row.set_text(job.schedule.on_calendar)

    # --- selection helpers ---
    def _selected_type(self) -> JobType:
        return _JOB_TYPES[self._type_row.get_selected()]

    def _selected_preset(self) -> str:
        return _PRESETS[self._preset_row.get_selected()]

    def _on_type_changed(self, *_args) -> None:
        job_type = self._selected_type()
        is_mount = job_type == JobType.RCLONE_MOUNT
        self._destination_row.set_visible(job_type != JobType.CUSTOM)
        self._custom_command_row.set_visible(job_type == JobType.CUSTOM)
        self._excludes_row.set_visible(job_type != JobType.CUSTOM)
        self._includes_row.set_visible(job_type != JobType.CUSTOM)
        self._bwlimit_row.set_visible(job_type != JobType.CUSTOM)
        self._rc_progress_row.set_visible(job_type in RC_CAPABLE_TYPES)
        self._rsync_delete_row.set_visible(job_type == JobType.RSYNC)
        self._dest_browse_button.set_visible(job_type in _RCLONE_TYPES)
        self._safety_group.set_visible(job_type not in _NEVER_DESTRUCTIVE_TYPES)
        self._schedule_group.set_visible(not is_mount)
        self._startup_group.set_visible(is_mount)

        # For a mount, source is the rclone remote and destination is the local
        # mount point — the reverse of copy/sync jobs — so the two path-picker
        # buttons swap which row they appear on.
        self._source_row.set_title("Remote (e.g. pcloud:path)" if is_mount else "Source")
        self._destination_row.set_title(
            "Mount point (local folder)" if is_mount else "Destination (remote:path or local path)"
        )
        self._source_pick_button.set_visible(not is_mount)
        self._source_browse_button.set_visible(is_mount)
        self._dest_pick_button.set_visible(is_mount)
        if is_mount:
            self._dest_browse_button.set_visible(False)
            self._refresh_linger_banner()

        self._update_destructive_ui()
        self._schedule_remote_check()

    def _on_preset_changed(self, *_args) -> None:
        is_custom = self._selected_preset() == "custom"
        self._custom_calendar_row.set_visible(is_custom)
        if not is_custom:
            self._custom_calendar_row.set_text(preset_to_on_calendar(self._selected_preset()))

    def _is_destructive(self) -> bool:
        job_type = self._selected_type()
        if job_type in _NEVER_DESTRUCTIVE_TYPES:
            return False
        if job_type == JobType.RSYNC:
            return self._rsync_delete_row.get_active()
        return True  # sync, bisync, custom

    def _update_destructive_ui(self) -> None:
        destructive = self._is_destructive()
        self._destructive_banner.set_revealed(destructive)
        self._ack_row.set_visible(destructive)
        if not destructive:
            self._ack_check.set_active(False)
        self._refresh_save_sensitivity()

    def _refresh_save_sensitivity(self) -> None:
        self._save_button.set_sensitive(not self._is_destructive() or self._ack_check.get_active())

    def _pick_source_folder(self, _button) -> None:
        dialog = Gtk.FileDialog()

        def on_response(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            if folder:
                self._source_row.set_text(folder.get_path())

        dialog.select_folder(self.get_root(), None, on_response)

    def _pick_log_file(self, _button) -> None:
        dialog = Gtk.FileDialog()
        current = self._log_path_row.get_text().strip()
        current_path = Path(current) if current else None
        if current_path:
            if current_path.parent.is_dir():
                dialog.set_initial_folder(Gio.File.new_for_path(str(current_path.parent)))
            dialog.set_initial_name(current_path.name)

        def on_response(dlg, result):
            try:
                file = dlg.save_finish(result)
            except GLib.Error:
                return
            if file:
                self._log_path_row.set_text(file.get_path())

        dialog.save(self.get_root(), None, on_response)

    def _pick_remote_destination(self, _button) -> None:
        current = self._destination_row.get_text().strip()
        initial_remote = current.split(":", 1)[0] + ":" if ":" in current else None

        def on_select(remote_path: str) -> None:
            self._destination_row.set_text(remote_path)

        RemoteBrowserDialog(on_select, initial_remote=initial_remote).present(self)

    def _pick_remote_source(self, _button) -> None:
        current = self._source_row.get_text().strip()
        initial_remote = current.split(":", 1)[0] + ":" if ":" in current else None

        def on_select(remote_path: str) -> None:
            self._source_row.set_text(remote_path)

        RemoteBrowserDialog(on_select, initial_remote=initial_remote).present(self)

    def _pick_mount_point(self, _button) -> None:
        dialog = Gtk.FileDialog()

        def on_response(dlg, result):
            try:
                folder = dlg.select_folder_finish(result)
            except GLib.Error:
                return
            if folder:
                self._destination_row.set_text(folder.get_path())

        dialog.select_folder(self.get_root(), None, on_response)

    def _refresh_linger_banner(self) -> None:
        enabled = linger.is_enabled()
        self._linger_banner.set_revealed(not enabled)

    def _on_enable_linger(self, _banner) -> None:
        if linger.enable():
            self._linger_banner.set_revealed(False)
        else:
            self._linger_banner.set_title(
                "Couldn't enable lingering — run `loginctl enable-linger` yourself"
            )

    def _on_dialog_closed(self, *_args) -> None:
        if self._remote_check_source_id is not None:
            GLib.source_remove(self._remote_check_source_id)
            self._remote_check_source_id = None
        if self._test_proc is not None and self._test_proc.poll() is None:
            self._test_proc.terminate()

    def _schedule_remote_check(self, *_args) -> None:
        if self._remote_check_source_id is not None:
            GLib.source_remove(self._remote_check_source_id)
        self._remote_check_source_id = GLib.timeout_add(
            _REMOTE_CHECK_DEBOUNCE_MS, self._check_remote_field
        )

    def _check_remote_field(self) -> bool:
        self._remote_check_source_id = None
        job_type = self._selected_type()

        text = None
        if job_type == JobType.RCLONE_MOUNT:
            text = self._source_row.get_text().strip()
        elif job_type in _RCLONE_TYPES:
            text = self._destination_row.get_text().strip()

        if not text or ":" not in text:
            self._remote_hint_label.set_visible(False)
            return GLib.SOURCE_REMOVE

        remote = text.split(":", 1)[0] + ":"
        remotes = list_remotes()
        if not remotes:
            self._remote_hint_label.set_text(
                "No configured rclone remotes found — check `rclone listremotes`."
            )
            self._remote_hint_label.set_visible(True)
        elif remote not in remotes:
            self._remote_hint_label.set_text(
                f"Remote “{remote}” isn't in `rclone listremotes` — check the name or configure it first."
            )
            self._remote_hint_label.set_visible(True)
        else:
            self._remote_hint_label.set_visible(False)

        return GLib.SOURCE_REMOVE

    def _on_test_job(self, _button) -> None:
        job = self._build_job()
        reason = dry_run.unsupported_reason(job)
        if reason:
            self._test_result_scroll.set_visible(True)
            self._test_result_view.get_buffer().set_text("✗ " + reason)
            return

        self._test_job_button.set_sensitive(False)
        self._test_cancel_button.set_visible(True)
        self._test_result_scroll.set_visible(True)
        self._test_result_view.get_buffer().set_text(
            "Testing… large or deeply-nested remotes can take a while; cancel any time."
        )
        self._test_cancelled = False

        def worker() -> None:
            proc = dry_run.start_test(job)
            self._test_proc = proc
            stdout, stderr = proc.communicate()
            if self._test_cancelled:
                return  # _on_cancel_test_job already updated the UI
            ok, message = dry_run.interpret_result(job, proc.returncode, stdout, stderr)
            GLib.idle_add(self._on_test_job_done, ok, message)

        threading.Thread(target=worker, daemon=True).start()

    def _on_cancel_test_job(self, _button) -> None:
        self._test_cancelled = True
        if self._test_proc is not None and self._test_proc.poll() is None:
            self._test_proc.terminate()
        self._test_proc = None
        self._test_job_button.set_sensitive(True)
        self._test_cancel_button.set_visible(False)
        self._test_result_view.get_buffer().set_text("Cancelled.")

    def _on_test_job_done(self, ok: bool, message: str) -> bool:
        self._test_proc = None
        self._test_job_button.set_sensitive(True)
        self._test_cancel_button.set_visible(False)
        prefix = "✓ " if ok else "✗ "
        self._test_result_view.get_buffer().set_text(prefix + message)
        return GLib.SOURCE_REMOVE

    def _on_test_schedule(self, _button) -> None:
        value = self._custom_calendar_row.get_text() if self._custom_calendar_row.get_visible() else preset_to_on_calendar(self._selected_preset())
        ok, message = validate_on_calendar(value)
        self._schedule_preview_row.set_visible(True)
        self._schedule_preview_row.set_title(message if ok else f"Invalid: {message}")

    def _resolve_rc_port(self, job_type: JobType) -> int:
        """0 if live progress isn't enabled/applicable; otherwise the existing
        port when editing (stable across saves) or a freshly allocated one."""
        if not self._rc_progress_row.get_active() or job_type not in RC_CAPABLE_TYPES:
            return 0
        if self._editing and self._editing.rc_port:
            return self._editing.rc_port
        taken = {j.rc_port for j in load_all_jobs() if j.rc_port}
        return allocate_port(taken)

    def _build_job(self) -> Job:
        job_type = self._selected_type()
        name = self._name_row.get_text().strip()
        slug = self._editing.slug if self._editing else unique_slug(name, self._existing_slugs)
        preset = self._selected_preset()
        on_calendar = (
            self._custom_calendar_row.get_text()
            if preset == "custom"
            else preset_to_on_calendar(preset)
        )
        return Job(
            slug=slug,
            name=name,
            job_type=job_type,
            source=self._source_row.get_text().strip(),
            destination=self._destination_row.get_text().strip(),
            extra_args=shlex.split(self._extra_args_row.get_text()),
            excludes=shlex.split(self._excludes_row.get_text()) if job_type != JobType.CUSTOM else [],
            includes=shlex.split(self._includes_row.get_text()) if job_type != JobType.CUSTOM else [],
            bwlimit=self._bwlimit_row.get_text().strip() if job_type != JobType.CUSTOM else "",
            rc_port=self._resolve_rc_port(job_type),
            pre_hook=self._pre_hook_row.get_text().strip(),
            post_hook=self._post_hook_row.get_text().strip(),
            condition_ac_power=self._ac_power_row.get_active(),
            condition_ssid=self._ssid_row.get_text().strip(),
            custom_command=shlex.split(self._custom_command_row.get_text()) or None
            if job_type == JobType.CUSTOM
            else None,
            rsync_delete=self._rsync_delete_row.get_active(),
            schedule=Schedule(preset=preset, on_calendar=on_calendar),
            log_path=self._log_path_row.get_text().strip(),
            enabled=self._editing.enabled if self._editing else True,
        )

    def _on_save_clicked(self, _button) -> None:
        job = self._build_job()
        if not job.log_path:
            job.log_path = str(Path.home() / ".local" / "state" / "pereprava" / f"{job.slug}.log")
        acknowledged = self._ack_check.get_active()
        errors = validate_job(job, destructive_acknowledged=acknowledged)
        if errors:
            self._errors_label.set_text("\n".join(errors))
            self._errors_label.set_visible(True)
            return
        self._errors_label.set_visible(False)
        self._on_save(job, acknowledged)
        self.close()
