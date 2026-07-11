"""CSS for status badges and the Nautilus-like flat list. Loaded once at startup."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk

CSS = """
.pereprava-status-ok {
    color: @success_color;
}
.pereprava-status-failed {
    color: @error_color;
    font-weight: bold;
}
.pereprava-status-running {
    color: @accent_color;
}
.pereprava-status-paused {
    color: alpha(currentColor, 0.6);
}
.pereprava-warning-icon {
    color: @warning_color;
}
.pereprava-job-list row {
    padding-top: 6px;
    padding-bottom: 6px;
}
.status-toggle {
    opacity: 0.7;
}
.status-toggle:hover,
.status-toggle:focus {
    opacity: 1;
}
.pereprava-current-badge {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
    border-radius: 999px;
    padding: 1px 9px;
    font-size: 0.85em;
    font-weight: bold;
}
.pereprava-bullet-dot {
    color: @accent_color;
    font-size: 0.7em;
}
"""


def load_styles() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
