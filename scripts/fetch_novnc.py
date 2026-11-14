#!/usr/bin/env python3
"""Fetch the pinned noVNC release into the vendored viewer directory.

The display viewer IS upstream noVNC (MPL-2.0), vendored VERBATIM — vnc.html
plus its whole app/ (keyboard/clipboard/extra-keys/reconnect UI), core/ and
vendor/ — served as-is by the stream server. No viewer code is maintained
here: bumping = editing NOVNC_VERSION + TARBALL_SHA256 (one commit), then
re-running this script and committing the refreshed files. Deployment-wide
defaults ride upstream's own `defaults.json` override (see DEPLOYMENT_DEFAULTS
below); the access code gate lives in the stream server, not the page.

Usage: uv run python scripts/fetch_novnc.py
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

NOVNC_VERSION = "1.7.0"
TARBALL_URL = f"https://github.com/novnc/noVNC/archive/refs/tags/v{NOVNC_VERSION}.tar.gz"
TARBALL_SHA256 = "b1003a11b6e6e8d8f7f5e5586daae7f8ca651d8aee0aa155ff9ac841c48f52c6"

DEST = Path(__file__).resolve().parent.parent / "src" / "services" / "desk_service" / "novnc"
# The whole upstream viewer ships: vnc.html + app/ (UI, styles, images,
# locale) + core/ + vendor/ (pako — required by the ES-module import chain).
# Not runtime: docs/, po/ (gettext sources), tests/, utils/, vnc_lite.html,
# packaging/CI files.
VENDORED_PREFIXES = ("core/", "vendor/", "app/")
# v1.7.0 has no root VERSION file (verified against the pinned tarball), so it
# is deliberately absent from this list.
KEEP = ("vnc.html", "defaults.json", "mandatory.json", "package.json", "LICENSE.txt")

# Our deployment defaults, written over upstream's empty `{}` — this file is
# upstream's own per-deployment override mechanism (vnc.html fetches it
# document-relative before UI.start). `resize=remote` = resizeSession
# (the framebuffer follows the viewport, as before); reconnect with a short
# delay so a dropped socket recovers without user action (upstream's
# reconnect screen + Cancel button come with it).
DEPLOYMENT_DEFAULTS = {"resize": "remote", "reconnect": True, "reconnect_delay": 3000}


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
    (dest / "defaults.json").write_text(
        json.dumps(DEPLOYMENT_DEFAULTS, indent=2) + "\n", encoding="utf-8"
    )
    (dest / "PROVENANCE").write_text(
        f"noVNC {NOVNC_VERSION} — vendored VERBATIM (vnc.html + app/ + core/ + vendor/) "
        f"from {TARBALL_URL}\n"
        f"tarball sha256 {TARBALL_SHA256}\n"
        f"defaults.json carries THIS app's deployment defaults: {DEPLOYMENT_DEFAULTS}\n"
        "License: MPL-2.0 (see LICENSE.txt). Refresh with scripts/fetch_novnc.py.\n",
        encoding="utf-8",
    )
    files = sorted(p.relative_to(dest) for p in dest.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    print(f"vendored noVNC {NOVNC_VERSION}: {len(files)} files, {total / 1024:.0f} KiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
