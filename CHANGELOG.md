# Changelog

## [0.6.2] "Common Ground" — 2026-07-16

### Fixed
- The Add/Edit form's "Test" dry run now reads rclone/rsync's actual output correctly — both write their per-file notices, dry-run previews, and transfer summary to stderr, not stdout, but `interpret_result` only ever checked stdout, so a real job with a large, genuine diff still reported the generic "no changes would be made" fallback. Also, since rclone's `-v` (needed so real runs don't log silently — see below) means its stats footer is now always present even for a genuinely no-op dry run, the "no changes" message is restored via a narrow, stable match on rclone's own zero-file-count line, rather than becoming unreachable behind a raw stats dump. This was purely a Test-button display bug — the actual scheduled/Run Now execution's log capture uses a separate, unaffected code path (`StandardOutput=`/`StandardError=append` on the systemd unit itself)
- A job whose most recent start attempt was silently skipped by an unmet Run Condition (AC power / Wi-Fi SSID) now shows "Skipped — a Run Condition isn't met" instead of looking like nothing happened at all, via a proper `RunState.SKIPPED` value rather than a bolt-on flag — so the tray icon, desktop failure notifications, and run history all correctly treat it as a routine skip too, instead of a real failure. (An earlier version of this fix added the skip as a separate boolean alongside the existing OK/FAILED/etc. state, which only fixed the status *text*: the underlying state still classified an unmet Wi-Fi condition as FAILED, so the tray flipped to "attention needed," a false "Job failed" desktop notification fired, and a misleading "Failed (exec-condition)" entry got recorded to history — every time the condition wasn't met.)
- `rclone`/`rsync` are now resolved via `PATH` (then `~/.local/bin`, `/usr/local/bin`, and common Homebrew-on-Linux locations) at startup instead of being hardcoded to `/usr/bin/rclone`/`/usr/bin/rsync` — on a machine where either is installed elsewhere, every single job referenced a nonexistent binary. For periodic (timer-based) jobs specifically, that failure was structurally invisible: saving only validates that the *timer* enables, never whether the triggered service's command can actually run, so nothing showed up until the timer fired on its own — no error, no log, no history

## [0.6.1] "Open Passage" — 2026-07-15

### Fixed
- "Repair" on a needs-repair job now forces it back to enabled, instead of respecting whatever `enabled` state was already stored — a previously-paused job whose unit had since been garbage-collected by systemd showed as "needs repair" the same as a genuinely broken one, but Repair would just call `disable_now` on a unit that wasn't even loaded: a no-op that reported success while changing nothing, leaving the discrepancy permanently stuck
- The "needs repair" discrepancy row now has Edit and Delete buttons, not just Repair — previously a job stuck in that state (e.g. one with a bad path/remote that Repair alone can't fix) had no way to be changed or removed at all

## [0.6.0] "Still Waters" — 2026-07-15

### Added
- The app now keeps running/monitoring in the background when the window is closed, instead of quitting — closing hides the window rather than destroying it; re-launching the app (or its desktop icon) re-presents the same window. Ctrl+Q actually quits
- Optional system tray icon reflecting overall job health (OK vs. needs attention), via AppIndicator (Ayatana's maintained fork preferred, falling back to the original) if installed. Best-effort only: on GNOME it needs the separate "AppIndicator and KStatusNotifierItem Support" extension (GNOME ships no tray by default); on KDE/XFCE it works natively. No dropdown menu — AppIndicator's menu API wants a GTK3 widget, which can't coexist in this GTK4 app's process, so the icon is status-only; the window is still how you interact with jobs

### Fixed
- Mount jobs now strip a stray `.directory` file from the destination before every mount attempt — KDE/Dolphin (and its file-open portal) write this hidden view-metadata file into essentially any folder they touch, including one freshly created through Pereprava's own mount-point folder picker moments earlier, which was enough on its own to trip rclone's "destination must be empty" safety check on an otherwise genuinely empty folder and send the mount into an endless `Restart=on-failure` retry loop

## [0.5.0] "Steady Current" — 2026-07-15

### Added
- Live progress display for `rclone copy`/`sync`/`bisync`/`check` jobs — an opt-in "Show live progress" toggle in the Add/Edit form starts rclone's own `--rc` control API on a loopback-only port (auto-allocated, one per job) and the job list polls it every 1.5s for real transfer stats (percent, speed, ETA) or check counts, shown as a slim progress bar + caption in place of the plain status label while the job is running. Off by default and not offered for `rsync`/`custom`/mount, since rsync has no equivalent control API and mount has no discrete "done" point to show progress toward

## [0.4.0] "Third Crossing" — 2026-07-15

### Added
- "Exclude folders/files" field in the Add/Edit form (space-separated glob patterns, quote ones with spaces) for `rclone copy`/`sync`/`bisync`/mount and `rsync` jobs — translates to repeated `--exclude PATTERN` flags, picked up automatically by the Test dry run since it goes through the same command-building code
- "Include only folders/files" field, same shape as Exclude, applied after it in filter order
- New `rclone check` job type — verifies source against destination without transferring anything, never destructive, shows up as a normal periodic job (OK/Failed) so drift gets caught and notified like any other failure
- Bandwidth limit field (`--bwlimit`), including rclone's own time-of-day schedule syntax (e.g. `08:00,512k 20:00,10M`) — passed through as a single argument, not space-split like the other fields
- Pre/post-run hook commands (shell one-liners, run via `/bin/sh -c` so `&&`/pipes/env vars work) — post-hook only fires if the main command succeeds, per stock systemd `ExecStartPost` semantics
- Run Conditions: "only run on AC power" (`ConditionACPower=`) and "only run on this Wi-Fi network" (SSID, checked via `nmcli` through `ExecCondition=` so an unmet condition skips cleanly rather than counting as a failure)
- "Duplicate…" job action — opens the Add/Edit form pre-filled with a copy (new slug/name/log path, paused) for review before saving, rather than silently creating a live second copy
- "Restore…" job action (copy/sync/bisync/rsync only) — same pre-fill-and-review flow as Duplicate, but with source and destination swapped
- "View History" per job — the last 50 runs (time, duration, success/failure), sourced from systemd's own start/exit timestamps rather than parsing rclone/rsync's log output, which isn't a stable format to depend on. Not tracked for mounts, which don't have discrete "runs"
- Guided encrypted-remote setup ("Add Encrypted Remote…" in the remote browser) — wraps an existing remote:path in an `rclone crypt` remote via `rclone obscure` + non-interactive `rclone config create`, same shape as the pCloud OAuth wizard
- Remote free-space/quota display in the remote browser (`rclone about --json`), shown for the selected remote when the backend supports it
- A "Needs attention (N)" header now separates unmanaged-unit/needs-repair discrepancy rows from the healthy job list, instead of them blending in as more plain rows
- The Add/Edit form's Test button, the log viewer's copy button, and Run Now all have matching polish: cancel support, a "Copied to clipboard" toast, and a proper error dialog on failure respectively
- Ctrl+N (Add Job) and Ctrl+R (Refresh) keyboard shortcuts
- The changelog window now also opens automatically once after an update (not just on demand via the version button), skipping the very first run

### Changed
- `rclone sync` jobs get their own row icon instead of sharing one with `rclone copy` — only `rclone bisync` did before
- Job row subtitles now elide the middle of long source/destination paths individually (with the full text in a tooltip) instead of relying on a single trailing ellipsis that could hide an entire side
- Job logs are capped at 5MB and truncated in place (keeping the most recent ~1MB) instead of growing forever — relevant for a mount job that keeps flapping and restarting every 10s

### Fixed
- Saving, pausing/resuming, repairing, deleting, running now, or bulk-importing a job now surfaces the actual `systemctl --user` error when the enable/disable/start step fails, instead of always reporting success — previously a job could silently end up in the "needs repair" state (JSON saved, unit never loaded) with no indication anything had gone wrong
- The Add/Edit form's "Test" dry run no longer has a fixed timeout at all (was 30s, briefly tried 90s) — a real dry run against a big or deeply-nested remote (e.g. a large photo library) can legitimately take minutes, so there's no correct constant. Instead the dry run now runs in the background indefinitely with a Cancel button, same shape as the pCloud authorize flow
- Removing an unmanaged unit now asks for confirmation first, matching the existing confirmation for deleting a managed job, instead of disabling and deleting it on a single click
- The log viewer now scrolls to the most recent output on open/refresh instead of landing at the top of the file
- `rclone copy`/`sync`/`bisync` and `rsync` jobs now always run with `-v` — neither tool prints anything on a quiet success when not attached to a terminal (which a systemd unit never is), so logs looked empty/broken even on jobs that ran fine. Existing jobs need a re-save (Edit → Save, or Repair) to pick up the new unit — Pereprava doesn't rewrite unit files on its own until the next explicit save
- Both mount and periodic job units now `mkdir -p` the log file's directory before running, instead of assuming it already exists — a fresh install with no prior `~/.local/state/pereprava/` could otherwise fail to open the log at all

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
