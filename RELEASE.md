## What's new

- **A restic job type.** Point it at a repository (local path, `sftp:host:/path`, or
  `rclone:remote:path`) and a password file, and Pereprava runs `restic backup` on your
  schedule. Exclude patterns, extra arguments, run conditions and hooks all work as for
  other jobs; the form's Test button does a `restic backup --dry-run`. The repository
  must already exist (`restic init` once).
- **Optional keep policy** (e.g. `--keep-daily 7 --keep-weekly 4`) runs
  `restic forget --prune` after each successful backup. Since that permanently deletes
  old snapshots, such a job needs the usual destructive-action acknowledgment.
- Zarya's Backups card shows restic jobs automatically.

`restic` must be installed on the host; the flatpak calls it there like `rclone` and
`rsync`.

See [CHANGELOG.md](CHANGELOG.md) for the full history.
