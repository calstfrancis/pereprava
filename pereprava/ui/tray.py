"""Optional system tray icon, best-effort only.

Real StatusNotifierItem support via AppIndicator (Ayatana's fork preferred,
falling back to the original) — works natively on KDE/XFCE; on GNOME it only
shows up with the separate "AppIndicator and KStatusNotifierItem Support"
shell extension installed, since GNOME ships no tray by default. If the
library isn't installed at all, this whole module quietly does nothing —
a tray icon must never be load-bearing for the app to work.

No dropdown menu: AppIndicator's classic API wants a GTK3 Gtk.Menu, and a
process can only ever load one Gtk version via GObject Introspection — a
GTK4 app cannot also construct a GTK3 widget. So the icon here only reflects
overall job health (OK vs. needs attention) via its icon + tooltip; the
window itself (reopened by re-launching the app) is still the only way to
interact with jobs.
"""

from __future__ import annotations

import gi

from pereprava.model.status import RunState

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3
    except (ValueError, ImportError):
        AppIndicator3 = None

TRAY_AVAILABLE = AppIndicator3 is not None

_ICON_OK = "folder-remote-symbolic"
_ICON_ATTENTION = "dialog-warning-symbolic"


def create_indicator():
    """None if AppIndicator isn't installed, or anything about setting it up
    fails — callers should treat that as "no tray icon" and move on."""
    if not TRAY_AVAILABLE:
        return None
    try:
        indicator = AppIndicator3.Indicator.new(
            "io.github.calstfrancis.pereprava",
            _ICON_OK,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        indicator.set_title("Pereprava")
        return indicator
    except Exception:
        return None


def update_indicator(indicator, entries) -> None:
    """Reflect overall job health in the icon/tooltip — the only signal a
    menu-less indicator can carry."""
    if indicator is None:
        return
    any_failed = any(entry.status.state == RunState.FAILED for entry in entries)
    try:
        if any_failed:
            indicator.set_icon_full(_ICON_ATTENTION, "Pereprava — attention needed")
            indicator.set_title("Pereprava — attention needed")
        else:
            indicator.set_icon_full(_ICON_OK, "Pereprava — all OK")
            indicator.set_title("Pereprava — all OK")
    except Exception:
        pass
