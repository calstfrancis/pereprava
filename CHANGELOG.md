# Changelog

## [0.1.0] "First Crossing" — 2026-07-11

Initial release.

### Added
- Job dashboard listing all `pereprava-job-*` systemd units, with live status (idle/running/ok/failed/paused), next/last run time, and per-job actions (Run Now, View Log, Pause/Resume, Edit, Delete)
- Add/Edit job form supporting `rclone copy`, `rclone sync`, `rclone bisync`, `rsync`, and custom commands, with schedule presets (hourly/every 6h/daily/weekly/custom) and a "Test" button that previews the next occurrences via `systemd-analyze calendar`
- Non-destructive-by-default safety model: `rclone copy` can never be marked destructive; `sync` / `bisync` / custom commands are always treated as destructive; `rsync --delete` is off by default. Any destructive job requires an explicit acknowledgment checkbox before it can be saved
- Discovery/reconciliation for units and job definitions that have drifted out of sync with each other (unmanaged units, jobs needing unit repair)
- Destination browser for rclone remotes: browse a configured remote's folders directly via `rclone lsjson` (no FUSE mount required) when picking a job's destination
- Status bar with an "auto-refresh" toggle (bold when active, matching house style) and a version button that opens a live-parsed changelog view
- File picker for a job's log location, instead of typing a path by hand
- `uninstall.sh`, which removes the app but deliberately leaves job definitions, systemd units, and logs untouched so uninstalling never disables a running backup
