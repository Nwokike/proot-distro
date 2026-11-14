"""Helpers for structure-pinning tests.

A module may be split into a sibling package (`display_launcher.py` →
`display_sheets/`); assertions about content must keep working, so they read the
facade AND its package instead of a single file path.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def module_text(rel: str, package: str | None = None) -> str:
    """Text of src/<rel>, plus its split package (`package` or the sibling)."""
    path = SRC / rel
    parts = [path.read_text(encoding="utf-8")]
    candidates = []
    if package:
        candidates.append(SRC / package)
    candidates.append(path.with_suffix(""))
    for directory in candidates:
        if directory.is_dir():
            parts.extend(f.read_text(encoding="utf-8") for f in sorted(directory.glob("*.py")))
            break
    return "\n".join(parts)
