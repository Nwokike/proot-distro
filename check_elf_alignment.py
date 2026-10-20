#!/usr/bin/env python3
"""Verify Play's 16 KB page-size requirement on a built artifact.

Usage: python check_elf_alignment.py <path.apk | path.aab> [...]

APK and AAB are zip containers: every ``*.so`` inside is checked for the
``p_align`` of its ``PT_LOAD`` headers. Google Play rejects uploads where a
64-bit library is aligned below 16384 (16 KB). 32-bit ABIs are reported as
warnings only (they are exempt).

Exits non-zero when a 64-bit library is misaligned, so it can gate CI.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

from build_flet_proot_wheel import ALIGN_16K, elf_info

ABI_64_BIT = ("arm64-v8a", "x86_64")


def check_artifact(artifact: Path) -> bool:
    """Check one APK/AAB; return True when it passes."""
    ok = True
    with zipfile.ZipFile(artifact) as archive:
        names = [n for n in archive.namelist() if n.endswith(".so")]
        if not names:
            print(f"FAIL {artifact.name}: no lib/*.so entries")
            return False
        for name in sorted(names):
            blob = archive.read(name)
            try:
                info = elf_info(blob, name)
            except SystemExit as exc:
                print(f"FAIL {artifact.name}: {name}: {exc}")
                ok = False
                continue
            align = info.get("align") or 0
            abi = next((a for a in ABI_64_BIT if f"/{a}/" in name), None)
            if abi and align < ALIGN_16K:
                print(f"FAIL {artifact.name}: {name} p_align={align:#x} (< 16 KB)")
                ok = False
            elif not abi and align < ALIGN_16K:
                print(f"warn {artifact.name}: {name} p_align={align:#x} (32-bit ABI, exempt)")
            else:
                print(f"ok   {artifact.name}: {name} p_align={align:#x}")
    return ok


def main() -> int:
    artifacts = [Path(arg) for arg in sys.argv[1:]]
    if not artifacts:
        print(__doc__)
        return 2
    missing = [str(a) for a in artifacts if not a.exists()]
    if missing:
        print(f"FAIL: no such artifact(s): {missing}")
        return 1
    ok = all(check_artifact(artifact) for artifact in artifacts)
    print("OK: all 64-bit libs are 16 KB aligned" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
