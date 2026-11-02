"""Regression cover for the packaged-app exit patcher (D-027).

In a `flet build` APK the build template replaces `sys.exit` with `flet_exit`
(lib/python.dart: `sys.exit = flet_exit`), which posts the exit code to the
Dart exit bridge and RETURNS — it never raises SystemExit. Upstream
`command_login(..., get_proot_cmd=True)` ends in `sys.exit(0)`, so on device
the whole app process exited 0 ("Zygote: Process N exited cleanly (0)") with no
traceback, and `except SystemExit` could not catch it. proot_service now wraps
every in-process upstream call in `_no_process_exit()`, which swaps sys.exit /
os.exec* / os._exit for raising stubs for the duration of the call.

These tests simulate the patched runtime (a RETURNING sys.exit stub, exactly
what flet_exit does) and assert the facade still returns the printed command
line without the stub ever firing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("flet")


def _hermetic_proot_distro(monkeypatch, tmp_path):
    """Fresh proot_distro bound to a tmp state tree (mirrors test_get_proot_cmd)."""
    root = tmp_path / "pd-root"
    (root / "proot-distro" / "containers").mkdir(parents=True)
    (root / "cache" / "proot-distro").mkdir(parents=True)
    (root / "temp").mkdir(parents=True)
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(root))
    monkeypatch.setenv("FLET_APP_STORAGE_CACHE", str(root / "cache"))
    monkeypatch.setenv("FLET_APP_STORAGE_TEMP", str(root / "temp"))
    fake_proot = tmp_path / "libproot.so"
    fake_proot.write_bytes(b"#!/bin/sh\nexit 0\n")
    fake_proot.chmod(0o755)
    monkeypatch.setenv("PD_PROOT_BIN", str(fake_proot))

    purged = [
        name for name in sys.modules if name == "proot_distro" or name.startswith("proot_distro.")
    ]
    for name in purged:
        monkeypatch.delitem(sys.modules, name)
    return root, fake_proot


def _install_fake_container(root: Path) -> None:
    import shutil

    rootfs = root / "proot-distro" / "containers" / "demo" / "rootfs"
    (rootfs / "bin").mkdir(parents=True)
    (rootfs / "etc").mkdir()
    (rootfs / "root").mkdir()
    shutil.copy2("/bin/sh", rootfs / "bin" / "sh")
    (rootfs / "bin" / "sh").chmod(0o755)
    (rootfs / "etc" / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\n")


def test_packaged_sys_exit_stub_never_fires_during_get_proot_cmd(monkeypatch, tmp_path):
    """Simulate the APK: sys.exit is flet_exit (records code, RETURNS).

    The guard must swap in a raising exit for the upstream call, so upstream's
    sys.exit(0) becomes a catchable SystemExit and the printed line returns.
    """
    if sys.platform == "win32":
        pytest.skip("POSIX-only integration path")

    root, fake_proot = _hermetic_proot_distro(monkeypatch, tmp_path)
    _install_fake_container(root)

    posted: list[object] = []

    def flet_exit_stub(code=0):
        posted.append(code)  # the real flet_exit posts to Dart and RETURNS

    monkeypatch.setattr(sys, "exit", flet_exit_stub)
    from services import proot_service

    line = proot_service.get_proot_cmd("demo")
    assert posted == [], "the patched sys.exit must not fire while upstream runs in-process"
    folded = line.replace("\\\n", " ")
    assert folded.lstrip().startswith("env")
    assert str(fake_proot) in folded
    # After the call the original (patched) reference is restored.
    assert sys.exit is flet_exit_stub


def test_guard_makes_exit_and_exec_raise_inside_and_restores_after():
    from services import proot_service

    real_exit = sys.exit
    real_execvpe = os.execvpe
    real__exit = os._exit
    with proot_service._no_process_exit():
        with pytest.raises(SystemExit):
            sys.exit(0)
        with pytest.raises(proot_service.ProotUnavailable):
            os.execvpe("/bin/sh", ["/bin/sh"], {})  # noqa: S606 - never runs: the guard replaces it
        with pytest.raises(proot_service.ProotUnavailable):
            os._exit(0)
    assert sys.exit is real_exit
    assert os.execvpe is real_execvpe
    assert os._exit is real__exit


def test_guard_is_refcounted_for_nested_sections():
    from services import proot_service

    real_exit = sys.exit
    with proot_service._no_process_exit():
        with proot_service._no_process_exit():  # refcount nesting is the point
            pass
        # Still guarded after the inner section exits.
        with pytest.raises(SystemExit):
            sys.exit(0)
    assert sys.exit is real_exit


def test_run_command_refuses_login_without_get_proot_cmd_even_with_patched_exit(
    monkeypatch, tmp_path
):
    """The _NO_EXEC_MODULES refusal must hold when sys.exit cannot raise."""
    if sys.platform == "win32":
        pytest.skip("POSIX-only integration path")

    _hermetic_proot_distro(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "exit", lambda code=0: None)  # flet_exit shape
    from services import proot_namespaces, proot_service

    ns = proot_namespaces._ns_login_get_proot_cmd("demo")
    ns.get_proot_cmd = False  # the landmine configuration
    with pytest.raises(proot_service.ProotUnavailable):
        proot_service._run_command("proot_distro.commands.login", "command_login", ns)


def test_both_facade_call_sites_use_the_guard():
    """Source guard: _run_command and _call_get_proot_cmd wrap fn(namespace)."""
    pkg = Path(__file__).resolve().parents[1] / "src" / "services" / "proot_service"
    src = "\n".join(p.read_text(encoding="utf-8") for p in sorted(pkg.glob("*.py")))
    for fn_name in ("def _run_command", "def _call_get_proot_cmd"):
        body = src.split(fn_name, 1)[1].split("\ndef ", 1)[0]
        assert "_no_process_exit()" in body, (
            f"{fn_name} must run every in-process upstream call under _no_process_exit()"
        )
