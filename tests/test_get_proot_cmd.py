"""Integration contract for upstream's login command output."""

import pytest


def _hermetic_proot_distro(monkeypatch, tmp_path):
    """Fresh proot_distro bound to a tmp state tree.

    Upstream reads XDG_* at import time, so the modules are purged and the
    env set BEFORE the lazy import inside get_proot_cmd runs. Test-side
    relocation only — the app itself never patches upstream.
    """
    import sys

    root = tmp_path / "pd-root"
    # Mirror what proot_service.bootstrap() will export: XDG_DATA_HOME = the
    # data root itself; containers under <root>/proot-distro/containers.
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


def test_get_proot_cmd_runs_the_real_upstream_path(monkeypatch, tmp_path):
    """End-to-end through upstream's command_login — no golden-string mock.

    Catches the two historical breaks: running cli.main() off the main
    thread (SIGQUIT handler) and capturing into io.StringIO (no .buffer,
    which upstream's printer writes to).
    """
    import shutil
    import sys

    if sys.platform == "win32":
        pytest.skip("POSIX-only integration path")

    root, fake_proot = _hermetic_proot_distro(monkeypatch, tmp_path)
    from services import proot_service

    # A fake installed container: real ELF shell (the arch probe reads its
    # header), a passwd entry, a home dir.
    rootfs = root / "proot-distro" / "containers" / "demo" / "rootfs"
    (rootfs / "bin").mkdir(parents=True)
    (rootfs / "etc").mkdir()
    (rootfs / "root").mkdir()
    shutil.copy2("/bin/sh", rootfs / "bin" / "sh")
    (rootfs / "bin" / "sh").chmod(0o755)
    (rootfs / "etc" / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\n")

    line = proot_service.get_proot_cmd("demo")
    # Upstream wraps with backslash-newline continuations (same shape as
    # GOLDEN_CMD_WRAPPED); fold them before asserting.
    folded = line.replace("\\\n", " ")
    assert folded.lstrip().startswith("env")
    assert "-i" in folded
    assert str(fake_proot) in folded
    assert folded.rstrip().endswith("-l")  # the login shell, not a bare sh


def test_get_proot_cmd_reports_a_missing_container(monkeypatch, tmp_path):
    import sys

    if sys.platform == "win32":
        pytest.skip("POSIX-only integration path")

    _hermetic_proot_distro(monkeypatch, tmp_path)
    from services import proot_service

    with pytest.raises(RuntimeError):
        proot_service.get_proot_cmd("no-such-container")
