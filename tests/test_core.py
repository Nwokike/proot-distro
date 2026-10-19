"""Core-side tests: the grp/pwd shims and the payload probe."""

from __future__ import annotations

import os
import sys
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

    Called on the factories directly so the contract is covered everywhere —
    on Android these are what `ensure()` installs; on desktop the real module
    is used instead (test_ensure_only_shims_what_is_missing covers that).
    """
    from core import posixdb

    grp = posixdb._shim_grp()
    entry = grp.getgrgid(3003)
    assert entry.gr_name == "3003" and entry.gr_gid == 3003 and entry.gr_mem == []
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
    result = proot_probe.ProbeResult()
    assert result.ok is True  # fresh result is fine
    # bootstrap_env with no native dir must report the sensible problem.
    monkeypatch.delenv("ANDROID_NATIVE_LIBRARY_DIR", raising=False)
    res = proot_probe.bootstrap_env(runtime_root=Path(os.environ.get("TMPDIR", ".")))
    assert res.problems and "nativeLibraryDir" in res.problems[0]


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
