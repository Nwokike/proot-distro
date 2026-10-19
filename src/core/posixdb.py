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


def _shim_grp() -> types.ModuleType:
    struct_group = namedtuple("struct_group", _STRUCT_GROUP)
    mod = types.ModuleType("grp")
    mod.struct_group = struct_group
    mod.__doc__ = "Android shim (see posixdb.py)"

    def getgrgid(gid):
        # proot-distro prefixes "aid_" itself; numeric names reproduce
        # Android's aid_<gid> convention exactly.
        return struct_group(str(gid), "x", gid, [])

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
