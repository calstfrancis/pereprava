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
- `rclone` and/or `rsync`, whichever your jobs use — found via `PATH`, then
  `~/.local/bin`, `/usr/local/bin`, and common Homebrew-on-Linux locations if not on
  `PATH` (resolved once, at launch)
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

**Flatpak** (recommended):

```sh
flatpak remote-add --user --if-not-exists calstfrancis \
  https://calstfrancis.github.io/flatpak/calstfrancis.flatpakrepo
flatpak install calstfrancis io.github.calstfrancis.pereprava
```

The flatpak build still manages real `systemd --user` units and calls `systemctl`,
`rclone`, `rsync`, `systemd-analyze`, and `loginctl` on the host (via the Flatpak portal,
`flatpak-spawn --host`) rather than bundling its own copies — a job's actual scheduled
execution always runs as a normal host process via systemd regardless, sandbox or not — so
your jobs, history, and logs are exactly the same ones a non-flatpak install would see. See
[Packaging](#packaging) below.

**Install script**, if you'd rather not add a flatpak remote — one-liner (downloads the
latest release and installs it):

```sh
curl -fsSL https://raw.githubusercontent.com/calstfrancis/pereprava/main/install-remote.sh | bash
```

Or clone/download a release yourself and run the installer directly:

```sh
./install.sh
pereprava
```

This creates a `.venv` **with `--system-site-packages`**, so it reuses your system's
GTK4/libadwaita bindings rather than trying to build `pycairo` from source (which needs
`meson` and dev headers you may not have). Installs a launcher to `~/.local/bin/pereprava`
and a desktop entry — make sure `~/.local/bin` is on your `PATH`.

## Uninstalling

Flatpak: `flatpak uninstall io.github.calstfrancis.pereprava`.

Install script:

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

Distributed as a flatpak (self-hosted repo, see [Installing](#installing) above) and via
the plain install script — no RPM.

Pereprava needs to control host `systemd --user` units, read arbitrary host paths, and run
`rclone mount`'s FUSE mounts as real host mounts, none of which are things a flatpak
sandbox does for free. Rather than granting broad device/filesystem permissions and hoping
those still work from inside the container, the flatpak build routes every host-only
binary call — `systemctl`, `rclone`, `rsync`, `systemd-analyze`, `loginctl` — through
`flatpak-spawn --host` (see `pereprava/logic/host_exec.py`), which runs them as genuine
host processes via the Flatpak portal. A job's actual scheduled execution was already a
plain host process either way, since systemd itself is a host daemon — the sandbox only
ever wraps the GUI. `--filesystem=home` is still granted (matching every other app in this
suite) so config, job history, and logs at their usual `~/.config`/`~/.local/share` paths
are unchanged between a flatpak install and the install-script one.

If you'd rather not add a flatpak remote, the install script remains fully supported:
the one-liner above (`install-remote.sh`) fetches the latest release tarball
automatically, or grab a release from the
[Releases page](https://github.com/calstfrancis/pereprava/releases) yourself, extract it,
and run `./install.sh`.
