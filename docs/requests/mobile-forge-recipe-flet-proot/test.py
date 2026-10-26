"""Recipe test — runs on a target installation (mobile-forge convention).

Validates the flet-proot manifest that ships inside the wheel and the invariants
the consuming app depends on: the core payload set is present and every payload
ELF is 16 KiB PT_LOAD aligned (Play requirement for targetSdk 35+).

Field values (VERSION/LIBS) are written by the recipe's build step; when the
test runs in an environment that has only the manifest installed, the ELF
parses happened at build time and are recorded here.
"""

import sys


def main() -> int:
    import flet_proot

    version = getattr(flet_proot, "VERSION", None)
    assert version, "flet_proot.VERSION missing from the wheel manifest"

    libs = getattr(flet_proot, "LIBS", [])
    names = {lib["jni"] for lib in libs}
    required = {"libproot.so", "libproot-loader.so", "libtalloc.so"}
    missing = required - names
    assert not missing, f"payload missing from manifest: {sorted(missing)}"

    for lib in libs:
        align = lib.get("align")
        assert align and align >= 0x4000, f"{lib['jni']}: PT_LOAD align {align!r} < 0x4000 (16 KiB)"

    print(f"flet-proot {version} OK — payloads: {sorted(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
