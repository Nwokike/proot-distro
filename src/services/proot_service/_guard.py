"""Process-exit containment for in-process upstream calls (D-027).

In a packaged Flet app the build template patches sys.exit = flet_exit,
which posts the exit code to the Dart exit bridge and RETURNS instead of
raising — so on device any sys.exit(...) kills the whole app with that
code, uncatchable. While an upstream handler runs in-process we swap
sys.exit / os.exec* / os._exit for raising stubs (refcounted, restored
afterwards). See docs/decisions.md D-027/D-028.
"""

from __future__ import annotations

import contextlib
import os
import threading


class ProotUnavailable(RuntimeError):
    """proot-distro cannot run on this interpreter (desktop Windows, no grp shim)."""


# In a packaged Flet app the build template patches `sys.exit`
# (lib/python.dart: `sys.exit = flet_exit`) into a function that posts the exit
# code to the Dart exit bridge and RETURNS — it never raises SystemExit, so
# `except SystemExit` cannot catch it and the whole app process exits with that
# code (logcat: "Zygote: Process N exited cleanly (0)", no traceback). Upstream
# login/run end in `sys.exit(0)` / `os.execvpe`; on device both are uncatchable
# process death. While an upstream handler runs in-process we swap these for
# raising stubs so every exit/exec path becomes a catchable exception again.
_EXEC_NAMES = (
    "execv",
    "execve",
    "execvp",
    "execvpe",
    "execl",
    "execle",
    "execlp",
    "execlpe",
)
_EXIT_LOCK = threading.Lock()
_EXIT_STATE = {"depth": 0, "saved": None}


def _raising_exit(code=0):
    raise SystemExit(code)


def _raising_exec(*_args, **_kwargs):
    raise ProotUnavailable(
        "in-process upstream call tried to os.exec* the app process "
        "(login/run must run with get_proot_cmd=True and be spawned on a PTY)"
    )


def _raising__exit(*_args, **_kwargs):
    raise ProotUnavailable("in-process upstream call tried os._exit")


@contextlib.contextmanager
def _no_process_exit():
    """Make sys.exit / os.exec* / os._exit raise instead of killing the process.

    Active only while an upstream command_* handler runs in-process; the real
    (possibly flet-patched) references are restored when the last guarded
    section exits. Refcounted, so a long install does not block a session open.
    On desktop this is semantics-identical: the real sys.exit raises anyway.
    subprocess/os.posix_spawn are unaffected (the C _posixsubprocess module
    calls execv directly, not the patched Python attribute).
    """
    import sys

    with _EXIT_LOCK:
        if _EXIT_STATE["depth"] == 0:
            _EXIT_STATE["saved"] = (
                sys.exit,
                {name: getattr(os, name) for name in _EXEC_NAMES},
                os._exit,
            )
            sys.exit = _raising_exit
            for name in _EXEC_NAMES:
                setattr(os, name, _raising_exec)
            os._exit = _raising__exit
        _EXIT_STATE["depth"] += 1
    try:
        yield
    finally:
        with _EXIT_LOCK:
            _EXIT_STATE["depth"] -= 1
            if _EXIT_STATE["depth"] == 0 and _EXIT_STATE["saved"] is not None:
                saved_exit, saved_exec, saved__exit = _EXIT_STATE["saved"]
                sys.exit = saved_exit
                for name, fn in saved_exec.items():
                    setattr(os, name, fn)
                os._exit = saved__exit
                _EXIT_STATE["saved"] = None


# Upstream login/run end in os.execvpe when get_proot_cmd is False, which would
# replace the whole app process with proot — a clean, traceless disappearance
# on device. In-process calls to these handlers must print the command line
# instead (get_proot_cmd=True); the PTY session spawns it. _run_command refuses
