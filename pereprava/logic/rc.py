"""Which job types can use rclone's --rc live-progress API, and loopback port
allocation for it. rsync/custom/mount have no equivalent (mount doesn't have a
discrete "done" point to show progress toward)."""

from __future__ import annotations

import random
import socket

from pereprava.model.job import JobType

RC_PORT_RANGE = range(21000, 22000)

RC_CAPABLE_TYPES = {
    JobType.RCLONE_COPY,
    JobType.RCLONE_SYNC,
    JobType.RCLONE_BISYNC,
    JobType.RCLONE_CHECK,
}


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def allocate_port(taken: set[int]) -> int:
    """Pick a loopback port not already assigned to another job, preferring one
    that's actually free system-wide right now (best-effort — a job started
    later could still race another process, same as any port allocation)."""
    candidates = [p for p in RC_PORT_RANGE if p not in taken]
    random.shuffle(candidates)
    for port in candidates:
        if _port_is_free(port):
            return port
    return candidates[0] if candidates else RC_PORT_RANGE.start
