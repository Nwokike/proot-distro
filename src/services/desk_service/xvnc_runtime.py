"""In-app Xvnc + PulseAudio runtime — the display payloads run from the APK's
native-library dir, exactly like proot (no guest installs, no capture pipeline).

Xvnc is an X server AND a VNC server in one process: the guest's apps draw on its
display over loopback TCP, the app's stream server proxies RFB over WebSocket to
the noVNC viewer, and the framebuffer never touches Python. PulseAudio (Termux's
Android-patched build) plays guest audio straight to the phone's speakers via the
aaudio module and feeds the mic back through sles-source — guest apps connect with
PULSE_SERVER=127.0.0.1 (proot shares the host loopback).

Everything here is device-gated: the payloads ship as jniLibs (libXvnc.so /
libpulseaudio.so / module-*.so), so this module only works inside the packaged
Android app — desktop dev runs keep the display feature unavailable, same as the
WebView itself.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import struct
import subprocess
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


def _xkb_source() -> Path | None:
    """The xkb tree inside the flet-xvnc wheel (share/xkeyboard-config-2 content)."""
    try:
        import flet_xvnc  # type: ignore[import-not-found]
    except Exception:  # desktop/dev runs — the payload wheel is Android-only
        return None
    path = Path(getattr(flet_xvnc, "__file__", "")).parent / "data" / "xkb"
    return path if path.is_dir() else None


def ensure_xkb_dir() -> Path:
    """Copy the xkb tree to a writable dir (Xvnc may write compiled keymaps
    beside it) and return it for -xkbdir."""
    source = _xkb_source()
    if source is None:
        raise RuntimeError("the xkb data is missing — the flet-xvnc wheel did not load")
    runtime = storage_paths.support_root() / "runtime"
    dest = runtime / "xkb"
    marker = dest / ".version"
    version = ""
    try:
        import flet_xvnc  # type: ignore[import-not-found]

        version = str(getattr(flet_xvnc, "XVNC_VERSION", ""))
    except Exception:
        pass
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == version:
        return dest
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(source, dest)
    marker.write_text(version, encoding="utf-8")
    logger.info("xkb data staged at %s (%s)", dest, version or "unknown version")
    return dest


# ── process commands ─────────────────────────────────────────────────────────


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


def xvnc_command(
    display: int, geometry: str, xauth_path: Path, xkb_dir: Path
) -> tuple[list[str], dict[str, str]]:
    """The Xvnc argv + env. RFB stays loopback-only (TigerVNC defaults -localhost
    to yes since 1.11 — our stream server is the only client, also local). The
    X port 6000+N serves the guest apps and is gated by the cookie file."""
    binary = xvnc_binary()
    argv = [
        str(binary),
        f":{display}",
        "-geometry",
        geometry,
        "-depth",
        "24",
        "-rfbport",
        str(RFB_PORT_BASE + display),
        "-SecurityTypes",
        "None",
        "-auth",
        str(xauth_path),
        "-xkbdir",
        str(xkb_dir),
        # The unix socket lives under /tmp/.X11-unix, which does not exist on
        # Android; the guest apps connect over TCP anyway (shared loopback).
        # -listen tcp sets PartialNetwork, so the missing unix socket is
        # tolerated instead of a FatalError.
        "-listen",
        "tcp",
        "-nolisten",
        "unix",
        "-noreset",
    ]
    return argv, _payload_env(binary.parent)


def write_pulse_config(runtime: Path) -> Path:
    """The daemon script: load OUR modules by absolute path (the compiled module
    dir is the Termux prefix, which does not exist in the app) and serve guests
    on the shared loopback only."""
    pa_dir = runtime / "pulse"
    pa_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        # speakers (AAudio — the OpenSL ES sink broke on Android 16)
        f"load-module {module_path('module-aaudio-sink.so')} sink_name=output",
        # fallback when the device audio stack refuses the sink above
        f"load-module {module_path('module-null-sink.so')} sink_name=fallback",
        # microphone (guest apps record through PULSE_SERVER)
        f"load-module {module_path('module-sles-source.so')} source_name=mic",
        # serve guest apps over loopback TCP
        (
            f"load-module {module_path('module-native-protocol-tcp.so')}"
            f" port={PULSE_TCP_PORT} listen=127.0.0.1"
            " auth-ip-acl=127.0.0.1 auth-anonymous=1"
        ),
    ]
    path = pa_dir / "default.pa"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def pulseaudio_command() -> tuple[list[str], dict[str, str]]:
    """The PulseAudio daemon argv + env (one app-wide daemon; the manager starts
    it with the first display and stops it with the last). -n skips the missing
    system default.pa; -F runs ours, which loads every module by absolute path."""
    binary = pulseaudio_binary()
    runtime = storage_paths.support_root() / "runtime"
    script = write_pulse_config(runtime)
    argv = [
        str(binary),
        "--daemonize=no",
        "--exit-idle-time=-1",
        "--disallow-exit=1",
        "--use-pid-file=false",
        "--fail=0",
        "-n",
        f"--file={script}",
    ]
    return argv, _payload_env(binary.parent)


def probe_pulseaudio() -> bool:
    """True when the daemon answers on the loopback TCP port."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", PULSE_TCP_PORT), timeout=0.5):
            return True
    except OSError:
        return False


def spawn(argv: list[str], env: dict[str, str]) -> subprocess.Popen:
    """One payload process in its own group (the desk manager kills groups)."""
    return subprocess.Popen(  # noqa: S603 - our own pinned payload binaries
        argv,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
        start_new_session=True,
    )
