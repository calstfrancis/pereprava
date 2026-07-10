#!/usr/bin/env python3
"""
Pereprava — a dashboard for rclone/rsync backup jobs run via systemd --user.
"""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio
from pereprava.storage.jobs_store import ensure_jobs_dir
from pereprava.ui.app_window import AppWindow
from pereprava.ui.styles import load_styles


def main():
    ensure_jobs_dir()

    app = Adw.Application(
        application_id="io.github.calstfrancis.pereprava",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
    )

    def on_activate(application):
        windows = application.get_windows()
        if windows:
            windows[0].present()
            return
        load_styles()
        window = AppWindow(application)
        window.present()

    app.connect("activate", on_activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
