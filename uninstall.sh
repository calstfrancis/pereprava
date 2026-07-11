#!/bin/bash
# Reverses install.sh: removes the venv, launcher wrapper, and desktop entry.
#
# Deliberately does NOT touch your job definitions, generated systemd units,
# or log files — uninstalling the app should never silently disable a
# scheduled backup. If you want to remove a specific job's backup entirely,
# do that through the app first (Delete on the job), or see the manual
# commands printed below.
set -euo pipefail
cd "$(dirname "$0")"

rm -rf .venv

BIN_DIR="$HOME/.local/bin"
rm -f "$BIN_DIR/pereprava"

DESKTOP_DIR="$HOME/.local/share/applications"
rm -f "$DESKTOP_DIR/io.github.calstfrancis.pereprava.desktop"
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "Uninstalled Pereprava (venv, launcher, desktop entry removed)."
echo ""
echo "Your backup jobs are untouched and still running on their schedules:"
echo "  - Job definitions: ~/.config/pereprava/jobs/"
echo "  - Systemd units:   ~/.config/systemd/user/pereprava-job-*.{service,timer}"
echo "  - Logs:            ~/.local/state/pereprava/"
echo ""
echo "To also stop and remove a specific job's backup, run:"
echo "  systemctl --user disable --now pereprava-job-<slug>.timer"
echo "  rm ~/.config/systemd/user/pereprava-job-<slug>.{service,timer}"
echo "  rm ~/.config/pereprava/jobs/<slug>.json"
echo "  systemctl --user daemon-reload"
