"""Per-container capability probe — rootfs filesystem reads only.

Instant by design: no proot spawn, no PTY, works offline. The display server
(Xvnc + PulseAudio) runs in the app, so a container needs nothing installed for
a display; the probe exists to name the distro in the UI (and to give the
post-remove/reset invalidation something real to drop).
"""

from __future__ import annotations

import logging
from pathlib import Path

from ._core import _imp

logger = logging.getLogger(__name__)


def guest_capabilities(name: str) -> dict:
    """What this container is: its os-release identity.

    Returns {"os": {...}}. Raises with the real reason when the
    container/rootfs is unavailable — the UI surfaces it, never a silently
    empty probe."""
    paths = _imp("proot_distro.paths")
    guestfile = _imp("proot_distro.guestfile")
    rootfs = Path(paths.container_rootfs(name))
    if not rootfs.is_dir():
        raise RuntimeError(f"container '{name}' has no rootfs at {rootfs}")

    os_release: dict[str, str] = {}
    try:
        raw = guestfile.read_guest_file(rootfs, "etc/os-release") or guestfile.read_guest_file(
            rootfs, "usr/lib/os-release"
        )
        if raw:
            for line in raw.splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    os_release[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as exc:
        logger.debug("os-release unreadable for %s: %r", name, exc)

    return {
        "os": {
            "distro_id": os_release.get("ID", ""),
            "distro_like": os_release.get("ID_LIKE", ""),
            "version_id": os_release.get("VERSION_ID", ""),
            "pretty_name": os_release.get("PRETTY_NAME", ""),
        },
    }


def arch_choices() -> tuple[str, ...]:
    """Every architecture spelling upstream's `normalize_arch` accepts.

    Derived from `proot_distro.arch`, never hardcoded: the native names, the
    bare Docker names and the `linux/`-prefixed platform strings, every one
    checked through `normalize_arch`. "host" is our sentinel (pass no `-a`)."""
    arch = _imp("proot_distro.arch")
    normalized = arch.normalize_arch
    native = sorted(arch._KNOWN_ARCHS)
    docker = sorted(arch._DOCKER_TO_PROOT)
    choices = ["host"]
    for name in native:
        if normalized(name) and name not in choices:
            choices.append(name)
    for name in docker:
        if normalized(name) and name not in choices:
            choices.append(name)
        prefixed = f"linux/{name}"
        if normalized(prefixed) and prefixed not in choices:
            choices.append(prefixed)
    return tuple(choices)


def host_arch() -> str:
    """The host CPU architecture in proot-distro's naming (e.g. aarch64)."""
    return _imp("proot_distro.arch").get_device_cpu_arch()
