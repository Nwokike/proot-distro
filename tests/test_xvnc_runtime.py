"""xvnc_runtime — the in-app payload contract: xauth bytes, payload lookup,
Xvnc/PulseAudio commands, xkb staging, spawn shape. All Android-only paths are
tested by patching `core.proot_probe._native_library_dir` (the conftest fakes a
desktop by simply not setting it).
"""

from __future__ import annotations

import socket
import struct
from pathlib import Path

import pytest

from core import storage_paths
from services.desk_service import xvnc_runtime

FAKE_COOKIE = "ab" * 16


@pytest.fixture
def fake_native(monkeypatch, tmp_path):
    """A fake APK native-lib dir with every payload present."""
    lib = tmp_path / "lib" / "arm64"
    lib.mkdir(parents=True)
    for name in (
        "libXvnc.so",
        "libpulseaudio.so",
        "module-aaudio-sink.so",
        "module-null-sink.so",
        "module-sles-source.so",
        "module-native-protocol-tcp.so",
    ):
        (lib / name).write_bytes(b"\x7fELF-fake")
    import core.proot_probe as probe

    monkeypatch.setattr(probe, "_native_library_dir", lambda: lib)
    return lib


# ── xauth bytes — the no-xauth-binary contract ───────────────────────────────


def _parse_xauth(blob: bytes) -> list[dict]:
    """Walk the .Xauthority record format back: family u16BE, then four
    length-prefixed fields (address, number, name, data)."""
    records = []
    off = 0
    while off < len(blob):
        (family,) = struct.unpack_from(">H", blob, off)
        off += 2
        fields = {}
        for field in ("addr", "number", "name", "data"):
            (length,) = struct.unpack_from(">H", blob, off)
            off += 2
            fields[field] = blob[off : off + length]
            off += length
        records.append({"family": family, **fields})
    return records


def test_xauth_records_parse_back():
    records = _parse_xauth(xvnc_runtime.xauth_bytes(FAKE_COOKIE, 3))
    assert [r["family"] for r in records] == [
        xvnc_runtime._FAMILY_WILD,
        xvnc_runtime._FAMILY_LOCAL,
        xvnc_runtime._FAMILY_INTERNET,
    ]
    wild, local, inet = records
    assert wild["addr"] == b""  # matches anything
    assert local["addr"] == b"localhost"  # the guest's unix socket
    assert inet["addr"] == b"127.0.0.1"  # the loopback TCP server
    for record in records:
        assert record["number"] == b"3"
        assert record["name"] == b"MIT-MAGIC-COOKIE-1"
        assert record["data"] == bytes.fromhex(FAKE_COOKIE)


def test_xauth_bytes_rejects_bad_input():
    with pytest.raises(ValueError):
        xvnc_runtime.xauth_bytes("zz", 0)
    with pytest.raises(ValueError):
        xvnc_runtime.xauth_bytes("ab" * 16, 100)
    with pytest.raises(ValueError):
        xvnc_runtime.xauth_bytes("ab" * 16, -1)


def test_write_xauth_file_creates_and_locks(tmp_path):
    path = tmp_path / "rootfs" / "tmp" / "x11" / "xauth-0"
    out = xvnc_runtime.write_xauth_file(FAKE_COOKIE, 0, path)
    assert out == path
    assert path.is_file()
    assert path.read_bytes() == xvnc_runtime.xauth_bytes(FAKE_COOKIE, 0)
    assert path.stat().st_mode & 0o777 == 0o600


def test_guest_cookie_path_shape():
    path = xvnc_runtime.guest_cookie_path("debian", 7)
    root = storage_paths.containers_dir()
    assert path == root / "debian" / "rootfs" / "tmp" / "x11" / "xauth-7"


# ── payload lookup ───────────────────────────────────────────────────────────


def test_native_dir_requires_the_payloads(monkeypatch):
    """Desktop/dev runs have no payloads — the failure names the reason.
    (Deterministic: earlier tests may leave a resolvable payload env behind.)"""
    import core.proot_probe as probe

    monkeypatch.setattr(probe, "_native_library_dir", lambda: None)
    with pytest.raises(RuntimeError, match="not available in this environment"):
        xvnc_runtime.native_dir()


def test_module_path_resolves_and_validates(fake_native):
    assert xvnc_runtime.module_path("module-aaudio-sink.so") == (
        fake_native / "module-aaudio-sink.so"
    )
    with pytest.raises(ValueError):
        xvnc_runtime.module_path("sub/module-aaudio-sink.so")
    with pytest.raises(ValueError):
        xvnc_runtime.module_path("module-aaudio-sink")
    with pytest.raises(RuntimeError):
        xvnc_runtime.module_path("module-not-there.so")


# ── commands ─────────────────────────────────────────────────────────────────


