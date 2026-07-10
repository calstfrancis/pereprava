#!/bin/bash
# Local (non-flatpak) install: venv + pip install -e + desktop entry.
set -euo pipefail
cd "$(dirname "$0")"

# --system-site-packages: reuse the system's PyGObject/GTK4/libadwaita bindings
# rather than building pycairo from source in an isolated venv (requires meson +
# dev headers not guaranteed to be present).
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/pereprava" <<EOF
#!/bin/bash
exec "$(pwd)/.venv/bin/pereprava" "\$@"
EOF
chmod +x "$BIN_DIR/pereprava"

DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cp io.github.calstfrancis.pereprava.desktop "$DESKTOP_DIR/"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Installed. Make sure $BIN_DIR is on your PATH, then run: pereprava"
