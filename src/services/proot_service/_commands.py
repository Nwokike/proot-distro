"""The print-only login/run command lines (get_proot_cmd family)."""

from __future__ import annotations

import io
import logging
import threading

from services.proot_namespaces import _ns_login_get_proot_cmd, _ns_run
from services.proot_runtime import _CapturedStdout

from ._core import _imp
from ._guard import _no_process_exit

logger = logging.getLogger(__name__)


_GET_PROOT_CMD_LOCK = threading.Lock()


def _call_get_proot_cmd(module_name: str, fn_name: str, namespace, _retry: bool = True) -> str:
    """Run an upstream command handler with get_proot_cmd=True; return the printed line.

    Calls the handler directly (never `cli.main()`: it installs a SIGQUIT
    handler, main-thread-only, and a subprocess is impossible on Android —
    `sys.executable` is the Flutter host). With get_proot_cmd=True upstream
    prints the `env -i …` line via sys.stdout.buffer and sys.exit(0)s before
    any exec, so this can never replace the app process; parsing lives in
    session_service.
    """
    module = _imp(module_name)
    fn = getattr(module, fn_name)
    import sys

    with _GET_PROOT_CMD_LOCK:
        stdout_backup = sys.stdout
        stderr_backup = sys.stderr
        captured = _CapturedStdout()
        errors = io.StringIO()
        sys.stdout = captured
        sys.stderr = errors
        try:
            with _no_process_exit():
                fn(namespace)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code != 0:
                reason = errors.getvalue().strip().splitlines()
                detail = reason[-1][:200] if reason else "no output"
                # The payload env can resolve late on device (the probe's
                # native-dir glob is not the only path). Re-resolve and retry
                # once before surfacing the failure.
                if _retry and "proot utility does not exist" in errors.getvalue().lower():
                    from core import proot_probe

                    if proot_probe.ensure_proot_env(force=True):
                        logger.info("proot payload resolved on retry — retrying %s", fn_name)
                        sys.stdout = stdout_backup
                        sys.stderr = stderr_backup
                        return _call_get_proot_cmd(module_name, fn_name, namespace, _retry=False)
                raise RuntimeError(f"{fn_name} --get-proot-cmd exited {code} — {detail}") from exc
        finally:
            sys.stdout = stdout_backup
            sys.stderr = stderr_backup
    return captured.value


def get_proot_cmd(container: str, _retry: bool = True) -> str:
    """Upstream's own session command line: `pd login <c> --get-proot-cmd`."""
    return _call_get_proot_cmd(
        "proot_distro.commands.login", "command_login", _ns_login_get_proot_cmd(container), _retry
    )


def run_command_argv(container: str, run_args: list[str], work_dir: str | None = None) -> str:
    """The printed command line for `pd run <c> -- args` (Entrypoint/Cmd + args).

    Safe by construction: the namespace carries get_proot_cmd=True, so upstream
    prints and exits instead of os.execvpe-ing the app process. The caller
    parses the line and spawns it on a PTY (session_service.run_argv).
    """
    ns = _ns_run(container, list(run_args), work_dir, get_proot_cmd=True)
    return _call_get_proot_cmd("proot_distro.commands.run", "command_run", ns)


def get_proot_cmd_with_options(container: str, **login_opts) -> str:
    """`pd login <c> --get-proot-cmd` with login/run options (user, env, binds…).

    Same print-only contract as get_proot_cmd (get_proot_cmd=True upstream).
    """
    return _call_get_proot_cmd(
        "proot_distro.commands.login",
        "command_login",
        _ns_login_get_proot_cmd(container, **login_opts),
    )
