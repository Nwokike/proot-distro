"""The run-it-first gate, enforced by the suite: every `ft.*` chain in `src/`
must exist in the INSTALLED flet (the ElevatedButton / `ft.border.all` class of
crash — an APK was handed over before this check existed and died on the
owner's phone). The guard itself is `tests/check_flet_api.py`; this test runs
it over every source file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = Path(__file__).resolve().parent / "check_flet_api.py"
SRC = ROOT / "src"


def _src_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_guard_covers_every_source_file():
    assert _src_files(), "no src files found — the guard would silently cover nothing"


def test_every_source_file_passes_the_api_guard():
    for target in _src_files():
        proc = subprocess.run(
            [sys.executable, str(GUARD), str(target)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert proc.returncode == 0, (
            f"{target.name}: flet API guard failed\n{proc.stdout}\n{proc.stderr}"
        )
