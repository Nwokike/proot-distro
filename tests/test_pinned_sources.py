"""Live guard for the pinned Termux debs used by the Xvnc wheel builder.

A rotated .deb in the Termux pool has broken several builds already: the
builder fetched a pinned path and got a 404. This test resolves every pin
against the repository indexes (four small Packages.gz files), so a removed
file or a changed checksum fails the quality job before three build jobs do.
It is marked live because it fetches from the network; CI runs it as its own
step with ``uv run pytest -m live tests/test_pinned_sources.py``.
"""

from __future__ import annotations

import gzip
import importlib.util
import sys
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEXES = {
    "termux-main": (
        "https://packages.termux.dev/apt/termux-main/dists/stable/main/binary-{arch}/Packages.gz"
    ),
    "termux-x11": (
        "https://packages.termux.dev/apt/termux-x11/dists/x11/main/binary-{arch}/Packages.gz"
    ),
}


def _builder_module():
    path = ROOT / "scripts" / "build_flet_xvnc_wheel.py"
    spec = importlib.util.spec_from_file_location("_xvnc_builder_for_pins", path)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(ROOT / "scripts"))  # elf_tools next to the builder
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _index(url: str) -> dict[str, str]:
    if not url.startswith("https://packages.termux.dev/apt/"):
        raise ValueError(f"unexpected index URL: {url}")
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - scheme checked above
        text = gzip.decompress(response.read()).decode("utf-8", "replace")
    packages: dict[str, str] = {}
    for block in text.split("\n\n"):
        rel = sha = None
        for line in block.splitlines():
            if line.startswith("Filename: "):
                rel = line.split(": ", 1)[1]
            elif line.startswith("SHA256: "):
                sha = line.split(": ", 1)[1]
        if rel and sha:
            packages[rel] = sha
    return packages


@pytest.mark.live
def test_every_pinned_deb_is_present_with_the_pinned_sha256():
    builder = _builder_module()
    indexes = {
        (repo, arch): _index(template.format(arch=arch))
        for repo, template in INDEXES.items()
        for arch in builder._PINNED_SOURCES
    }
    failures: list[str] = []
    for arch, spec in builder._PINNED_SOURCES.items():
        for pkg, (rel, sha) in spec["packages"].items():
            repo = "termux-x11" if pkg in builder._X11_PACKAGES else "termux-main"
            actual = indexes[(repo, arch)].get(rel)
            if actual is None:
                failures.append(f"{arch}/{pkg}: {rel} missing from {repo}")
            elif actual != sha:
                failures.append(f"{arch}/{pkg}: {rel} sha256 {actual} != pin {sha}")
    assert not failures, "Termux pins are stale:\n  " + "\n  ".join(failures)
