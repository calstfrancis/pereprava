"""Read-only log viewer dialog."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, GLib, Gtk

from pereprava.storage.logs import tail_log


class LogViewDialog(Adw.Dialog):
    def __init__(self, job_name: str, log_path: str):
        super().__init__()
        self._log_path = log_path
        self.set_title(f"Log — {job_name}")
        self.set_content_width(700)
        self.set_content_height(500)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        refresh_button = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_button.set_tooltip_text("Refresh")
        refresh_button.connect("clicked", lambda _b: self._reload())
        header.pack_start(refresh_button)

        copy_button = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_button.set_tooltip_text("Copy to clipboard")
        copy_button.connect("clicked", lambda _b: self._copy())
        header.pack_end(copy_button)

        toolbar_view.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_monospace(True)
        self._text_view.set_left_margin(8)
        self._text_view.set_top_margin(8)
        scrolled.set_child(self._text_view)
        toolbar_view.set_content(scrolled)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(toolbar_view)
        self.set_child(self._toast_overlay)
        self._reload()

    def _reload(self) -> None:
        text = tail_log(self._log_path)
        buf = self._text_view.get_buffer()
        buf.set_text(text)

        def scroll_to_end() -> bool:
            end_mark = buf.create_mark(None, buf.get_end_iter(), False)
            self._text_view.scroll_mark_onscreen(end_mark)
            return GLib.SOURCE_REMOVE

        # Deferred: right after set_text() the view may not be laid out yet
        # (e.g. the very first _reload() during __init__, before the dialog
        # is even presented), so scroll_mark_onscreen would be a no-op.
        GLib.idle_add(scroll_to_end)

    def _copy(self) -> None:
        buf = self._text_view.get_buffer()
        start, end = buf.get_bounds()
        text = buf.get_text(start, end, False)
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(text)
        self._toast_overlay.add_toast(Adw.Toast(title="Copied to clipboard", timeout=2))
