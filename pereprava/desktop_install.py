"""Install desktop entry and icon into the user's local share directories.

Only used by the non-flatpak (install.sh) distribution — the flatpak build
installs its desktop file and icon directly into /app via the manifest
instead (see io.github.calstfrancis.pereprava.yml)."""

import shutil
import subprocess
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"
_ROOT_DIR = Path(__file__).parent.parent
_APP_ID = "io.github.calstfrancis.pereprava"

_ICONS_BASE = Path.home() / ".local" / "share" / "icons" / "hicolor"
_ICON_SVG = _ICONS_BASE / "scalable" / "apps" / f"{_APP_ID}.svg"
_DESKTOP_DEST = Path.home() / ".local" / "share" / "applications" / f"{_APP_ID}.desktop"

_PNG_SIZES = (48, 128, 256)


def ensure_installed() -> None:
    """Copy icon (SVG + PNGs) and desktop file if missing or outdated."""
    icon_src = _DATA_DIR / f"{_APP_ID}.svg"
    desktop_src = _ROOT_DIR / f"{_APP_ID}.desktop"

    if not icon_src.exists() or not desktop_src.exists():
        return

    changed = False

    if _needs_update(_ICON_SVG, icon_src):
        _ICON_SVG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, _ICON_SVG)
        changed = True

    for size in _PNG_SIZES:
        png_dest = _ICONS_BASE / f"{size}x{size}" / "apps" / f"{_APP_ID}.png"
        if _needs_update(png_dest, icon_src):
            png_dest.parent.mkdir(parents=True, exist_ok=True)
            _svg_to_png(icon_src, png_dest, size)
            changed = True

    if _needs_update(_DESKTOP_DEST, desktop_src):
        _DESKTOP_DEST.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(desktop_src, _DESKTOP_DEST)
        changed = True

    if changed:
        _refresh_caches()


def _svg_to_png(svg_path: Path, png_path: Path, size: int) -> None:
    try:
        import gi

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf

        pb = GdkPixbuf.Pixbuf.new_from_file_at_size(str(svg_path), size, size)
        pb.savev(str(png_path), "png", [], [])
    except Exception:
        pass  # librsvg not available — SVG-only install is still better than nothing


def _needs_update(dest: Path, src: Path) -> bool:
    if not dest.exists():
        return True
    return src.stat().st_mtime > dest.stat().st_mtime


def _refresh_caches() -> None:
    icons_dir = str(_ICONS_BASE)
    apps_dir = str(_DESKTOP_DEST.parent)

    subprocess.run(["update-desktop-database", apps_dir], check=False, capture_output=True)
    subprocess.run(["gtk-update-icon-cache", "-f", "-t", icons_dir], check=False, capture_output=True)
    for cmd in ("kbuildsycoca6", "kbuildsycoca5"):
        result = subprocess.run([cmd, "--noincremental"], check=False, capture_output=True)
        if result.returncode == 0:
            break


if __name__ == "__main__":
    ensure_installed()
