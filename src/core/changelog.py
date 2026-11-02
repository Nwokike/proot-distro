"""Bundled changelog — the offline "What's New" for the current build."""

from __future__ import annotations

CHANGELOG: dict[str, str] = {
    "1.0.0": (
        "• Real Linux containers on Android — no root, no Termux\n"
        "• Install any Docker image: type a reference or search Docker Hub\n"
        "• Interactive shells in every container, with the extra-keys bar\n"
        "• Manage containers: rename, back up, restore, copy, reset, remove\n"
        "• Light and dark themes, following the system by default"
    ),
}


def _version_key(version: str) -> tuple[tuple[int, ...], str]:
    """Stdlib-only dotted-int sort key ('1.10.0' > '1.9.0'); odd suffixes
    sort by their raw string so ordering stays deterministic."""
    head = version.split("-", 1)[0].split("+", 1)[0]
    parts = head.split(".")
    if all(p.isdigit() for p in parts):
        return (tuple(int(p) for p in parts), version)
    return ((), version)


def notes_for(version: str) -> str:
    """The changelog entry for a version, falling back to the newest one.

    Newest = highest version key (dict insertion order is not guaranteed to
    be newest-first once older versions are appended below the head).
    """
    if version in CHANGELOG:
        return CHANGELOG[version]
    if not CHANGELOG:
        return ""
    newest = max(CHANGELOG, key=_version_key)
    return CHANGELOG[newest]
