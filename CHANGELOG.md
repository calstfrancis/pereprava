# Changelog

## [0.1.0] — 2026-07-10

Initial version.

### Added
- Job dashboard listing all `pereprava-job-*` systemd units, with live status
  (idle/running/ok/failed/paused), next/last run time, and per-job actions
  (Run Now, View Log, Pause/Resume, Edit, Delete).
- Add/Edit job form supporting `rclone copy`, `rclone sync`, `rclone bisync`, `rsync`,
  and custom commands, with schedule presets (hourly/every 6h/daily/weekly/custom) and
  a "Test" button that previews the next occurrences via `systemd-analyze calendar`.
- Non-destructive-by-default safety model: `rclone copy` can never be marked
  destructive; `sync`/`bisync`/custom commands are always treated as destructive;
  `rsync --delete` is off by default. Any destructive job requires an explicit
  acknowledgment checkbox before it can be saved.
- Discovery/reconciliation for units and job definitions that have drifted out of
  sync with each other (unmanaged units, jobs needing unit repair).
