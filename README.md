# Pereprava

A small GTK4/libadwaita dashboard for rclone/rsync backup jobs run as `systemd --user`
timers, plus persistent `rclone mount` points run as `systemd --user` services. Shows
all your jobs at a glance — last run, next run, mounted/unmounted, success/failure —
and lets you create/edit them through a form instead of hand-writing systemd units.

**Safety first:** non-destructive `rclone copy` is the default job type. Anything that
*can* delete files at its destination (`rclone sync`, `rclone bisync`, `rsync --delete`,
or a custom command) is flagged loudly in the UI and requires an explicit
acknowledgment before it can be saved.

## Requirements

- Python 3.10+
- GTK4 and libadwaita with their GObject Introspection bindings (`python3-gobject` /
  `python-gobject` / distro equivalent) installed system-wide
- `rclone` and/or `rsync`, whichever your jobs use
- FUSE (`/dev/fuse` + the `fuse`/`fuse3` package), if you use any `rclone mount` jobs
- `systemd --user` (any modern Linux desktop)
- For a mount to start at boot without logging in, enable lingering for your user
  (`loginctl enable-linger`) — the Add/Edit form offers a button for this

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
- Logs: `~/.local/state/pereprava/<slug>.log` by default (configurable per job)

## Packaging

No flatpak — Pereprava needs to control host `systemd --user` units and read arbitrary
host paths, both of which fight the flatpak sandbox model. No RPM either; for the small
number of people using this, the install script is the whole distribution story. Grab a
release from the [Releases page](https://github.com/calstfrancis/pereprava/releases),
extract it, and run `./install.sh`.
