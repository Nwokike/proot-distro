"""Minimal ELF64 reader shared by the flet-proot wheel builder and the APK gate.

Reads only what matters for Android native payloads:

* ``align``  — minimum PT_LOAD ``p_align`` (16 KiB = ``0x4000`` is the Play
  requirement for targetSdk 35+; a smaller value means the library would load
  unaligned on 16 KiB-page devices).
* ``needed`` — DT_NEEDED names (what the linker must find at load time).
* ``soname`` — DT_SONAME (the name the linker registers/should find on
  ``LD_LIBRARY_PATH``; jniLibs filenames must be ``lib*.so``, so SONAMEs are
  re-materialised at app runtime, not at packaging time).

Stdlib only; ELF64 little-endian (all Android ABIs we ship).
"""

from __future__ import annotations

import struct

DT_NEEDED, DT_STRTAB, DT_SONAME = 1, 5, 14
ALIGN_16K = 0x4000

# bionic/system libraries provided by the platform — never shipped by us.
SYSTEM_SONAMES = {
    "libc.so",
    "libdl.so",
    "libm.so",
    "liblog.so",
    "libandroid.so",
    "libz.so",
}


class ElfError(SystemExit):
    """Raised when a blob is not the expected ELF64 payload."""


def _cstr(blob: bytes, off: int) -> str:
    end = blob.find(b"\0", off)
    return blob[off : end if end != -1 else len(blob)].decode("utf-8", "replace")


def elf_info(blob: bytes, label: str) -> dict:
    """Return {needed: [str], soname: str|None, align: int|None} for an ELF64 blob."""
    if blob[:4] != b"\x7fELF":
        raise ElfError(f"{label}: not an ELF file")
    if blob[4] != 2:
        raise ElfError(f"{label}: only ELF64 supported (ei_class={blob[4]})")
    e_phoff = struct.unpack_from("<Q", blob, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", blob, 0x36)[0]
    e_phnum = struct.unpack_from("<H", blob, 0x38)[0]
    loads: list[tuple[int, int, int, int]] = []
    dyn_off = dyn_size = None
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", blob, o)[0]
        p_offset, p_vaddr = struct.unpack_from("<QQ", blob, o + 0x08)
        p_filesz = struct.unpack_from("<Q", blob, o + 0x20)[0]
        p_align = struct.unpack_from("<Q", blob, o + 0x30)[0]
        if p_type == 1:  # PT_LOAD
            loads.append((p_offset, p_vaddr, p_filesz, p_align))
        elif p_type == 2:  # PT_DYNAMIC
            dyn_off, dyn_size = p_offset, p_filesz
    align = min((seg[3] for seg in loads), default=None)
    if dyn_off is None:
        return {"needed": [], "soname": None, "align": align}

    def vaddr_to_off(v: int) -> int | None:
        for p_offset, p_vaddr, p_filesz, _ in loads:
            if p_vaddr <= v < p_vaddr + p_filesz:
                return p_offset + (v - p_vaddr)
        return None

    entries: list[tuple[int, int]] = []
    for i in range(dyn_size // 16):
        d_tag, d_val = struct.unpack_from("<QQ", blob, dyn_off + i * 16)
        if d_tag == 0:
            break
        entries.append((d_tag, d_val))
    strtab_v = next((v for t, v in entries if t == DT_STRTAB), None)
    strtab_off = vaddr_to_off(strtab_v) if strtab_v is not None else None
    needed = (
        [_cstr(blob, strtab_off + v) for t, v in entries if t == DT_NEEDED]
        if strtab_off is not None
        else []
    )
    soname = (
        next((_cstr(blob, strtab_off + v) for t, v in entries if t == DT_SONAME), None)
        if strtab_off is not None
        else None
    )
    return {"needed": needed, "soname": soname, "align": align}


def unmet_needed(info: dict, shipped_sonames: set[str]) -> list[str]:
    """DT_NEEDED entries not satisfied by the shipped payloads or the platform."""
    return [
        n
        for n in info["needed"]
        if n not in shipped_sonames
        and not n.startswith(("libc.", "libdl.", "libm."))
        and n not in SYSTEM_SONAMES
    ]
