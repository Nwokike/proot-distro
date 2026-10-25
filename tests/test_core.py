"""Core-side tests: the grp/pwd shims and the payload probe."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _restore_db_modules():
    """Keep shims installed by one test from leaking into the next."""
    saved = {k: sys.modules.get(k) for k in ("pwd", "grp")}
    yield
    for k, v in saved.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v


# ── posixdb (the device-proven Android shim) ─────────────────────────────────


def test_probe_reports_real_modules():
    from core import posixdb

    probe = posixdb.probe()
    assert set(probe) == {"pwd", "grp"}
    if sys.platform == "win32":
        # Windows has neither module natively.
        assert probe == {"pwd": False, "grp": False}
    else:
        # Device truth (Android log): pwd exists, grp does not (PEP 738).
        assert probe["pwd"] is True


def test_ensure_only_shims_what_is_missing():
    from core import posixdb

    missing = [n for n in ("pwd", "grp") if not posixdb._module_present(n)]
    shimmed = posixdb.ensure()
    assert shimmed == missing


def test_grp_shim_shapes():
    """The shim's shapes are a platform-independent contract (Termux parity).

    getgrgid mirrors bionic: known AIDs and app-range gids get real names,
    everything else raises KeyError — upstream's register_android_ids_at
    skips unresolvable gids, so inventing names would write junk
    aid_<number> group entries into every install.
    """
    from core import posixdb

    grp = posixdb._shim_grp()
    entry = grp.getgrgid(3003)
    assert entry.gr_name == "inet" and entry.gr_gid == 3003 and entry.gr_mem == []
    assert grp.getgrgid(10115).gr_name == "u0_a115"
    with pytest.raises(KeyError):
        grp.getgrgid(50000)  # no name on Android either
    assert grp.getgrall() == []  # Termux parity: their stub returns NULL too
    with pytest.raises(KeyError):
        grp.getgrnam("root")


def test_pwd_shim_shapes():
    from core import posixdb

    pwd = posixdb._shim_pwd()
    entry = pwd.getpwuid(10315)
    assert entry.pw_name == "u0_a315" and entry.pw_uid == 10315
    assert entry.pw_shell == "/sbin/nologin"
    with pytest.raises(KeyError):
        pwd.getpwnam("definitely-not-a-name")


# ── probe ────────────────────────────────────────────────────────────────────


def test_probe_reports_a_problem_without_native_libs(monkeypatch):
    from core import proot_probe

    monkeypatch.delenv("ANDROID_NATIVE_LIBRARY_DIR", raising=False)
    monkeypatch.delenv("PD_PROOT_BIN", raising=False)
    result = proot_probe.ProbeResult()
    assert result.ok is True  # fresh result is fine
    # bootstrap_env with no native dir and no system proot must report the
    # sensible problem (the desktop dev case; the APK always ships proot).
    # A machine that happens to have system proot installed resolves instead.
    res = proot_probe.bootstrap_env(runtime_root=Path(os.environ.get("TMPDIR", ".")))
    if res.problems:
        assert "proot" in res.problems[0].lower()
    else:
        assert res.payload_provenance.startswith("system proot")


def test_ensure_proot_env_resolves_payload_once(monkeypatch):
    """The guarantee every proot_distro call relies on (the device terminal bug)."""
    from core import proot_probe

    monkeypatch.delenv("ANDROID_NATIVE_LIBRARY_DIR", raising=False)
    monkeypatch.delenv("PD_PROOT_BIN", raising=False)
    # Force the Android payload branch with a staged fake native dir.
    tmp = Path(tempfile.mkdtemp())
    native = tmp / "lib" / "arm64"
    native.mkdir(parents=True)
    (native / "libproot.so").write_bytes(b"proot")
    monkeypatch.setattr(proot_probe, "_native_library_dir", lambda: native)
    monkeypatch.setattr(proot_probe, "_PAYLOAD_ENV_DONE", False)
    assert proot_probe.ensure_proot_env() is True
    assert os.environ["PD_PROOT_BIN"] == str(native / "libproot.so")
    assert os.environ.get("PROOT_TMP_DIR")
    # Idempotent: a second call does not redo the resolution.
    monkeypatch.setattr(proot_probe, "_native_library_dir", lambda: None)
    assert proot_probe.ensure_proot_env() is True


def test_f2fs_probe_reports_a_verdict():
    import tempfile

    from core import proot_probe

    with tempfile.TemporaryDirectory() as d:
        verdict = proot_probe._f2fs_probe(Path(d))
    assert "f2fs" in verdict.lower()


# ── state ────────────────────────────────────────────────────────────────────


def test_state_starts_empty():
    from core.state import state

    assert state.containers == []
    assert state.installing is None
    assert state.probe_passed is False
