"""Payload paths, xauth files and the rewritten-prefix helpers."""

from __future__ import annotations

import logging
import os
import re
import struct
from pathlib import Path

from core import storage_paths

logger = logging.getLogger(__name__)


RFB_PORT_BASE = 5900

PULSE_TCP_PORT = 4713

_COOKIE_RE = re.compile(r"^[0-9a-f]{32}$")

# X protocol auth families (X.h).
_FAMILY_INTERNET = 0
_FAMILY_LOCAL = 256
_FAMILY_WILD = 65535

# ── payload locations ────────────────────────────────────────────────────────


def native_dir() -> Path:
    """The APK's extracted native-lib dir — where the flet-xvnc / flet-pulseaudio
    wheels land their payloads (libXvnc.so, libpulseaudio.so, module-*.so)."""
    from core.proot_probe import _native_library_dir

    native = _native_library_dir()
    if native is None or not native.is_dir():
        raise RuntimeError(
            "the display payloads ship inside the Android app — they are not "
            "available in this environment"
        )
    return native


def xvnc_binary() -> Path:
    binary = native_dir() / "libXvnc.so"
    if not binary.is_file():
        raise RuntimeError(f"libXvnc.so missing from {binary.parent}")
    return binary


def pulseaudio_binary() -> Path:
    binary = native_dir() / "libpulseaudio.so"
    if not binary.is_file():
        raise RuntimeError(f"libpulseaudio.so missing from {binary.parent}")
    return binary


def module_path(name: str) -> Path:
    """One PulseAudio module from the wheel (absolute path — pulseaudio accepts a
    path wherever it accepts a module name, libltdl dlopens it directly)."""
    if "/" in name or not name.endswith(".so"):
        raise ValueError(f"module name must be a bare basename.so: {name!r}")
    path = native_dir() / name
    if not path.is_file():
        raise RuntimeError(f"{name} missing from {path.parent}")
    return path


# ── xauth (Python-written — the guest has no xauth binary) ───────────────────


def xauth_bytes(cookie: str, display: int) -> bytes:
    """One MIT-MAGIC-COOKIE-1 auth file covering every connection shape.

    .Xauthority is concatenated records of: family (u16 BE), address, display
    number, auth name, auth data — each with a u16 BE length prefix. We write
    FamilyWild (matches anything), FamilyLocal (the guest's unix socket) and
    FamilyInternet (127.0.0.1 TCP), so the server accepts the stream server's
    loopback connection and the guest apps' socket connection alike.
    """
    if not _COOKIE_RE.fullmatch(cookie):
        raise ValueError("cookie must be 32 hex chars")
    if not isinstance(display, int) or not 0 <= display <= 99:
        raise ValueError(f"display must be an int 0-99, got {display!r}")
    data = bytes.fromhex(cookie)
    name = b"MIT-MAGIC-COOKIE-1"
    number = str(display).encode()

    def record(family: int, addr: bytes) -> bytes:
        return (
            struct.pack(">H", family)
            + struct.pack(">H", len(addr))
            + addr
            + struct.pack(">H", len(number))
            + number
            + struct.pack(">H", len(name))
            + name
            + struct.pack(">H", len(data))
            + data
        )

    return (
        record(_FAMILY_WILD, b"")
        + record(_FAMILY_LOCAL, b"localhost")
        + record(_FAMILY_INTERNET, b"127.0.0.1")
    )


def write_xauth_file(cookie: str, display: int, path: Path) -> Path:
    """Write the auth file (host-side path INSIDE the guest rootfs — the same
    file is handed to Xvnc via -auth and exported to the guest as XAUTHORITY)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(xauth_bytes(cookie, display))
    path.chmod(0o600)
    return path


def guest_cookie_path(container: str, display: int) -> Path:
    """Host-side path of the guest's xauth file (inside the container rootfs)."""
    from core import storage_paths as sp

    return sp.containers_dir() / container / "rootfs" / "tmp" / "x11" / f"xauth-{display}"


# ── xkb data ─────────────────────────────────────────────────────────────────


