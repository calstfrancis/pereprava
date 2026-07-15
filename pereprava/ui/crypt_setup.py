"""Guided encrypted-remote setup: wrap an existing remote:path in an rclone
`crypt` remote for client-side encryption before upload.

Runs `rclone obscure` (required — rclone config's password fields must already
be obscured when created non-interactively) then `rclone config create ...
crypt ...`, off the GTK main thread, same shape as the pCloud OAuth dialog."""

from __future__ import annotations

import threading
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from pereprava.storage.rclone import create_crypt_remote, list_remotes, obscure_password


class CryptSetupDialog(Adw.Dialog):
    def __init__(self, on_created: Callable[[str], None]):
        super().__init__()
        self._on_created = on_created
        self.set_content_width(440)
        self.set_title("Add Encrypted Remote")

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
            title="Add Encrypted Remote",
            description=(
                "Wraps an existing remote (or a folder on one) in client-side "
                "encryption — files are encrypted before they ever leave this machine."
            ),
        )
        page.add(group)

        self._name_row = Adw.EntryRow(title="Remote name")
        self._name_row.set_text("crypt")
        group.add(self._name_row)

        self._wrapped_row = Adw.EntryRow(title="Wrap remote:path")
        self._wrapped_row.set_tooltip_text("e.g. pcloud:Encrypted — must already exist as a configured remote")
        group.add(self._wrapped_row)

        self._password_row = Adw.PasswordEntryRow(title="Password")
        group.add(self._password_row)

        self._confirm_row = Adw.PasswordEntryRow(title="Confirm password")
        group.add(self._confirm_row)

        self._password2_row = Adw.PasswordEntryRow(title="Optional second password (filename salt)")
        group.add(self._password2_row)

        self._create_button = Gtk.Button(label="Create")
        self._create_button.add_css_class("suggested-action")
        self._create_button.set_halign(Gtk.Align.START)
        self._create_button.set_margin_top(8)
        self._create_button.connect("clicked", self._on_create_clicked)
        group.add(self._create_button)

        self._status_label = Gtk.Label(label="")
        self._status_label.set_wrap(True)
        self._status_label.set_xalign(0.0)
        self._status_label.set_margin_top(4)
        self._status_label.set_visible(False)
        group.add(self._status_label)

    def _set_status(self, text: str, *, is_error: bool) -> None:
        self._status_label.set_text(text)
        self._status_label.set_visible(bool(text))
        if is_error:
            self._status_label.add_css_class("pereprava-hint-warning")
        else:
            self._status_label.remove_css_class("pereprava-hint-warning")

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self._name_row,
            self._wrapped_row,
            self._password_row,
            self._confirm_row,
            self._password2_row,
            self._create_button,
        ):
            widget.set_sensitive(not busy)

    def _on_create_clicked(self, _button) -> None:
        name = self._name_row.get_text().strip()
        wrapped = self._wrapped_row.get_text().strip()
        password = self._password_row.get_text()
        confirm = self._confirm_row.get_text()
        password2 = self._password2_row.get_text()

        if not name:
            self._set_status("Enter a remote name first.", is_error=True)
            return
        if name in {r.rstrip(":") for r in list_remotes()}:
            self._set_status(f"A remote named “{name}” already exists.", is_error=True)
            return
        if not wrapped:
            self._set_status("Enter the remote:path to wrap.", is_error=True)
            return
        if not password:
            self._set_status("Enter a password.", is_error=True)
            return
        if password != confirm:
            self._set_status("Passwords don't match.", is_error=True)
            return

        self._set_busy(True)
        self._set_status("Creating encrypted remote…", is_error=False)

        def worker() -> None:
            ok, obscured = obscure_password(password)
            if not ok:
                GLib.idle_add(self._on_done, False, obscured)
                return
            obscured2 = ""
            if password2:
                ok, obscured2 = obscure_password(password2)
                if not ok:
                    GLib.idle_add(self._on_done, False, obscured2)
                    return
            ok, message = create_crypt_remote(name, wrapped, obscured, obscured2)
            GLib.idle_add(self._on_done, ok, message, name if ok else None)

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, ok: bool, message: str, name: str | None = None) -> bool:
        if ok:
            self._set_status(f"“{name}:” is ready to use.", is_error=False)
            self._on_created(name)
            self.close()
        else:
            self._set_busy(False)
            self._set_status(message, is_error=True)
        return GLib.SOURCE_REMOVE
