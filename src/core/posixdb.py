"""pwd/grp shims for Android CPython (grp is absent per PEP 738)."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from collections import namedtuple

_STRUCT_PASSWD = "pw_name pw_passwd pw_uid pw_gid pw_gecos pw_dir pw_shell"  # noqa: S105 - field names, not secrets
_STRUCT_GROUP = "gr_name gr_passwd gr_gid gr_mem"


def _pw_name(uid: int) -> str:
    """Android app-uid naming convention: uid 10315 -> 'u0_a315'."""
    return f"u0_a{uid - 10000}" if uid >= 10000 else str(uid)


def _gid() -> int:
    """os.getgid() is POSIX-only; the shim also runs on Windows (dev previews)."""
    getgid = getattr(os, "getgid", None)
    return getgid() if getgid else 0


def _shim_pwd() -> types.ModuleType:
    struct_passwd = namedtuple("struct_passwd", _STRUCT_PASSWD)
    mod = types.ModuleType("pwd")
    mod.struct_passwd = struct_passwd
    mod.__doc__ = "Android shim (see posixdb.py)"

    def getpwuid(uid):
        return struct_passwd(_pw_name(uid), "x", uid, _gid(), "Android app", "/", "/sbin/nologin")

    def getpwnam(name):
        uid = getattr(os, "getuid", lambda: 0)()
        if name == _pw_name(uid):
            return getpwuid(uid)
        raise KeyError(name)

    def getpwall():
        uid = getattr(os, "getuid", lambda: 0)()
        return [getpwuid(uid)]

    mod.getpwuid = getpwuid
    mod.getpwnam = getpwnam
    mod.getpwall = getpwall
    return mod


# Bionic names these supplementary gids; everything else has no group name
# on Android and getgrgid must raise KeyError (upstream's
# register_android_ids_at skips unresolvable gids — a shim that invents a
# name for every gid writes junk aid_<number> group entries instead).
_KNOWN_GIDS = {
    3001: "bt_net",
    3002: "bt_net_raw",
    3003: "inet",
    3004: "inet_raw",
    3005: "inet_admin",
    9997: "everybody",
}


def _gr_name(gid: int) -> str | None:
    if gid in _KNOWN_GIDS:
        return _KNOWN_GIDS[gid]
    if 10000 <= gid < 20000:
        # Android app uid/gid range (u0_aNNN); outside it nothing has a name.
        return f"u0_a{gid - 10000}"
    return None


def _shim_grp() -> types.ModuleType:
    struct_group = namedtuple("struct_group", _STRUCT_GROUP)
    mod = types.ModuleType("grp")
    mod.struct_group = struct_group
    mod.__doc__ = "Android shim (see posixdb.py)"

    def getgrgid(gid):
        name = _gr_name(gid)
        if name is None:
            raise KeyError(gid)
        return struct_group(name, "x", gid, [])

    def getgrnam(name):
        raise KeyError(name)

    def getgrall():
        # Termux parity: their getgrent stub returns NULL, so getgrall() is
        # always empty there too (termux-packages PR #28768).
        return []

    mod.getgrgid = getgrgid
    mod.getgrnam = getgrnam
    mod.getgrall = getgrall
    return mod


def _module_present(name: str) -> bool:
    """True when `name` is importable OR already shimmed into sys.modules.

    A shim installed by this module has `__spec__ = None`, which makes
    `importlib.util.find_spec` raise ValueError — so check the module table
    first, and treat a failed spec lookup as "not present natively".
    """
    if name in sys.modules:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except ValueError, ImportError:
        return False


def probe() -> dict[str, bool]:
    """Which of the shimmed modules exist natively (True) vs need the shim (False)."""
    return {name: _module_present(name) for name in ("pwd", "grp")}


def ensure() -> list[str]:
    """Install shims for any of pwd/grp missing from this interpreter.

    Returns the names that were shimmed (empty on normal desktop Pythons).
    """
    shimmed: list[str] = []
    for name, factory in (("pwd", _shim_pwd), ("grp", _shim_grp)):
        if _module_present(name):
            continue
        sys.modules[name] = factory()
        shimmed.append(name)
    return shimmed


_SIGNAL_GUARD_INSTALLED = False


def ensure_signal_safe() -> None:
    """Make signal.signal() a no-op off the main thread (idempotent).

    proot-distro's l2s.rewrite_l2s_targets() installs SIGINT/SIGQUIT
    handlers, and signal.signal() raises ValueError on any thread but the
    main one. On Android the Python interpreter is never the main thread
    (Flutter owns it), so every rename and every login would crash with
    "signal only works in main thread of the main interpreter". The
    handlers are decorative in this embedding — the PTY child is signalled
    through the terminal, not the Python process — so skipping them is
    behaviour-preserving.
    """
    global _SIGNAL_GUARD_INSTALLED
    if _SIGNAL_GUARD_INSTALLED:
        return
    import signal
    import threading

    if threading.current_thread() is threading.main_thread():
        # Desktop dev runs: the real signal.signal works, leave it alone.
        _SIGNAL_GUARD_INSTALLED = True
        return

    real_signal = signal.signal

    def _safe_signal(sig, handler):
        try:
            return real_signal(sig, handler)
        except ValueError:
            return None

    signal.signal = _safe_signal
    _SIGNAL_GUARD_INSTALLED = True