def _payload_env(native: Path) -> dict[str, str]:
    """The exec env for the payloads: our libs on the linker path, app dirs as
    the writable homes (the payloads were built for the Termux prefix, whose
    paths do not exist here — everything they touch must be redirected)."""
    env = dict(os.environ)
    runtime = storage_paths.support_root() / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    ld = [str(native), str(runtime)]
    if os.environ.get("LD_LIBRARY_PATH"):
        ld.append(os.environ["LD_LIBRARY_PATH"])
    env["LD_LIBRARY_PATH"] = ":".join(ld)
    env["HOME"] = str(storage_paths.data_root())
    env["TMPDIR"] = str(storage_paths.temp_root())
    xdg = runtime / "xdg"
    xdg.mkdir(parents=True, exist_ok=True)
    env["XDG_RUNTIME_DIR"] = str(xdg)
    return env


def ensure_lock_dir() -> Path | None:
    """Create `<app>/tmp` — where the builder rewrote Xvnc's compiled Termux
    prefix. The server creates `<prefix>/tmp/.tX{N}-lock` there (fatal when
    unwritable, device 2026-11-13) and compiles keymaps under `<prefix>/tmp/`.
    The app root is derived from our own storage path: `<app>/files/data` → `<app>`."""
    try:
        app_root = storage_paths.data_root().parents[1]
    except Exception:
        return None
    if not app_root.is_dir():
        return None
    target = app_root / "tmp"
    target.mkdir(parents=True, exist_ok=True)
    return target


# ── the baked prefix's executables ───────────────────────────────────────────
# Xvnc was built for Termux's prefix and the builder rewrites that literal
# prefix in place to our app dir. Two of those paths are EXECUTABLES Xvnc
# spawns: its os/utils.c Popen runs `<app>//bin/sh -c "<app>//bin/xkbcomp …"`
# and xkb/ddxLoad.c ALWAYS spawns xkbcomp to compile the keymap (the
# `server-<N>.xkm` cache is written, read and unlinked in the same call — an
# existing file is never reused, verified in xorg-server 21.1.25).
#
# Android's W^X rule forbids execve() of files under the app home, but execve
# FOLLOWS symlinks and SELinux checks the resolved inode: the APK's
# native-library files are apk_data_file, which apps may execute (the
# documented python-for-android / Termux-bootstrap pattern). So the baked
# paths are satisfied by links into the native dir — the payloads keep running
# from the exec-allowed location, and xkbcomp derives the keymap from the
# shipped xkeyboard-config data exactly as Xorg intends.
_SYSTEM_SHELL = "/system/bin/sh"


def app_root() -> Path | None:
    """The app's private root (`<app>/files/data` → `<app>`), or None off-device."""
    try:
        root = storage_paths.data_root().parents[1]
    except Exception:
        return None
    return root if root.is_dir() else None


def ensure_prefix_bin() -> Path | None:
    """Satisfy `<app>/bin/sh` and `<app>/bin/xkbcomp` with links to the
    platform shell and the shipped libxkbcomp.so.

    Called before every spawn and compares the link target, so an app update
    (a new native-lib dir) re-links instead of silently pointing at the old
    install. Off-device (no payload dir) this is a no-op."""
    root = app_root()
    if root is None:
        return None
    try:
        native = native_dir()
    except RuntimeError:
        return None  # desktop dev — there is no payload dir to link into
    compiler = native / "libxkbcomp.so"
    if not compiler.is_file():
        # Fatal for the display: Xorg always spawns xkbcomp to compile its
        # keymap, so fail here with the real reason instead of a server exit.
        raise RuntimeError(f"libxkbcomp.so missing from {native}")
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name, target in (("xkbcomp", compiler), ("sh", Path(_SYSTEM_SHELL))):
        if not target.is_file():
            # The platform shell is absent only in desktop dev runs.
            logger.debug("display: %s not present at %s", name, target)
            continue
        link = bin_dir / name
        try:
            if link.is_symlink() and os.readlink(link) == str(target):
                continue
            if link.is_symlink() or link.exists():
                link.unlink()
            os.symlink(target, link)
        except OSError as exc:
            raise RuntimeError(f"could not link {link} → {target}: {exc}") from exc
    return bin_dir
