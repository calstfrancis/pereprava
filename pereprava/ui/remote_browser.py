"""Browse an rclone remote's folders directly via the API — no FUSE mount involved."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from pereprava.storage.rclone import list_dirs, list_remotes


class RemoteBrowserDialog(Adw.Dialog):
    def __init__(self, on_select: Callable[[str], None], initial_remote: str | None = None):
        super().__init__()
        self._on_select = on_select
        self.set_content_width(480)
        self.set_content_height(560)
        self.set_title("Browse Remote")

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.add_css_class("flat")
        self._select_button = Gtk.Button(label="Select This Folder")
        self._select_button.add_css_class("suggested-action")
        self._select_button.connect("clicked", self._on_select_clicked)
        header.pack_end(self._select_button)
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", lambda _b: self.close())
        header.pack_start(cancel_button)
        toolbar_view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        remotes = list_remotes()
        self._remote = initial_remote or (remotes[0] if remotes else "")

        remote_row = Adw.ComboRow(title="Remote")
        remote_row.set_model(Gtk.StringList.new(remotes or ["(no remotes configured)"]))
        if self._remote in remotes:
            remote_row.set_selected(remotes.index(self._remote))
        remote_row.connect("notify::selected", self._on_remote_changed)
        self._remotes = remotes
        content.append(remote_row)

        self._path_label = Gtk.Label(label="/")
        self._path_label.set_xalign(0.0)
        self._path_label.add_css_class("dim-label")
        content.append(self._path_label)

        up_button = Gtk.Button(icon_name="go-up-symbolic")
        up_button.set_tooltip_text("Up one level")
        up_button.set_halign(Gtk.Align.START)
        up_button.connect("clicked", lambda _b: self._go_up())
        content.append(up_button)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        scrolled.set_child(self._list_box)
        content.append(scrolled)

        toolbar_view.set_content(content)
        self.set_child(toolbar_view)

        self._path = ""
        self._refresh()

    def _on_remote_changed(self, row, _pspec) -> None:
        if self._remotes:
            self._remote = self._remotes[row.get_selected()]
        self._path = ""
        self._refresh()

    def _go_up(self) -> None:
        if not self._path:
            return
        parts = self._path.strip("/").split("/")
        self._path = "/".join(parts[:-1])
        self._refresh()

    def _enter(self, name: str) -> None:
        self._path = f"{self._path}/{name}" if self._path else name
        self._refresh()

    def _refresh(self) -> None:
        self._path_label.set_text(f"{self._remote}{self._path}/" if self._remote else "(no remote)")

        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        if not self._remote:
            return

        for name in list_dirs(self._remote, self._path):
            row = Adw.ActionRow(title=name)
            row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
            row.set_activatable(True)
            row.connect("activated", lambda _r, n=name: self._enter(n))
            self._list_box.append(row)

    def _on_select_clicked(self, _button) -> None:
        if self._remote:
            self._on_select(f"{self._remote}{self._path}")
        self.close()
