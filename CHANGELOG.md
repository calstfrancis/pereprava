# Changelog

## [0.3.0] "Second Crossing" — 2026-07-13

### Added
- "Test" button in the Add/Edit form runs a dry run (`--dry-run` for rclone copy/sync/bisync and rsync; a reachability check via `rclone lsjson` for mount jobs) in a background thread and shows the result without touching anything — custom commands are explicitly unsupported since there's nothing safe to preview
- Real-time remote-name check in the form: as you type a `remote:path` value, an inline hint flags a remote that isn't in `rclone listremotes` before you ever save the job
- Export/Import buttons in the header bundle every job definition to/from a single JSON file, for backup or moving to another machine; importing renames a slug that collides with an existing job rather than overwriting it, and regenerates/enables systemd units for each imported job
- Desktop notifications (via `Gio.Notification`) fire the moment a job or mount transitions into a failed state — not on every refresh tick while it stays failed
- Guided pCloud remote setup: an "Add pCloud Remote…" button in the remote browser walks through rclone's own headless OAuth recipe (`rclone authorize pcloud` → `rclone config create ... token ...`), opening your browser for the login and finishing automatically once you approve access

## [0.2.0] "Anchor" — 2026-07-13

### Added
- New `rclone mount` job type for persistent mount points (e.g. mounting pCloud at `~/pCloud`), alongside the existing copy/sync/rsync/custom job types
- Mount jobs run as a `systemd --user` service enabled directly via `WantedBy=default.target` instead of a timer, since they're meant to stay up rather than run on a schedule; the dashboard shows Mounted/Unmounted/Mount failed instead of the periodic-job OK/Paused/Failed wording, and "Pause"/"Resume" become "Unmount"/"Mount"
- Add/Edit form swaps the path pickers for a mount job: Source becomes the rclone remote (with the remote browser), Destination becomes the local mount point (with a folder picker), and the Schedule/Safety sections hide since neither applies
- A "Startup" section in the form surfaces whether `loginctl` lingering is enabled for your user, with a one-click Enable button — lingering is what lets the mount start at boot without an interactive login
- Discovery/reconciliation now recognizes a mount job's `.service` unit the same way it already recognized a periodic job's `.timer`, so unmanaged/needs-repair detection covers both

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
