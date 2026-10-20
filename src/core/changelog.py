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


def notes_for(version: str) -> str:
    """The changelog entry for a version, falling back to the newest one."""
    return CHANGELOG.get(version) or next(iter(CHANGELOG.values()), "")
