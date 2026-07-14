"""Guided pCloud remote setup: name it, click Authorize, approve in the browser.

Runs rclone's own headless OAuth recipe (`rclone authorize pcloud` -> `rclone
config create ... token ...`) off the GTK main thread so the dialog stays
responsive while waiting on the user's browser."""

from __future__ import annotations

import subprocess
import threading
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from pereprava.storage.rclone import create_pcloud_remote, extract_token, list_remotes, start_pcloud_authorize


class PcloudSetupDialog(Adw.Dialog):
    def __init__(self, on_created: Callable[[str], None]):
        super().__init__()
        self._on_created = on_created
        self._proc: subprocess.Popen | None = None
        self.set_content_width(440)
        self.set_title("Add pCloud Remote")
        self.connect("closed", self._on_closed)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda _b: self.close())
        header.pack_start(cancel_button)
        toolbar_view.add_top_bar(header)

        page = Adw.PreferencesPage()
        toolbar_view.set_content(page)
        self.set_child(toolbar_view)

        group = Adw.PreferencesGroup(
            title="Add pCloud Remote",
            description=(
                "Clicking Authorize opens pCloud's login in your browser. "
                "Approve access there — this dialog finishes automatically."
            ),
        )
        page.add(group)

        self._name_row = Adw.EntryRow(title="Remote name")
        self._name_row.set_text("pcloud")
        group.add(self._name_row)

        self._authorize_button = Gtk.Button(label="Authorize in Browser")
        self._authorize_button.add_css_class("suggested-action")
        self._authorize_button.set_halign(Gtk.Align.START)
        self._authorize_button.set_margin_top(8)
        self._authorize_button.connect("clicked", self._on_authorize_clicked)
        group.add(self._authorize_button)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_wrap(True)
        self._status_label.set_xalign(0.0)
        self._status_label.set_margin_top(4)
        self._status_label.set_visible(False)
        group.add(self._status_label)

        self._cancel_wait_button = Gtk.Button(label="Cancel Authorization")
        self._cancel_wait_button.set_halign(Gtk.Align.START)
        self._cancel_wait_button.connect("clicked", self._on_cancel_wait)
        self._cancel_wait_button.set_visible(False)
        group.add(self._cancel_wait_button)

    def _on_closed(self, *_args) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()

    def _on_authorize_clicked(self, _button) -> None:
        name = self._name_row.get_text().strip()
        if not name:
            self._set_status("Enter a remote name first.", is_error=True)
            return
        if name in {r.rstrip(":") for r in list_remotes()}:
            self._set_status(f"A remote named “{name}” already exists.", is_error=True)
            return

        self._authorize_button.set_sensitive(False)
        self._name_row.set_sensitive(False)
        self._cancel_wait_button.set_visible(True)
        self._set_status("Waiting for browser authorization…", is_error=False)

        def worker() -> None:
            proc = start_pcloud_authorize()
            self._proc = proc
            try:
                stdout, stderr = proc.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                GLib.idle_add(self._on_authorize_done, False, "Timed out waiting for authorization.", None)
                return
            if proc.returncode != 0:
                message = stderr.strip() or "Cancelled or failed before authorization completed."
                GLib.idle_add(self._on_authorize_done, False, message, None)
                return
            token = extract_token(stdout)
            if not token:
                GLib.idle_add(self._on_authorize_done, False, "Didn't get a token back from rclone.", None)
                return
            GLib.idle_add(self._on_authorize_done, True, "", (name, token))

        threading.Thread(target=worker, daemon=True).start()

    def _on_authorize_done(self, ok: bool, message: str, name_token) -> bool:
        self._proc = None
        if not ok:
            self._authorize_button.set_sensitive(True)
            self._name_row.set_sensitive(True)
            self._cancel_wait_button.set_visible(False)
            self._set_status(message, is_error=True)
            return GLib.SOURCE_REMOVE

        name, token = name_token
        self._set_status("Finishing setup…", is_error=False)
        ok, message = create_pcloud_remote(name, token)
        self._cancel_wait_button.set_visible(False)
        if ok:
            self._set_status(f"“{name}:” is ready to use.", is_error=False)
            self._on_created(name)
            self.close()
        else:
            self._authorize_button.set_sensitive(True)
            self._name_row.set_sensitive(True)
            self._set_status(message, is_error=True)
        return GLib.SOURCE_REMOVE

    def _on_cancel_wait(self, _button) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._authorize_button.set_sensitive(True)
        self._name_row.set_sensitive(True)
        self._cancel_wait_button.set_visible(False)
        self._set_status("Cancelled.", is_error=False)

    def _set_status(self, text: str, *, is_error: bool) -> None:
        self._status_label.set_text(text)
        self._status_label.set_visible(bool(text))
        if is_error:
            self._status_label.add_css_class("pereprava-hint-warning")
        else:
            self._status_label.remove_css_class("pereprava-hint-warning")
