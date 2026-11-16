"""TTL cache for probed facts, stored under the regenerable cache root.

The capability probe and the app scan are host-side filesystem reads, but they
still cost time on a phone (thousands of stat calls per container). `.flet`'s
README is explicit that `cache/` is regenerable: that is exactly what these
results are, so they live there with an expiry and never in `data/`.
"""

from __future__ import annotations

import json
import logging
import time

from core import storage_paths

logger = logging.getLogger(__name__)

# Long enough to make a cold start instant, short enough that installing a
# desktop or an app shows up without a manual re-check.
DEFAULT_TTL_SEC = 3600


def _path(kind: str, key: str):
    folder = storage_paths.cache_root() / "proot-distro" / "probe"
    folder.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in key)
    return folder / f"{kind}-{safe}.json"


def load(kind: str, key: str, ttl: int = DEFAULT_TTL_SEC):
    """The cached value, or None when absent/expired/unreadable."""
    try:
        raw = _path(kind, key).read_text(encoding="utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        if time.time() - float(payload.get("at", 0)) > ttl:
            return None
        return payload.get("data")
    except Exception as exc:
        logger.debug("probe cache read failed for %s/%s: %s", kind, key, exc)
        return None


def store(kind: str, key: str, data) -> None:
    """Best-effort write; a failed write only costs a re-probe later."""
    try:
        _path(kind, key).write_text(json.dumps({"at": time.time(), "data": data}), encoding="utf-8")
    except Exception as exc:
        logger.debug("probe cache write failed for %s/%s: %s", kind, key, exc)


def drop(kind: str, key: str) -> None:
    """Forget one entry (container removed, reset or renamed)."""
    try:
        _path(kind, key).unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("probe cache drop failed for %s/%s: %s", kind, key, exc)


def drop_all() -> int:
    """Clear every cached probe; returns the count removed.

    These entries are regenerable by definition, so Settings can offer one
    'Clear app cache' action without touching anything durable."""
    folder = storage_paths.cache_root() / "proot-distro" / "probe"
    removed = 0
    if not folder.is_dir():
        return 0
    for path in folder.glob("*.json"):
        try:
            path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            continue
    if removed:
        logger.info("probe cache cleared: %d entr(ies)", removed)
    return removed
