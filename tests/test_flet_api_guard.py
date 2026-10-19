"""The run-it-first gate, enforced by the suite: every `ft.*` chain in `src/`
must exist in the INSTALLED flet (the ElevatedButton / `ft.border.all` class of
crash — an APK was handed over before this check existed and died on the
owner's phone). The guard itself is `tests/check_flet_api.py`; this test runs
it in-process over every source file."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = Path(__file__).resolve().parent / "check_flet_api.py"
SRC = ROOT / "src"


def _load_guard():
    spec = importlib.util.spec_from_file_location("check_flet_api", GUARD)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _src_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_guard_covers_every_source_file():
    assert _src_files(), "no src files found — the guard would silently cover nothing"


def test_every_source_file_passes_the_api_guard():
    guard = _load_guard()
    argv_backup = sys.argv[:]
    failures: list[str] = []
    try:
        for target in _src_files():
            sys.argv = ["check_flet_api.py", str(target)]
            if guard.main() != 0:
                failures.append(str(target))
    finally:
        sys.argv = argv_backup
    assert not failures, f"flet API guard failed for: {failures}"
