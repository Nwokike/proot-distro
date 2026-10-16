#!/usr/bin/env python3
"""Set the house Android signing secrets on a GitHub repo from a keystore.

House convention (verified in Nwokike/Sherlock, DDGS, CollabShell, akili-v2…):
    secrets:  KEYSTORE_BASE64  KEY_ALIAS  KEYSTORE_PASSWORD  KEY_PASSWORD
    workflow: echo "$KEYSTORE_BASE64" | base64 --decode > kiri_keystore.jks
    pyproject: key_store = "../../../../kiri_keystore.jks", key_alias = "upload"

Usage (direct):
    python tools/setup_signing.py --repo Nwokike/proot-distro \\
        --keystore kiri_keystore.jks --alias upload \\
        --store-password '…' --key-password '…'

Usage (from an export produced by export_keystore_from_repo.py):
    python tools/setup_signing.py --repo Nwokike/proot-distro \\
        --from-json kiri-signing.json

Validates the keystore before uploading when `openssl` is available
(PKCS12) — values are only ever piped to `gh secret set`, never printed.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SECRET_NAMES = ("KEYSTORE_BASE64", "KEY_ALIAS", "KEYSTORE_PASSWORD", "KEY_PASSWORD")


def _gh(*args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], input=stdin, capture_output=True, check=False)


def _validate_pkcs12(keystore: Path, store_password: str) -> str:
    openssl = shutil.which("openssl")
    if not openssl:
        return "validation skipped (openssl not found)"
    head = keystore.read_bytes()[:2]
    if head != b"\x30\x82":  # not DER/PKCS12 — likely a JKS; keytool would be needed
        return "not PKCS12 (JKS?) — validation skipped"
    p = subprocess.run(
        [openssl, "pkcs12", "-in", str(keystore), "-passin", f"pass:{store_password}", "-nokeys", "-info"],
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise SystemExit(f"openssl could not open the keystore (wrong store password?):\n{p.stderr.decode(errors='replace')[-800:]}")
    names = [ln.split(":", 1)[1].strip() for ln in p.stdout.decode(errors="replace").splitlines() if "friendlyName" in ln]
    return f"openssl OK, aliases: {names}"


def _set_secret(repo: str, name: str, value: bytes) -> None:
    p = _gh("secret", "set", name, "-R", repo, stdin=value)
    if p.returncode != 0:
        raise SystemExit(f"gh secret set {name} failed:\n{p.stderr.decode(errors='replace')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="target repo, e.g. Nwokike/proot-distro")
    ap.add_argument("--keystore", help="path to the keystore file (.jks/.p12)")
    ap.add_argument("--alias", default="upload")
    ap.add_argument("--store-password", default=None)
    ap.add_argument("--key-password", default=None)
    ap.add_argument("--from-json", default=None, help="kiri-signing.json from export_keystore_from_repo.py")
    args = ap.parse_args()

    tmp: Path | None = None
    if args.from_json:
        doc = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        keystore_b64 = doc["keystore_b64"].strip()
        alias = doc["alias"]
        store_password = doc["store_password"]
        key_password = doc["key_password"]
        fd, name = tempfile.mkstemp(suffix=".jks")
        tmp = Path(name)
        with contextlib.suppress(OSError):
            os.close(fd)  # Windows: unlink fails while the mkstemp fd is open
        tmp.write_bytes(base64.b64decode(keystore_b64))
        keystore_path = tmp
    else:
        if not args.keystore or not args.store_password or not args.key_password:
            print("need --keystore, --store-password and --key-password (or --from-json)", file=sys.stderr)
            return 2
        keystore_path = Path(args.keystore)
        if not keystore_path.exists():
            print(f"keystore not found: {keystore_path}", file=sys.stderr)
            return 2
        keystore_b64 = base64.b64encode(keystore_path.read_bytes()).decode()
        alias = args.alias
        store_password = args.store_password
        key_password = args.key_password

    try:
        verdict = _validate_pkcs12(keystore_path, store_password)
        print(f"keystore: {keystore_path.stat().st_size} bytes — {verdict}")
        print(f"target repo: {args.repo}  alias: {alias!r}")

        _set_secret(args.repo, "KEYSTORE_BASE64", keystore_b64.encode())
        _set_secret(args.repo, "KEY_ALIAS", alias.encode())
        _set_secret(args.repo, "KEYSTORE_PASSWORD", store_password.encode())
        _set_secret(args.repo, "KEY_PASSWORD", key_password.encode())

        p = _gh("secret", "list", "-R", args.repo)
        print(p.stdout.decode(errors="replace").strip())
        print("\nOK — 4 signing secrets set (values never printed).")
        return 0
    finally:
        if tmp is not None:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
