"""Bundled changelog — the offline "What's New" for the current build."""

from __future__ import annotations

CHANGELOG: dict[str, str] = {
    "1.2.1": (
        "• Desktop installation removed: run any command on its own display; a desktop is just a command such as startxfce4\n"
        "• Microphone is off at display start; the toolbar button is the only switch and asks Android for the grant when turned on\n"
        "• Presets refresh on their own and have a refresh button, in the display sheet and on the Display tab\n"
        "• A container's sheet shows only its own presets; detected apps get a no-sandbox checkbox\n"
        "• Share works without a tunnel: the local and Wi-Fi URLs open a sign-in page where the access code is typed\n"
        "• The keyboard opens through the noVNC panel; fullscreen hides the status and navigation bars\n"
        "• Guest app notifications are forwarded as Android notifications (best effort)\n"
        "• Arch pacman works under proot (sandbox disabled, download user fixed)\n"
        "• Ads placed between Distros and Presets, every five presets, and after the Home install list\n"
        "• Terminal default theme follows the app mode: Dracula in dark, Colab Light in light\n"
        "• Play device support restored: microphone, touchscreen and leanback are no longer required features\n"
        "• Files list sits closer to the top; banners stay between sections"
    ),
    "1.2.0": (
        "• Display engine rebuilt: TigerVNC's X server (Xvnc) runs INSIDE the app\n"
        "• Audio out and microphone for guest apps (PulseAudio, per-display bus)\n"
        "• The viewer is upstream noVNC, verbatim: the keyboard really opens\n"
        "• Fit-to-screen letterboxing; the whole desktop stays visible\n"
        "• Any CPU architecture: QEMU user-mode bundled for foreign-arch images\n"
        "• Desktop-aware shells: Start X display exports DISPLAY into your shell\n"
        "• Every Xvnc/PulseAudio option exposed: depth, fps, quality, viewers,\n"
        "  privacy, timeouts, clipboard cap, audio rate/latency/mode, mic format\n"
        "• Saved presets: name any app command and start it in one tap\n"
        "• App detection reads the container's own application entries\n"
        "• Failures tell the truth (Failed rows, whole-tree Stop, orphan sweep)\n"
        "• Storage shows containers vs OCI cache, real image sizes and sweeps\n"
        "• Core X fonts ship inside the APK, so text needs no guest install\n"
        "• Settings hub, Help screen, bundled license texts and docs"
    ),
    "1.1.0": (
        "• X11 display: GUI apps and full desktops streamed inside the app\n"
        "• One tap from the Display tab: install desktop support, start, use\n"
        "• Single-app mode: any command alone on its own :N display\n"
        "• Multi-display sessions with globally unique display numbers\n"
        "• Full input (tap, drag, scroll, keyboard) plus clipboard sync\n"
        "• Share on your Wi-Fi (LAN) or through a public tunnel, access-code protected\n"
        "• Pillow built with XCB in CI, so screen capture actually works\n"
        "• Minimal desktop install: only what a session needs, DE extras apart\n"
        "• Display toolbar: shell for the container, live output panel, fullscreen\n"
        "• Fixed: black desktops (TCP listen, guest XAUTHORITY, glycin sandbox)\n"
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
        "• Real Linux containers on Android, no root, no Termux\n"
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
