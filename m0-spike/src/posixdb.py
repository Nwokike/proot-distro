"""Minimal `grp`/`pwd` shims for Android's embedded CPython.

VERIFIED: CPython's Android port excludes `grp` (PEP 738, "Unsupported
modules": curses/readline, dbm.gnu, dbm.ndbm, grp, multiprocessing,
tkinter/turtle) — and the device log confirms `ModuleNotFoundError: No
module named 'grp'`. `pwd` is NOT in PEP 738's unsupported list, so it may
well exist on the device; `probe()` reports device truth and `ensure()`
installs a shim for whichever module is actually missing.

`proot-distro` imports both unconditionally (`helpers/rootfs.py:42-44`) and
uses exactly two calls while registering the Android uid/gid entries into a
container's /etc files:

    pwd.getpwuid(os.getuid()).pw_name   -> written as  aid_{name}
    grp.getgrgid(g).gr_name             -> written as  aid_{name}

The shims reproduce Android's own `u0_a<uid>` / numeric-group naming, so the
guest ends up with entries like:

    aid_u0_a315:x:10315:10315:Termux:/:/sbin/nologin
    aid_3003:x:3003:root,aid_u0_a315

This is a platform-capability shim, not an upstream patch: nothing inside
proot-distro is modified, and nothing is invented beyond the two accessors
the library actually calls (unknown lookups raise KeyError, matching CPython).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from collections import namedtuple

_STRUCT_PASSWD = "pw_name pw_passwd pw_uid pw_gid pw_gecos pw_dir pw_shell"
_STRUCT_GROUP = "gr_name gr_passwd gr_gid gr_mem"


def _pw_name(uid: int) -> str:
    """Android app-uid naming convention: uid 10315 -> 'u0_a315'."""
    return f"u0_a{uid - 10000}" if uid >= 10000 else str(uid)


def _shim_pwd() -> types.ModuleType:
    struct_passwd = namedtuple("struct_passwd", _STRUCT_PASSWD)
    mod = types.ModuleType("pwd")
    mod.struct_passwd = struct_passwd
    mod.__doc__ = "Android shim (see posixdb.py)"

    def getpwuid(uid):
        return struct_passwd(_pw_name(uid), "x", uid, os.getgid(), "Android app", "/", "/sbin/nologin")

    def getpwnam(name):
        uid = os.getuid()
        if name == _pw_name(uid):
            return getpwuid(uid)
        raise KeyError(name)

    def getpwall():
        return [getpwuid(os.getuid())]

    mod.getpwuid = getpwuid
    mod.getpwnam = getpwnam
    mod.getpwall = getpwall
    return mod


def _shim_grp() -> types.ModuleType:
    struct_group = namedtuple("struct_group", _STRUCT_GROUP)
    mod = types.ModuleType("grp")
    mod.struct_group = struct_group
    mod.__doc__ = "Android shim (see posixdb.py)"

    def _gids():
        out: list[int] = []
        seen: set[int] = set()
        gids = [os.getgid()]
        if hasattr(os, "getgroups"):
            gids.extend(os.getgroups())
        for g in gids:
            if g not in seen:
                seen.add(g)
                out.append(g)
        return out

    def getgrgid(gid):
        # proot-distro prefixes "aid_" itself; numeric names reproduce
        # Android's aid_<gid> convention exactly.
        return struct_group(str(gid), "x", gid, [])

    def getgrnam(name):
        raise KeyError(name)

    def getgrall():
        return [getgrgid(g) for g in _gids()]

    mod.getgrgid = getgrgid
    mod.getgrnam = getgrnam
    mod.getgrall = getgrall
    return mod


def probe() -> dict[str, bool]:
    """Which of the shimmed modules exist natively (True) vs need the shim (False)."""
    return {name: importlib.util.find_spec(name) is not None for name in ("pwd", "grp")}


def ensure() -> list[str]:
    """Install shims for any of pwd/grp missing from this interpreter.

    Returns the names that were shimmed (empty on normal desktop Pythons).
    """
    shimmed: list[str] = []
    for name, factory in (("pwd", _shim_pwd), ("grp", _shim_grp)):
        if importlib.util.find_spec(name) is not None:
            continue
        sys.modules[name] = factory()
        shimmed.append(name)
    return shimmed
