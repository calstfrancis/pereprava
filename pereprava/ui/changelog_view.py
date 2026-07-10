"""Live changelog viewer — parses CHANGELOG.md at runtime so the in-app view can
never drift from the actual file (see ~/Projects/CLAUDE.md's UI design standard,
ported from Zerkalo's show_changelog/md_inline_to_pango)."""

from __future__ import annotations

import re
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

CHANGELOG_PATH = Path(__file__).resolve().parents[2] / "CHANGELOG.md"

# Long single-line labels don't reliably wrap via Gtk.Label's wrap/width-chars
# properties in this environment (confirmed: natural width scales linearly with
# text length regardless of wrap-mode/width-chars settings past ~90 chars) —
# so long text is hard-wrapped ourselves with embedded newlines, which Pango
# always respects for natural-size purposes independent of that behavior.
_TOKEN_RE = re.compile(
    r"`[^`]*`[.,;:!?]*|\*\*[^*]*\*\*[.,;:!?]*|\[[^\]]*\]\([^)]*\)[.,;:!?]*|\S+"
)
WRAP_WIDTH = 70


def _wrap_markdown(text: str, width: int = WRAP_WIDTH) -> str:
    """Word-wrap markdown text, treating `code` / **bold** / [text](url) spans as
    atomic tokens so they never get split mid-span, then convert to Pango markup."""
    tokens = _TOKEN_RE.findall(text)
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for tok in tokens:
        visible = tok
        if visible.startswith("`") and visible.endswith("`") and len(visible) >= 2:
            visible = visible[1:-1]
        elif visible.startswith("**") and visible.endswith("**") and len(visible) >= 4:
            visible = visible[2:-2]
        added_len = len(visible) + (1 if current else 0)
        if current and current_len + added_len > width:
            lines.append(" ".join(current))
            current = [tok]
            current_len = len(visible)
        else:
            current.append(tok)
            current_len += added_len
    if current:
        lines.append(" ".join(current))
    return "\n".join(md_inline_to_pango(line) for line in lines)


def md_inline_to_pango(text: str) -> str:
    """Minimal inline markdown -> Pango markup: **bold**, `code`, [text](url) -> text."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "*" and i + 1 < n and text[i + 1] == "*":
            end = text.find("**", i + 2)
            if end == -1:
                out.append(GLib.markup_escape_text(text[i:]))
                break
            out.append("<b>" + GLib.markup_escape_text(text[i + 2 : end]) + "</b>")
            i = end + 2
            continue
        if ch == "`":
            end = text.find("`", i + 1)
            if end == -1:
                out.append(GLib.markup_escape_text(text[i:]))
                break
            out.append("<tt>" + GLib.markup_escape_text(text[i + 1 : end]) + "</tt>")
            i = end + 1
            continue
        if ch == "[":
            close = text.find("]", i + 1)
            if close != -1 and close + 1 < n and text[close + 1] == "(":
                url_end = text.find(")", close + 2)
                if url_end != -1:
                    out.append(GLib.markup_escape_text(text[i + 1 : close]))
                    i = url_end + 1
                    continue
        out.append(GLib.markup_escape_text(ch))
        i += 1
    return "".join(out)


def _bullet_row(text: str) -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_margin_start(8)
    dot = Gtk.Label(label="•")
    dot.set_valign(Gtk.Align.START)
    dot.add_css_class("dim-label")
    label = Gtk.Label()
    label.set_markup(_wrap_markdown(text))
    label.set_xalign(0.0)
    label.set_justify(Gtk.Justification.LEFT)
    label.set_hexpand(True)
    label.set_halign(Gtk.Align.FILL)
    row.append(dot)
    row.append(label)
    return row


def _build_body(changelog_text: str, current_version: str) -> Gtk.Widget:
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    body.set_margin_start(24)
    body.set_margin_end(24)
    body.set_margin_top(16)
    body.set_margin_bottom(24)

    first_heading = True
    for line in changelog_text.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("## ["):
            inner = trimmed[len("## [") :]
            if "]" in inner:
                version, rest = inner.split("]", 1)
                rest = rest.strip()
            else:
                version, rest = inner.rstrip("]"), ""
            title = rest[2:] if rest.startswith("— ") else rest

            heading_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            heading_row.set_margin_top(0 if first_heading else 22)
            first_heading = False

            ver_label = Gtk.Label(label=version)
            ver_label.add_css_class("monospace")
            ver_label.add_css_class("dim-label")
            ver_label.add_css_class("caption-heading")
            ver_label.set_xalign(0.0)
            heading_row.append(ver_label)

            if version == current_version:
                badge = Gtk.Label(label="· Current")
                badge.add_css_class("caption-heading")
                badge.add_css_class("accent")
                heading_row.append(badge)

            body.append(heading_row)

            if title:
                title_label = Gtk.Label()
                title_label.set_markup(_wrap_markdown(title))
                title_label.add_css_class("title-3")
                title_label.set_xalign(0.0)
                title_label.set_margin_bottom(2)
                body.append(title_label)
        elif trimmed.startswith("### "):
            label = Gtk.Label(label=trimmed[4:])
            label.add_css_class("heading")
            label.set_xalign(0.0)
            label.set_margin_top(8)
            label.set_margin_start(4)
            label.set_margin_bottom(2)
            label.set_wrap(True)
            label.set_max_width_chars(60)
            body.append(label)
        elif trimmed.startswith("- "):
            body.append(_bullet_row(trimmed[2:]))

    return body


def show_changelog(parent: Gtk.Window, current_version: str) -> None:
    try:
        text = CHANGELOG_PATH.read_text(encoding="utf-8")
    except OSError:
        text = "(CHANGELOG.md not found)"

    win = Adw.Window()
    win.set_title("Changelog — Pereprava")
    win.set_default_size(720, 680)
    win.set_transient_for(parent)
    win.set_modal(False)

    header = Adw.HeaderBar()
    title_widget = Adw.WindowTitle(title="Changelog", subtitle=f"You're on v{current_version}")
    header.set_title_widget(title_widget)

    body = _build_body(text, current_version)

    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    clamp = Adw.Clamp()
    clamp.set_maximum_size(700)
    clamp.set_child(body)
    scroll.set_child(clamp)

    toolbar_view = Adw.ToolbarView()
    toolbar_view.add_top_bar(header)
    toolbar_view.set_content(scroll)
    win.set_content(toolbar_view)
    win.present()
