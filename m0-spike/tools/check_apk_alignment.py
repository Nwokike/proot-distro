#!/usr/bin/env python3
"""Report PT_LOAD alignment + presence of payloads inside built APK(s).

Usage: python tools/check_apk_alignment.py build/apk/*.apk

Prints, for every lib/<abi>/*.so in each APK, the minimum PT_LOAD p_align
(0x4000 = 16 KiB is the Play requirement for targetSdk 35+). Exits 0 unless
libproot.so is missing from an APK (alignment is reported, not enforced —
termux prebuilts may still be 4 KiB-aligned; M2 fixes that via NDK r28+).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_proot_wheel import elf_info


def check(apk: Path) -> bool:
    print(f"== {apk.name}")
    ok = True
    with zipfile.ZipFile(apk) as z:
        libs = sorted(n for n in z.namelist() if n.startswith("lib/") and n.endswith(".so"))
        if not libs:
            print("   no lib/*.so entries (unexpected — legacy_packaging extracts them, but they must exist in the APK)")
            ok = False
        for name in libs:
            blob = z.read(name)
            try:
                info = elf_info(blob, name)
            except SystemExit as e:
                print(f"   {name}: ELF parse failed: {e}")
                ok = False
                continue
            align = info["align"]
            flag = "16K-OK" if align and align >= 0x4000 else "!! 4K"
            align_s = f"{align:#x}" if align else "?"
            print(f"   {name:<48} align={align_s} ({flag}) soname={info['soname']}")
        if not any(n.endswith("libproot.so") for n in libs):
            print("   MISSING libproot.so — native payload did not reach jniLibs")
            ok = False
    return ok


def main() -> int:
    apks = [Path(p) for p in sys.argv[1:]]
    if not apks:
        print(__doc__)
        return 2
    ok = all(check(apk) for apk in apks if apk.exists())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
