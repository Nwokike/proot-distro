"""Core of the proot-distro facade: bootstrap, import gate, command runner."""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
import os
from dataclasses import dataclass
from types import SimpleNamespace

from core import storage_paths
from services.proot_runtime import _LineTee

from ._guard import ProotUnavailable, _no_process_exit

logger = logging.getLogger(__name__)


_BOOTSTRAPPED = False

_NO_EXEC_MODULES = frozenset({"proot_distro.commands.login", "proot_distro.commands.run"})


@dataclass
class Outcome:
    ok: bool
    detail: str
    output: str = ""


def bootstrap() -> None:
    """Env contract + shims before the first proot_distro import (idempotent).

    Also resolves the payload env (PD_PROOT_BIN / PROOT_LOADER /
    LD_LIBRARY_PATH / PROOT_TMP_DIR) so every upstream call — including
    `login --get-proot-cmd`, which needs the proot binary — finds the binary
    even if the startup probe's native-dir lookup missed it.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    from core import posixdb

    posixdb.ensure()
    posixdb.ensure_signal_safe()
    os.environ.update(storage_paths.env_contract())
    from core import proot_probe

    proot_probe.ensure_proot_env()
    _BOOTSTRAPPED = True


def available() -> bool:
    bootstrap()
    try:
        importlib.import_module("proot_distro")
    except Exception:
        return False
    return True


def _imp(module_name: str):
    """Import an upstream module after bootstrap; ProotUnavailable when absent.

    The facade is the sole importer, and a missing proot_distro must surface as
    a real reason in the UI (state.data_note), not a raw ModuleNotFoundError
    that kills init — that is what running under the wrong interpreter (system
    flet/python without the project venv) looked like.
    """
    bootstrap()
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise ProotUnavailable(f"proot_distro unavailable: {exc!r}") from exc


def _run_command(
    module_name: str, fn_name: str, namespace: SimpleNamespace, on_line=None
) -> Outcome:
    """Run one upstream command_* handler with captured output.

    When `on_line` is given, upstream's stderr stage lines are forwarded live
    (the UI's progress source) as well as captured for the final report.
    """
    if module_name in _NO_EXEC_MODULES and not getattr(namespace, "get_proot_cmd", False):
        raise ProotUnavailable(
            f"refusing in-process {module_name}.{fn_name} without get_proot_cmd=True: "
            "upstream ends in os.execvpe and would replace the app process"
        )
    module = _imp(module_name)
    fn = getattr(module, fn_name)
    buf = io.StringIO()
    tee: _LineTee | None = None
    try:
        if on_line is not None:
            tee = _LineTee(on_line)
            with (
                contextlib.redirect_stdout(buf),
                contextlib.redirect_stderr(tee),
                _no_process_exit(),
            ):
                fn(namespace)
        else:
            with (
                contextlib.redirect_stdout(buf),
                contextlib.redirect_stderr(buf),
                _no_process_exit(),
            ):
                fn(namespace)
        captured = buf.getvalue() + (tee.getvalue() if tee is not None else "")
        return Outcome(True, "completed", captured)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        captured = buf.getvalue() + (tee.getvalue() if tee is not None else "")
        if code == 0:
            return Outcome(True, "no-op", captured)
        return Outcome(False, f"proot-distro exited {code}", captured)
    except Exception as exc:
        captured = buf.getvalue() + (tee.getvalue() if tee is not None else "")
        return Outcome(False, f"{exc}", captured)
