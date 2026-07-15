# Pereprava

A small GTK4/libadwaita dashboard for rclone/rsync backup jobs run as `systemd --user`
timers, plus persistent `rclone mount` points run as `systemd --user` services. Shows
all your jobs at a glance — last run, next run, mounted/unmounted, success/failure —
and lets you create/edit them through a form instead of hand-writing systemd units.

**Safety first:** non-destructive `rclone copy` is the default job type. Anything that
*can* delete files at its destination (`rclone sync`, `rclone bisync`, `rsync --delete`,
or a custom command) is flagged loudly in the UI and requires an explicit
acknowledgment before it can be saved.

## Features

- **Job types:** `rclone copy`/`sync`/`bisync`, `rclone check` (verify source against
  destination without transferring anything), `rsync`, a persistent `rclone mount`, or
  a custom command
- **Filtering:** exclude and include glob patterns, applied in the order rclone/rsync
  see them
- **Bandwidth limiting**, including rclone's own time-of-day schedule syntax
  (e.g. `08:00,512k 20:00,10M`)
- **Live transfer progress** for rclone jobs — an opt-in toggle starts rclone's own
  `--rc` control API (loopback-only) so the job list can show real percent/speed/ETA
  instead of just "Running…"
- **Pre/post-run hook commands** (shell one-liners) around a job's main command
- **Conditional scheduling** — only run on AC power, or only on a specific Wi-Fi
  network (checked via `nmcli`)
- **Duplicate** and **Restore** actions — Restore pre-fills a new job with source and
  destination swapped, for pulling a backup back down
- **Per-job run history** (last 50 runs: time, duration, success/failure), sourced from
  systemd's own timestamps rather than parsed log output
- Guided remote setup: pCloud (OAuth via `rclone authorize`) and client-side encrypted
  remotes (`rclone crypt`, wrapping any existing remote:path)
- Remote free-space/quota display in the remote browser, where the backend supports it
- Desktop notifications the moment a job or mount transitions into a failed state
- Export/import job definitions as a single JSON file, for backup or moving to another
  machine
- Keeps monitoring in the background when the window is closed (Ctrl+Q to actually
  quit), with an optional system tray icon reflecting overall job health if
  AppIndicator is installed — see [Requirements](#requirements)

## Requirements

- Python 3.10+
- GTK4 and libadwaita with their GObject Introspection bindings (`python3-gobject` /
  `python-gobject` / distro equivalent) installed system-wide
- `rclone` and/or `rsync`, whichever your jobs use
- FUSE (`/dev/fuse` + the `fuse`/`fuse3` package), if you use any `rclone mount` jobs
- `systemd --user` (any modern Linux desktop)
- For a mount to start at boot without logging in, enable lingering for your user
  (`loginctl enable-linger`) — the Add/Edit form offers a button for this
- A browser, if you use the guided "Add pCloud Remote…" setup (it opens pCloud's
  OAuth login via `rclone authorize`)
- `nmcli` (NetworkManager), only if you use the "only run on this Wi-Fi network"
  scheduling condition
- `gir1.2-ayatanaappindicator3-0.1` (or `gir1.2-appindicator3-0.1`), only for the
  optional system tray icon — and on GNOME, the separate "AppIndicator and
  KStatusNotifierItem Support" shell extension, since GNOME ships no tray by default.
  Without either, the app runs exactly the same, just without a tray icon

## Installing

```sh
./install.sh
pereprava
```

This creates a `.venv` **with `--system-site-packages`**, so it reuses your system's
GTK4/libadwaita bindings rather than trying to build `pycairo` from source (which needs
`meson` and dev headers you may not have). Installs a launcher to `~/.local/bin/pereprava`
and a desktop entry — make sure `~/.local/bin` is on your `PATH`.

## Uninstalling

```sh
./uninstall.sh
```

Removes the venv, launcher, and desktop entry. **Does not** touch your job definitions,
generated systemd units, or logs — your scheduled backups keep running untouched. The
script prints the manual commands to remove a specific job's backup entirely, if you
want that.

## Data locations

- Job definitions: `~/.config/pereprava/jobs/<slug>.json` (source of truth)
- Generated systemd units: `~/.config/systemd/user/pereprava-job-<slug>.{service,timer}`
  (regenerated from the JSON on every change — never hand-edit these)
- Logs: `~/.local/state/pereprava/<slug>.log` by default (configurable per job), capped
  at 5MB and truncated in place rather than growing forever
- Run history: `~/.local/share/pereprava/history/<slug>.json` (last 50 runs)
- App state (e.g. which version's "What's New" you've last seen):
  `~/.config/pereprava/state.json`

## Packaging

No flatpak — Pereprava needs to control host `systemd --user` units and read arbitrary
host paths, both of which fight the flatpak sandbox model. No RPM either; for the small
number of people using this, the install script is the whole distribution story. Grab a
release from the [Releases page](https://github.com/calstfrancis/pereprava/releases),
extract it, and run `./install.sh`.
