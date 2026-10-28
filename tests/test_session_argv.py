"""Upstream login command parsing contract."""

import pytest
from session_support import GOLDEN_CMD, GOLDEN_CMD_WRAPPED

from services import session_service


async def test_session_argv_parses_env_and_command(monkeypatch):
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )
    # The host essentials are merged over the guest env — clear them so the
    # parse is deterministic (CI runners set LD_LIBRARY_PATH themselves).
    for key in session_service._HOST_ESSENTIALS:
        monkeypatch.delenv(key, raising=False)

    env, argv = session_service.session_argv("debian")

    assert env["TERM"] == "xterm-256color"
    assert env["HOME"] == "/root"
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["LD_LIBRARY_PATH"].endswith("/files/usr/lib")
    assert argv[0].endswith("libproot.so")
    assert "--change-id=0:0" in argv
    assert argv[-2:] == ["/bin/bash", "-l"]


async def test_session_argv_merges_the_host_essentials(monkeypatch):
    """Proot needs LD_LIBRARY_PATH/PROOT_LOADER; upstream's env is clean."""
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )
    monkeypatch.setenv("LD_LIBRARY_PATH", "/data/data/app/files/usr/lib")
    monkeypatch.setenv("PROOT_LOADER", "/data/data/app/files/usr/lib/libproot-loader.so")

    env, _argv = session_service.session_argv("debian")
    assert env["LD_LIBRARY_PATH"] == "/data/data/app/files/usr/lib"
    assert env["PROOT_LOADER"].endswith("libproot-loader.so")


async def test_session_argv_rejects_garbage(monkeypatch):
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: "not-a-command"
    )

    with pytest.raises(RuntimeError):
        session_service.session_argv("debian")


async def test_session_argv_rejects_empty_command(monkeypatch):
    monkeypatch.setattr(session_service.proot_service, "get_proot_cmd", lambda c: "env -i")

    with pytest.raises(RuntimeError):
        session_service.session_argv("debian")


async def test_session_argv_handles_upstreams_wrapped_output(monkeypatch):
    """The real --get-proot-cmd format is backslash-newline wrapped."""
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD_WRAPPED
    )
    for key in session_service._HOST_ESSENTIALS:
        monkeypatch.delenv(key, raising=False)

    env, argv = session_service.session_argv("debian")
    assert env["TERM"] == "xterm-256color"
    assert "n" not in argv
    assert argv[0].endswith("libproot.so")
    assert argv[-2:] == ["/bin/bash", "-l"]
