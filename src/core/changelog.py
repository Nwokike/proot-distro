"""Bundled changelog — the offline "What's New" for the current build."""

from __future__ import annotations

CHANGELOG: dict[str, str] = {
    "1.2.0": (
        "• Display rebuilt: the X server now runs INSIDE the app\n"
        "• Zero installs: single apps run on any container instantly\n"
        "• Damage-driven streaming — a still screen costs nothing\n"
        "• Audio output and microphone support for guest apps\n"
        "• Clipboard over the stream itself — no guest tools needed\n"
        "• Heavier capture machinery removed; the app got leaner"
    ),
    "1.1.0": (
        "• Proot Distro X11: native X11 desktop on your phone\n"
        "• One tap from the Display tab: install desktop support, start, use\n"
        "• Full input — tap, drag, scroll, keyboard — plus clipboard sync\n"
        "• Access-code protected, loopback-only: nothing leaves the device\n"
        "• Works on Alpine, Debian, Ubuntu, Fedora and Arch containers\n"
        "• Flet family moved to 1.1.0"
    ),
    "1.0.1": (
        "• Background running: persistent notification keeps sessions alive\n"
        "• Exit App button in Settings\n"
        "• Live Activity Terminal in Settings for on-device diagnostics\n"
        "• Fixed container names for namespaced Docker images\n"
        "• Files modal crash fix, downloads and uploads working\n"
        "• Search results under the search bar, banner placement fixed\n"
        "• Terminal: real Clear, Select All, FAB in non-fullscreen"
    ),
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
