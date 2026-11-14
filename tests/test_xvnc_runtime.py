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
        "libxkbcomp.so",
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


def test_xvnc_command_threads_every_real_option(fake_native, tmp_path):
    """Depth, frame rate, sharing policy, clipboard and auto-close are REAL
    Xvnc parameters — each one must appear in the argv exactly as set."""
    argv, _env = xvnc_runtime.xvnc_command(
        1,
        "1280x720",
        tmp_path / "xauth-1",
        tmp_path / "xkb",
        depth="16",
        frame_rate=15,
        shared_policy="never",
        clipboard=False,
        disconnect_timeout=1800,
        desktop_name="debian:1",
    )
    assert argv[argv.index("-depth") + 1] == "16"
    assert "-FrameRate=15" in argv
    assert "-NeverShared=1" in argv and "-DisconnectClients=1" in argv
    assert "-AlwaysShared=1" not in argv
    assert "-AcceptCutText=0" in argv and "-SendCutText=0" in argv
    assert "-MaxDisconnectionTime=1800" in argv
    assert argv[argv.index("-desktop") + 1] == "debian:1"

    # Auto policy keeps upstream defaults (no sharing flags at all).
    plain, _ = xvnc_runtime.xvnc_command(1, "1280x720", tmp_path / "x", tmp_path / "y")
    for absent in ("-AlwaysShared=1", "-NeverShared=1", "-MaxDisconnectionTime=1800"):
        assert absent not in plain
    assert "-FrameRate=30" in plain  # the app default


def test_pulse_config_mic_toggle_and_audio_knobs(fake_native, tmp_path, monkeypatch):
    """Mic off → the sles-source module line is absent (privacy); AAudio
    latency/performance mode ride the sink line (real module args)."""
    body_off = xvnc_runtime.write_pulse_config(
        tmp_path / "rt", mic=False, latency_ms=80, pm=1
    ).read_text(encoding="utf-8")
    assert "module-sles-source.so" not in body_off
    assert "sink_name=output latency=80 pm=1" in body_off
    body_on = xvnc_runtime.write_pulse_config(tmp_path / "rt2").read_text(encoding="utf-8")
    assert "module-sles-source.so" in body_on
    assert "sink_name=output pm=2" in body_on  # latency 0 → device default
    assert "latency=" not in body_on


def test_xvnc_command_creates_the_app_tmp_dir(fake_native, tmp_path):
    """The builder rewrites Xvnc's compiled Termux prefix to <app>/tmp (the lock
    file + compiled keymaps live there) — the dir must exist before start."""
    xvnc_runtime.xvnc_command(0, "1280x720", tmp_path / "xauth-0", tmp_path / "xkb")
    app_root = storage_paths.data_root().parents[1]
    assert (app_root / "tmp").is_dir()


def test_xvnc_command_links_the_baked_prefix_binaries(fake_native, tmp_path, monkeypatch):
    """Xvnc execs its baked prefix paths: `<app>//bin/sh -c "<app>//bin/xkbcomp …"`
    (os/utils.c Popen + xkb/ddxLoad.c RunXkbComp — verified in the shipped
    binary). Both must resolve to the native-lib payloads, which Android's
    exec policy allows; a plain file in the app home would be blocked."""
    shell = tmp_path / "platform-sh"
    shell.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setattr(xvnc_runtime, "_SYSTEM_SHELL", str(shell))

    xvnc_runtime.xvnc_command(0, "1280x720", tmp_path / "xauth-0", tmp_path / "xkb")
    app_root = storage_paths.data_root().parents[1]
    link = app_root / "bin" / "xkbcomp"
    assert link.is_symlink()
    assert Path(link.readlink()) == fake_native / "libxkbcomp.so"
    assert (app_root / "bin" / "sh").readlink() == shell


def test_prefix_bin_relinks_after_an_app_update(fake_native, tmp_path, monkeypatch):
    """The native-lib dir changes on every install (`/data/app/~~hash/…`); a
    stale link would point at the old dir. The target is compared, so a moved
    payload re-links and an unchanged one is left alone."""
    shell = tmp_path / "platform-sh"
    shell.write_bytes(b"#!/bin/sh\n")
    monkeypatch.setattr(xvnc_runtime, "_SYSTEM_SHELL", str(shell))
    bin_dir = xvnc_runtime.ensure_prefix_bin()
    link = bin_dir / "xkbcomp"
    link.unlink()
    link.symlink_to(tmp_path / "old-install" / "libxkbcomp.so")
    xvnc_runtime.ensure_prefix_bin()
    assert Path(link.readlink()) == fake_native / "libxkbcomp.so"
    # idempotent: same target stays untouched
    inode = link.lstat().st_ino
    xvnc_runtime.ensure_prefix_bin()
    assert link.lstat().st_ino == inode


def test_prefix_bin_fails_loudly_without_xkbcomp(fake_native):
    """Xorg ALWAYS spawns xkbcomp for its keymap; without the payload the
    server would die with a generic XKB error — name the real reason."""
    (fake_native / "libxkbcomp.so").unlink()
    with pytest.raises(RuntimeError, match=r"libxkbcomp\.so missing"):
        xvnc_runtime.ensure_prefix_bin()


def test_prefix_bin_is_a_noop_without_the_payload_dir(monkeypatch):
    """Desktop dev runs (no payload dir) must not raise or create links there."""
    import core.proot_probe as probe

    monkeypatch.setattr(probe, "_native_library_dir", lambda: None)
    assert xvnc_runtime.ensure_prefix_bin() is None


