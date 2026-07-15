"""Talk to a running rclone process's --rc control server (loopback-only,
--rc-no-auth) to read live transfer stats for the progress display.

Just the one endpoint this app needs (core/stats), not a general rclone RC
client. All failures — server not up yet, job just finished, wrong rclone
version — collapse to None; none of them are worth surfacing as errors since
polling just tries again next tick."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_TIMEOUT = 2


def fetch_stats(port: int) -> dict | None:
    url = f"http://127.0.0.1:{port}/core/stats"
    request = urllib.request.Request(
        url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return None