def test_xvnc_command_argv_and_env(fake_native):
    argv, env = xvnc_runtime.xvnc_command(
        2, "1280x720", fake_native.parent / "xauth-2", fake_native.parent / "xkb"
    )
    assert argv[0] == str(fake_native / "libXvnc.so")
    assert ":2" in argv
    for flag in (
        "-geometry",
        "1280x720",
        "-depth",
        "24",
        "-rfbport",
        "5902",
        "-SecurityTypes",
        "None",
        "-auth",
        "-xkbdir",
        "-listen",
        "tcp",
        "-nolisten",
        "unix",
        "-noreset",
    ):
        assert flag in argv
    assert argv[argv.index("-auth") + 1].endswith("xauth-2")
    # The payloads were built for the Termux prefix — everything they touch is
    # redirected into the app's own dirs.
    assert str(fake_native) in env["LD_LIBRARY_PATH"]
    assert env["HOME"] == str(storage_paths.data_root())
    assert env["TMPDIR"] == str(storage_paths.temp_root())
    assert "XDG_RUNTIME_DIR" in env


def test_pulseaudio_command_argv(fake_native):
    argv, _env = xvnc_runtime.pulseaudio_command()
    assert argv[0] == str(fake_native / "libpulseaudio.so")
    joined = " ".join(argv)
    for flag in (
        "--daemonize=no",
        "--exit-idle-time=-1",
        "--fail=0",
        "-n",
        "--file=",
    ):
        assert flag in joined
    # the daemon script rides with the command and loads OUR modules
    file_arg = next(a for a in argv if a.startswith("--file="))
    script = Path(file_arg.removeprefix("--file="))
    body = script.read_text(encoding="utf-8")
    assert f"load-module {fake_native / 'module-aaudio-sink.so'} sink_name=output" in body
    assert f"load-module {fake_native / 'module-sles-source.so'} source_name=mic" in body
    assert (
        f"load-module {fake_native / 'module-native-protocol-tcp.so'}"
        f" port={xvnc_runtime.PULSE_TCP_PORT} listen=127.0.0.1"
        " auth-ip-acl=127.0.0.1 auth-anonymous=1" in body
    )


# ── xkb staging ──────────────────────────────────────────────────────────────


def _stage_xkb_source(tmp_path):
    source = tmp_path / "wheel" / "xkb"
    (source / "symbols").mkdir(parents=True)
    (source / "symbols" / "us").write_text("xkb_symbols\n")
    return source


def test_ensure_xkb_dir_copies_once_then_on_version_bump(monkeypatch, tmp_path):
    import sys
    import types

    source = _stage_xkb_source(tmp_path)
    stub = types.ModuleType("flet_xvnc")
    stub.__file__ = str(tmp_path / "wheel" / "flet_xvnc" / "__init__.py")
    stub.XVNC_VERSION = "1.16.2"
    monkeypatch.setitem(sys.modules, "flet_xvnc", stub)
    monkeypatch.setattr(xvnc_runtime, "_xkb_source", lambda: source)

    dest = xvnc_runtime.ensure_xkb_dir()
    assert (dest / "symbols" / "us").is_file()

    # same version: no recopy (edits survive — the dir may hold compiled keymaps)
    (dest / "symbols" / "us").write_text("edited")
    assert xvnc_runtime.ensure_xkb_dir() == dest
    assert (dest / "symbols" / "us").read_text(encoding="utf-8") == "edited"

    # version bump: the tree is re-staged from the wheel
    stub.XVNC_VERSION = "1.17.0"
    xvnc_runtime.ensure_xkb_dir()
    assert (dest / "symbols" / "us").read_text(encoding="utf-8") == "xkb_symbols\n"


# ── audio probe + spawn shape ────────────────────────────────────────────────


def test_probe_pulseaudio_true_and_false(monkeypatch):
    calls = []

    def fake_connect(addr, timeout):
        calls.append((addr, timeout))
        if len(calls) == 1:
            raise OSError("refused")

    class _Sock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        socket, "create_connection", lambda *a, **kw: fake_connect(*a, **kw) or _Sock()
    )
    assert xvnc_runtime.probe_pulseaudio() is False
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: _Sock())
    assert xvnc_runtime.probe_pulseaudio() is True


def test_spawn_uses_its_own_process_group(monkeypatch):
    seen = {}

    def fake_popen(argv, **kw):
        seen.update(kw)
        return type("P", (), {"pid": 5, "stdout": None, "poll": lambda self: None})()

    monkeypatch.setattr(xvnc_runtime.subprocess, "Popen", fake_popen)
    xvnc_runtime.spawn(["/bin/true"], {})
    assert seen["start_new_session"] is True
    assert seen["stdout"] == xvnc_runtime.subprocess.PIPE
