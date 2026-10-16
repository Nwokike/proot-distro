#!/usr/bin/env python3
"""Verify the flet-proot payload inside built APK(s) — presence + 16 KiB alignment.

Usage: python tools/check_apk_alignment.py build/apk/*.apk

Enforcing rules (fail the build — exit 1):
  * flet-proot payload libs (libproot.so, libproot-loader.so, libtalloc.so,
    libandroid-shmem.so) must be present in every inspected APK, and each must
    have every PT_LOAD segment aligned to >= 0x4000 (16 KiB) — the Play
    requirement for targetSdk 35+ and the reason the production wheel builder
    asserts alignment before writing the wheel.
  * An APK with no lib/*.so at all is a failure (legacy_packaging extracts
    them at install, but they must exist in the APK).

Report-only: the CPython stdlib shared libs that serious_python bundles are
listed with their alignment but do not gate the build (they are not ours).

The 16 KiB guarantee chain: pinned deb (sha256-verified) -> builder asserts
PT_LOAD >= 0x4000 before writing the wheel -> this gate re-checks what actually
landed in the APK. NDK-rebuild workarounds stay unnecessary while Termux
prebuilts remain 16K-aligned; if an upstream deb ever regresses, the builder
fails first with a named offender.
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from elfinfo import ALIGN_16K, elf_info  # noqa: E402

PAYLOAD_LIBS = {
    "libproot.so",
    "libproot-loader.so",
    "libtalloc.so",
    "libandroid-shmem.so",
}


def check(apk: Path) -> bool:
    print(f"== {apk.name}")
    ok = True
    with zipfile.ZipFile(apk) as z:
        all_libs = sorted(
            n for n in z.namelist() if n.startswith("lib/") and n.endswith(".so")
        )
        if not all_libs:
            print("   FAIL: no lib/*.so entries in the APK")
            return False
        present = {n.rsplit("/", 1)[-1] for n in all_libs}
        for name in all_libs:
            blob = z.read(name)
            try:
                info = elf_info(blob, name)
            except SystemExit as e:
                print(f"   {name}: ELF parse failed: {e}")
                ok = False
                continue
            align = info["align"]
            align_s = f"{align:#x}" if align else "?"
            is_payload = name.rsplit("/", 1)[-1] in PAYLOAD_LIBS
            aligned = bool(align) and align >= ALIGN_16K
            if is_payload and not aligned:
                print(f"   FAIL {name:<44} align={align_s} (< 0x{ALIGN_16K:x})")
                ok = False
            else:
                flag = "16K-OK" if aligned else "4K (report-only)"
                marker = "payload" if is_payload else "stdlib"
                print(
                    f"   {name:<48} align={align_s} ({flag}) [{marker}] "
                    f"soname={info['soname']}"
                )
        missing = sorted(PAYLOAD_LIBS - present)
        if missing:
            print(f"   FAIL: flet-proot payload missing from APK: {missing}")
            ok = False
    return ok


def main() -> int:
    apks = [Path(p) for p in sys.argv[1:]]
    if not apks:
        print(__doc__)
        return 2
    existing = [a for a in apks if a.exists()]
    if not existing:
        print(f"FAIL: no such APK(s): {[str(a) for a in apks]}")
        return 1
    ok = all(check(apk) for apk in existing)
    print("OK: all payload libs present and 16K-aligned" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