def _stub_pa_package(monkeypatch, libs, version="17.0"):
    import sys
    import types

    stub = types.ModuleType("flet_pulseaudio")
    stub.PA_VERSION = version
    stub.LIBS = list(libs)
    monkeypatch.setitem(sys.modules, "flet_pulseaudio", stub)


def test_request_mic_permission_is_a_noop_off_android():
    """RECORD_AUDIO is a dangerous permission requiring a RUNTIME grant; the
    helper asks through serious_python's Activity. On desktop (no pyjnius) it
    must degrade silently — audio only, never a display failure."""
    xvnc_runtime.request_mic_permission()  # no exception, no output


def test_pulseaudio_libs_are_staged_without_libcrypto(monkeypatch, fake_native):
    """The daemon's linker path must be a libcrypto-free staging dir — with the
    native dir on it, vendor libs that dlopen system libs expecting the old
    OpenSSL ABI fail (device 2026-11-13, module-sles-source → libsqlite)."""
    _stub_pa_package(monkeypatch, ["libpulseaudio.so", "libpulse.so", "libcrypto.so"])
    (fake_native / "libpulse.so").write_bytes(b"\x7fELF-fake")
    stage = xvnc_runtime.ensure_pa_libs()
    assert (stage / "libpulseaudio.so").is_file()
    assert (stage / "libpulse.so").is_file()
    # libcrypto is NOT in the wheel's PA payloads — never staged, never shadowing
    assert not (stage / "libcrypto.so").exists()
    _argv, env = xvnc_runtime.pulseaudio_command()
    assert env["LD_LIBRARY_PATH"] == str(stage)
    assert str(fake_native) not in env["LD_LIBRARY_PATH"]


def test_pulseaudio_command_argv(fake_native, monkeypatch):
    _stub_pa_package(monkeypatch, ["libpulseaudio.so"])
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


def test_xkb_data_is_staged_from_a_zipped_wheel(monkeypatch, tmp_path):
    """THE DEVICE SHAPE: serious_python imports pip packages from a stored ZIP
    (sitepackages.zip) — a __file__-relative data path does not exist on disk.
    The resources Traversable API must reach inside the zip (device failure
    2026-11-13: 'the xkb data is missing — the flet-xvnc wheel did not load')."""
    import sys
    import zipfile

    zip_path = tmp_path / "sitepackages.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("flet_xvnc/__init__.py", 'XVNC_VERSION = "1.16.2"\n')
        zf.writestr("flet_xvnc/data/xkb/symbols/us", "xkb_symbols\n")
        zf.writestr("flet_xvnc/data/xkb/rules/evdev", "rules\n")
    monkeypatch.syspath_prepend(str(zip_path))
    monkeypatch.delitem(sys.modules, "flet_xvnc", raising=False)
    monkeypatch.setattr(xvnc_runtime.storage_paths, "support_root", lambda: tmp_path / "support")

    dest = xvnc_runtime.ensure_xkb_dir()
    assert (dest / "symbols" / "us").read_text(encoding="utf-8") == "xkb_symbols\n"
    assert (dest / "rules" / "evdev").read_text(encoding="utf-8") == "rules\n"
    assert (dest / ".version").read_text(encoding="utf-8").strip() == "1.16.2"


def test_xkb_data_recopies_on_version_bump(monkeypatch, tmp_path):
    """Same version: no recopy (the dir may hold compiled keymaps). New version:
    re-staged from the wheel."""
    import sys

    pkg_root = tmp_path / "pkgroot"
    pkg = pkg_root / "flet_xvnc"
    (pkg / "data" / "xkb" / "symbols").mkdir(parents=True)
    (pkg / "__init__.py").write_text('XVNC_VERSION = "1.16.2"\n', encoding="utf-8")
    (pkg / "data" / "xkb" / "symbols" / "us").write_text("xkb_symbols\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(pkg_root))
    monkeypatch.delitem(sys.modules, "flet_xvnc", raising=False)
    monkeypatch.setattr(xvnc_runtime.storage_paths, "support_root", lambda: tmp_path / "support")

    dest = xvnc_runtime.ensure_xkb_dir()
    (dest / "symbols" / "us").write_text("edited", encoding="utf-8")
    # same version: edits survive
    assert xvnc_runtime.ensure_xkb_dir() == dest
    assert (dest / "symbols" / "us").read_text(encoding="utf-8") == "edited"
    # version bump: tree re-staged (clear the stale .pyc too — same size/second
    # would otherwise be accepted by the bytecode cache)
    (pkg / "__init__.py").write_text('XVNC_VERSION = "1.17.0"\n', encoding="utf-8")
    import shutil as _shutil

    _shutil.rmtree(pkg / "__pycache__", ignore_errors=True)
    monkeypatch.delitem(sys.modules, "flet_xvnc", raising=False)
    xvnc_runtime.ensure_xkb_dir()
    assert (dest / "symbols" / "us").read_text(encoding="utf-8") == "xkb_symbols\n"


def test_xkb_missing_payload_names_the_reason(monkeypatch, tmp_path):
    import sys

    monkeypatch.delitem(sys.modules, "flet_xvnc", raising=False)
    monkeypatch.setattr(xvnc_runtime.storage_paths, "support_root", lambda: tmp_path / "support")
    with pytest.raises(RuntimeError, match="payload data is unreadable"):
        xvnc_runtime.ensure_xkb_dir()


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
