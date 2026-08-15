# SPDX-License-Identifier: MIT
"""On-SD-card cache for the once-a-day World Skills and Awards data.

Fetching World Skills or Awards means walking the whole roster for every
tracked team -- by far the most network/CPU work an update of this
dashboard does, and data that only meaningfully changes a few times a
season. code.py refetches each at most once per local calendar day
(gated by is_fresh()) instead of on every REFRESH_INTERVAL_SECONDS like
the Active Today view, and persists whatever it fetches here -- along
with the time it was fetched -- so a reboot later the same day doesn't
lose that work and refetch for nothing.

Each dataset is one small JSON file: ``{"fetched_at": <unix epoch
seconds>, "data": {...the fetch result...}}``. Requires an SD card
mounted at /sd (see hardware.mount_sd_card()) -- if there's no card,
every function here is a silent no-op / returns None, so the dashboard
still runs fine, it just refetches every time it's viewed.
"""

import json
import time

_FILES = {
    "world_skills": "/sd/world_skills_cache.json",
    "awards": "/sd/awards_cache.json",
}


def load(key):
    """{"fetched_at": ..., "data": ...} for ``key``, or None if there's no
    usable cache -- no SD card, first run, or a corrupt/incomplete file."""
    path = _FILES.get(key)
    if path is None:
        return None
    try:
        with open(path, "r") as f:
            cached = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(cached, dict) or "fetched_at" not in cached or "data" not in cached:
        return None
    return cached


def save(key, data):
    """Persist ``data`` for ``key`` along with the current time.

    Silently does nothing if there's no SD card to write to --
    persistence is a nice-to-have, not a requirement for the dashboard
    to keep running.
    """
    path = _FILES.get(key)
    if path is None:
        return
    payload = {"fetched_at": int(time.time()), "data": data}
    try:
        with open(path, "w") as f:
            json.dump(payload, f)
    except OSError as exc:
        print("Could not write cache for %s: %s" % (key, exc))


def is_fresh(cached, now=None):
    """True if ``cached`` (from ``load()``) was fetched on the same local
    calendar day as ``now`` (default: the current time)."""
    if cached is None:
        return False
    now = now if now is not None else time.time()
    fetched = time.localtime(cached["fetched_at"])
    current = time.localtime(now)
    return (fetched[0], fetched[1], fetched[2]) == (current[0], current[1], current[2])
