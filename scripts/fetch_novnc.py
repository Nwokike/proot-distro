#!/usr/bin/env python3
"""Fetch the pinned noVNC release into the vendored viewer directory.

The display viewer is noVNC (MPL-2.0): its core/ + vendor/ JS is vendored into
`src/services/desk_service/novnc/` and served by our stream server, next to our
own index.html. Bumping = editing NOVNC_VERSION + TARBALL_SHA256 (one commit),
then re-running this script and committing the refreshed files. Stdlib only.

Usage: uv run python scripts/fetch_novnc.py
"""

from __future__ import annotations

import hashlib
import io
import shutil
import tarfile
import urllib.request
from pathlib import Path

NOVNC_VERSION = "1.7.0"
TARBALL_URL = f"https://github.com/novnc/noVNC/archive/refs/tags/v{NOVNC_VERSION}.tar.gz"
TARBALL_SHA256 = "b1003a11b6e6e8d8f7f5e5586daae7f8ca651d8aee0aa155ff9ac841c48f52c6"

DEST = Path(__file__).resolve().parent.parent / "src" / "services" / "desk_service" / "novnc"
# Only the viewer library ships — not noVNC's own app UI (we have index.html).
VENDORED_PREFIXES = ("core/", "vendor/")
KEEP = ("LICENSE.txt", "VERSION")


def fetch() -> bytes:
    request = urllib.request.Request(TARBALL_URL, headers={"User-Agent": "kiri-fetch-novnc/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - pinned https
        return response.read()


def main() -> int:
    blob = fetch()
    got = hashlib.sha256(blob).hexdigest()
    if got != TARBALL_SHA256:
        raise SystemExit(
            f"noVNC {NOVNC_VERSION} tarball sha256 mismatch\n"
            f"  expected {TARBALL_SHA256}\n  got      {got}"
        )
    dest = DEST
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    prefix = f"noVNC-{NOVNC_VERSION}/"
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for member in tar.getmembers():
            rel = member.name.removeprefix(prefix)
            if not rel or member.isdir():
                continue
            if not rel.startswith(VENDORED_PREFIXES) and rel not in KEEP:
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym():
                continue
            extracted = tar.extractfile(member)
            if extracted is not None:
                target.write_bytes(extracted.read())
    (dest / "PROVENANCE").write_text(
        f"noVNC {NOVNC_VERSION} — core/ + vendor/ vendored from {TARBALL_URL}\n"
        f"tarball sha256 {TARBALL_SHA256}\n"
        "License: MPL-2.0 (see LICENSE.txt). Refresh with scripts/fetch_novnc.py.\n",
        encoding="utf-8",
    )
    files = sorted(p.relative_to(dest) for p in dest.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    print(f"vendored noVNC {NOVNC_VERSION}: {len(files)} files, {total / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
