#!/usr/bin/env python3
"""Assemble the `flet-proot` payload wheel from Termux .debs (M0 spike).

Downloads the aarch64 Termux packages for proot (+ its runtime deps) from
packages.termux.dev, extracts the ELF payloads, reads their dynamic
dependencies (DT_NEEDED / DT_SONAME) and PT_LOAD alignment, and writes a
wheel whose `opt/lib/lib*.so` files are picked up by serious_python's
`copyOpt` step (site-packages/<abi>/opt/**/*.so -> APK jniLibs).

Layout of the produced wheel:

    flet_proot/__init__.py         -> LIBS manifest (importable in-app)
    flet_proot-0.1.0.dist-info/…
    opt/lib/libproot.so            (proot ELF, exec'd from nativeLibraryDir)
    opt/lib/libproot-loader.so     (proot's unbundled loader, PROOT_LOADER)
    opt/lib/libtalloc.so           (real file; SONAME recorded in manifest)
    opt/lib/libandroid-shmem.so    (same, when present)

Rationale for the rename dance: jniLibs/`copyOpt` only accepts `*.so`-suffixed
names, while a DT_NEEDED like `libtalloc.so.2` must satisfy the linker by that
exact name. The app side (m0-spike/src/main.py) copies the payloads into its
data dir under their SONAME and points LD_LIBRARY_PATH at it (mmap-exec of
app-data files stays allowed under Android W^X; only execve is restricted).

Only the Python standard library is used. Usage:

    python tools/build_proot_wheel.py --out dist [--arch aarch64]
                                      [--tag py3-none-any | --android-tag]
                                      [--proot-version 5.1.107.96]

Exit code 0 = wheel written; non-zero = actionable error on stderr.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import re
import struct
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

POOL_ROOT = "https://packages.termux.dev/apt/termux-main/pool/main"
WHEEL_VERSION = "0.1.0"
WHEEL_BUILD_TAG = "1"
DIST_NAME = "flet_proot"

# deb pool directory -> member regex (per-arch). Group ids used by the Termux
# repo for these packages; the lib* directories have two-letter prefixes.
DEB_SOURCES = [
    ("proot", "p/proot", r'proot_([0-9][^"<]*?)_{arch}\.deb'),
    ("libtalloc", "libt/libtalloc", r'libtalloc_([0-9][^"<]*?)_{arch}\.deb'),
    ("libandroid-shmem", "liba/libandroid-shmem", r'libandroid-shmem_([0-9][^"<]*?)_{arch}\.deb'),
]

TIMEOUT = 120.0
UA = "kiri-m0-spike-wheel-builder/0.1 (+https://github.com/Nwokike/proot-distro)"


# ── network ──────────────────────────────────────────────────────────────────


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _version_key(v: str):
    return [int(p) if p.isdigit() else p for p in re.split(r"[._~+-]", v)]


def pick_deb_url(pkg: str, pool_dir: str, pattern: str, arch: str, pin: str | None) -> str:
    dir_url = f"{POOL_ROOT}/{pool_dir}/"
    try:
        html = _fetch(dir_url).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[{pkg}] directory listing failed: {dir_url} -> HTTP {e.code}") from e
    rx = re.compile(pattern.format(arch=re.escape(arch)))
    versions = sorted({m.group(1) for m in rx.finditer(html)}, key=_version_key)
    if not versions:
        raise SystemExit(f"[{pkg}] no {arch} .deb found in {dir_url}")
    version = pin if pin else versions[-1]
    if pin and pin not in versions:
        raise SystemExit(f"[{pkg}] requested version {pin} not in index ({versions[-5:]})")
    fname = f"{pkg}_{version}_{arch}.deb"
    print(f"[{pkg}] using {fname}")
    return f"{dir_url}{fname}"


# ── ar / deb extraction ──────────────────────────────────────────────────────


def parse_ar(blob: bytes) -> dict[str, bytes]:
    if not blob.startswith(b"!<arch>\n"):
        raise SystemExit("not an ar archive (bad magic)")
    members: dict[str, bytes] = {}
    off = 8
    while off + 60 <= len(blob):
        header = blob[off : off + 60]
        name = header[0:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip() or "0")
        data = blob[off + 60 : off + 60 + size]
        if len(data) != size:
            raise SystemExit(f"truncated ar member {name!r}")
        members[name] = data
        off += 60 + size + (size % 2)
    return members


def deb_payloads(deb_blob: bytes) -> dict[str, bytes]:
    """Return {path -> bytes} for regular files + symlink targets of data.tar.*."""
    members = parse_ar(deb_blob)
    data = next((v for k, v in members.items() if k.startswith("data.tar")), None)
    if data is None:
        raise SystemExit("no data.tar.* member in .deb")
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        for m in tar:
            if m.isfile():
                f = tar.extractfile(m)
                if f is not None:
                    out[m.name.lstrip("./")] = f.read()
    return out


def pick_suffix(files: dict[str, bytes], suffix: str) -> tuple[str, bytes]:
    """Strictly pick the single file whose path ends with `suffix` (no fallback)."""
    hits = [(p, b) for p, b in files.items() if p.endswith(suffix)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one {suffix!r} in deb, found {[h[0] for h in hits]}")
    return hits[0]


def pick_lib(files: dict[str, bytes], stem: str) -> tuple[str, bytes]:
    hits = [
        (p, b)
        for p, b in files.items()
        if re.fullmatch(rf"{re.escape(stem)}(\.so(\.[0-9]+)*)?", p.rsplit("/", 1)[-1])
    ]
    if not hits:
        raise SystemExit(f"shared lib {stem}.so* not found in deb")
    hits.sort(key=lambda h: len(h[0]))
    return hits[-1]


# ── minimal ELF64 reader (dynamic deps + load alignment) ────────────────────

DT_NEEDED, DT_STRTAB, DT_SONAME = 1, 5, 14


def _cstr(blob: bytes, off: int) -> str:
    end = blob.find(b"\0", off)
    return blob[off : end if end != -1 else len(blob)].decode("utf-8", "replace")


def elf_info(blob: bytes, label: str) -> dict:
    if blob[:4] != b"\x7fELF":
        raise SystemExit(f"{label}: not an ELF file")
    if blob[4] != 2:
        raise SystemExit(f"{label}: only ELF64 supported (ei_class={blob[4]})")
    e_phoff = struct.unpack_from("<Q", blob, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", blob, 0x36)[0]
    e_phnum = struct.unpack_from("<H", blob, 0x38)[0]
    loads, dyn_off = [], None
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
    if dyn_off is None:
        return {"needed": [], "soname": None, "align": min((seg[3] for seg in loads), default=None)}

    def vaddr_to_off(v: int, size: int = 1) -> int | None:
        for p_offset, p_vaddr, p_filesz, _ in loads:
            if p_vaddr <= v < p_vaddr + p_filesz:
                return p_offset + (v - p_vaddr)
        return None

    entries = []
    n = dyn_size // 16
    for i in range(n):
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
    soname = next((_cstr(blob, strtab_off + v) for t, v in entries if t == DT_SONAME), None) if strtab_off is not None else None
    align = min((seg[3] for seg in loads), default=None)
    return {"needed": needed, "soname": soname, "align": align}


# ── wheel assembly ───────────────────────────────────────────────────────────


def build_wheel(out_dir: Path, tag: str, arch: str, proot_pin: str | None) -> Path:
    payloads: list[dict] = []

    def add_payload(jni_name: str, blob: bytes, source: str):
        info = elf_info(blob, jni_name)
        payloads.append(
            {
                "jni": jni_name,
                "source": source,
                "soname": info["soname"],
                "needed": info["needed"],
                "align": info["align"],
                "sha256": hashlib.sha256(blob).hexdigest(),
                "size": len(blob),
                "data": blob,
            }
        )

    proot_files = None
    for pkg, pool_dir, pattern in DEB_SOURCES:
        url = pick_deb_url(pkg, pool_dir, pattern, arch, proot_pin if pkg == "proot" else None)
        files = deb_payloads(_fetch(url))
        if pkg == "proot":
            proot_files = files
            # Termux layout: usr/bin/proot (main binary) and
            # usr/libexec/proot/loader (the unbundled loader, see
            # PROOT_UNBUNDLE_LOADER in termux-packages/packages/proot/build.sh).
            path, blob = pick_suffix(files, "files/usr/bin/proot")
            add_payload("libproot.so", blob, f"{url} :: {path}")
            lpath, lblob = pick_suffix(files, "files/usr/libexec/proot/loader")
            add_payload("libproot-loader.so", lblob, f"{url} :: {lpath}")
            if hashlib.sha256(blob).digest() == hashlib.sha256(lblob).digest():
                raise SystemExit("loader and main binary are identical — layout assumption broken")
        else:
            stem = "libtalloc" if pkg == "libtalloc" else "libandroid-shmem"
            try:
                path, blob = pick_lib(files, stem)
            except SystemExit as e:
                if pkg == "libandroid-shmem":
                    print(f"WARNING: optional dep skipped: {e}", file=sys.stderr)
                    continue
                raise
            add_payload(f"{stem}.so", blob, f"{url} :: {path}")

    assert proot_files is not None

    # Compatibility check: every DT_NEEDED of libproot.so must be satisfied by
    # a shipped payload (bionic/system names excepted).
    shipped_sonames = {p["jni"] for p in payloads} | {p["soname"] for p in payloads if p["soname"]}
    missing = [n for n in payloads[0]["needed"] if n not in shipped_sonames and not n.startswith("libc.") and n not in ("libdl.so", "libm.so", "liblog.so", "libandroid.so")]
    if missing:
        raise SystemExit(f"libproot.so needs {missing} but they are not shipped — extend DEB_SOURCES")

    manifest = (
        "# Generated by m0-spike/tools/build_proot_wheel.py — do not edit.\n"
        f"VERSION = {WHEEL_VERSION!r}\n"
        f"LIBS = {[{k: p[k] for k in ('jni', 'soname', 'needed', 'align', 'size', 'sha256')} for p in payloads]!r}\n"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{DIST_NAME}-{WHEEL_VERSION}-{WHEEL_BUILD_TAG}-{tag}.whl"
    wheel_path = out_dir / fname

    entries: dict[str, bytes] = {
        "flet_proot/__init__.py": manifest.encode(),
    }
    for p in payloads:
        entries[f"opt/lib/{p['jni']}"] = p["data"]

    dist_info = f"{DIST_NAME}-{WHEEL_VERSION}.dist-info"
    entries[f"{dist_info}/METADATA"] = (
        "Metadata-Version: 2.1\n"
        "Name: flet-proot\n"
        f"Version: {WHEEL_VERSION}\n"
        "Summary: PRoot native payload for Flet Android apps (m0-spike build)\n"
        "License: GPL-2.0-or-later\n"  # proot is GPL-2.0; libtalloc GPL-3.0
        "License-File: LICENSE.proot\n"
        "License-File: LICENSE.libtalloc\n"
    ).encode()
    entries[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: m0-spike/tools/build_proot_wheel.py\n"
        "Root-Is-Purelib: true\n"
        f"Tag: {tag}\n"
    ).encode()
    # License stubs pointing at upstream sources (GPL compliance notice).
    entries[f"{dist_info}/LICENSE.proot"] = (
        b"proot is GPL-2.0. Source: https://github.com/termux/proot\n"
        b"Packaged verbatim from the Termux apt repository (aarch64 debs).\n"
    )
    entries[f"{dist_info}/LICENSE.libtalloc"] = (
        b"libtalloc is GPL-3.0. Source: https://talloc.samba.org/\n"
        b"Packaged verbatim from the Termux apt repository (aarch64 debs).\n"
    )

    # RECORD (PEP 427): sha256=urlsafe-b64, no padding.
    lines = []
    for name, blob in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).rstrip(b"=").decode()
        lines.append(f"{name},sha256={digest},{len(blob)}")
    lines.append(f"{dist_info}/RECORD,,")
    entries[f"{dist_info}/RECORD"] = ("\n".join(lines) + "\n").encode()

    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in entries.items():
            z.writestr(name, blob)

    print(f"\nwheel: {wheel_path} ({wheel_path.stat().st_size / 1024:.0f} KiB)")
    print("payloads:")
    for p in payloads:
        align_s = f"{p['align']:#x}" if p["align"] else "?"
        print(
            f"  opt/lib/{p['jni']:<24} soname={p['soname']!r:<24} "
            f"align={align_s} size={p['size']}"
        )
        if p["needed"]:
            print(f"      needs: {p['needed']}")
    return wheel_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="dist", help="output directory (default: dist)")
    ap.add_argument("--arch", default="aarch64", choices=["aarch64"])
    ap.add_argument("--tag", default="py3-none-any", help="wheel tag (e.g. py3-none-any)")
    ap.add_argument("--android-tag", action="store_true", help="use py3-none-android_24_arm64_v8a instead")
    ap.add_argument("--proot-version", default=None, help="pin the proot deb version (default: newest)")
    args = ap.parse_args()
    tag = "py3-none-android_24_arm64_v8a" if args.android_tag else args.tag
    build_wheel(Path(args.out), tag, args.arch, args.proot_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
