#!/usr/bin/env python3
"""Build the flet-proot payload wheels from pinned Termux debs.

One self-contained file: the sha256 pins and the ELF/alignment checks live below.
Bumping a source = editing _PINNED_SOURCES (one commit). Stdlib only.
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

REPO_ROOT = Path(__file__).resolve().parent
LICENSE_DIR = REPO_ROOT / "LICENSES"

DIST_NAME = "flet_proot"
TIMEOUT = 120.0
UA = "kiri-flet-proot-wheel-builder/1.0 (+https://github.com/Nwokike/proot-distro)"

# ── the pin set (the "bump a version" path: one edit here) ──────────────────
# proot 5.1.107.98 replaced 5.1.107.96 when Termux dropped the old debs from
# the pool (CI 404). talloc/shmem unchanged.

_PINNED_SOURCES = {
    "pool_root": "https://packages.termux.dev/apt/termux-main/pool/main",
    "wheel_build_tag": "1",
    "packages": {
        "proot": {
            "pool_dir": "p/proot",
            "version": "5.1.107.98",
            "debs": {
                "aarch64": {
                    "file": "proot_5.1.107.98_aarch64.deb",
                    "sha256": "29de40efea4daa2a6168b617915206511c63e8d46bf5f4b07d48723441ef7f3b",
                },
                "x86_64": {
                    "file": "proot_5.1.107.98_x86_64.deb",
                    "sha256": "1c31ad7e1046f4d418fef19b6dfaa9a14801d2047ade6ad0375b3f5501e3e227",
                },
            },
        },
        "libtalloc": {
            "pool_dir": "libt/libtalloc",
            "version": "2.5.0",
            "debs": {
                "aarch64": {
                    "file": "libtalloc_2.5.0_aarch64.deb",
                    "sha256": "556591f43bb773ad8777e1a29522640866a55f95dab71914418b94a8c58ad5a7",
                },
                "x86_64": {
                    "file": "libtalloc_2.5.0_x86_64.deb",
                    "sha256": "b8c6d95f20075dc1f9ec6573575b2444e8d526e48e0d8d6d5cf4e071e6e06530",
                },
            },
        },
        "libandroid-shmem": {
            "pool_dir": "liba/libandroid-shmem",
            "version": "0.7",
            "debs": {
                "aarch64": {
                    "file": "libandroid-shmem_0.7_aarch64.deb",
                    "sha256": "0da3a24d558b93c92bcf8d611e0826a99ff96e396b148e6cdf33b47c47c57ff6",
                },
                "x86_64": {
                    "file": "libandroid-shmem_0.7_x86_64.deb",
                    "sha256": "ffa9e4c87467b158b148d0ff92dda796aa038276c2075af3269cdcdb06f25797",
                },
            },
        },
    },
}

# ── minimal ELF64 reader (what Android native payloads must satisfy) ─────────
# align  — minimum PT_LOAD p_align (16 KiB = 0x4000 is the Play requirement
#          for targetSdk 35+; smaller means unaligned loads on 16 KiB pages).
# needed — DT_NEEDED names the linker must find at load time.
# soname — DT_SONAME (jniLibs names must be lib*.so, so SONAMEs are
#          re-materialised at app runtime, not at packaging time).

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


# architecture -> Android wheel platform tag (mirrors flet-libffmpeg)
ARCH_TAGS = {
    "aarch64": "py3-none-android_24_arm64_v8a",
    "x86_64": "py3-none-android_24_x86_64",
}

# Payload piece -> (deb package, license file, license label)
PAYLOAD_LICENSES = {
    "libproot.so": ("proot", "GPL-2.0.txt"),
    "libproot-loader.so": ("proot", "GPL-2.0.txt"),
    "libtalloc.so": ("libtalloc", "GPL-3.0.txt"),
    "libandroid-shmem.so": ("libandroid-shmem", "BSD-3-Clause.txt"),
}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _fetch_verified(url: str, expected_sha256: str, what: str) -> bytes:
    blob = _fetch(url)
    actual = hashlib.sha256(blob).hexdigest()
    if actual != expected_sha256:
        raise SystemExit(
            f"{what}: sha256 mismatch\n  url:      {url}\n  expected: {expected_sha256}\n  actual:   {actual}\n"
            "The pinned .deb changed upstream — verify and bump _PINNED_SOURCES in this file."
        )
    return blob


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


# ── wheel assembly ───────────────────────────────────────────────────────────


def collect_payloads(lock: dict, arch: str, downloaded: dict[str, bytes]) -> list[dict]:
    payloads: list[dict] = []

    def add(jni_name: str, blob: bytes, source: str, pkg: str):
        try:
            info = elf_info(blob, jni_name)
        except ElfError as e:
            raise SystemExit(str(e)) from e
        if not info["align"] or info["align"] < ALIGN_16K:
            raise SystemExit(
                f"{jni_name}: PT_LOAD align {info['align']!r} < 0x{ALIGN_16K:x} (16 KiB) — "
                f"refusing to ship a non-16K-aligned payload (source: {source})"
            )
        payloads.append(
            {
                "jni": jni_name,
                "package": pkg,
                "source": source,
                "soname": info["soname"],
                "needed": info["needed"],
                "align": info["align"],
                "sha256": hashlib.sha256(blob).hexdigest(),
                "size": len(blob),
                "data": blob,
            }
        )

    for pkg in ("proot", "libtalloc", "libandroid-shmem"):
        url = downloaded[pkg]["url"]
        files = deb_payloads(downloaded[pkg]["blob"])
        if pkg == "proot":
            # Termux layout: usr/bin/proot (main binary) and
            # usr/libexec/proot/loader (PROOT_UNBUNDLE_LOADER).
            path, blob = pick_suffix(files, "files/usr/bin/proot")
            add("libproot.so", blob, f"{url} :: {path}", pkg)
            lpath, lblob = pick_suffix(files, "files/usr/libexec/proot/loader")
            add("libproot-loader.so", lblob, f"{url} :: {lpath}", pkg)
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
            add(f"{stem}.so", blob, f"{url} :: {path}", pkg)

    shipped = {p["jni"] for p in payloads} | {p["soname"] for p in payloads if p["soname"]}
    for p in payloads:
        missing = unmet_needed(p, shipped)
        if missing:
            raise SystemExit(
                f"{p['jni']} needs {missing} but they are not shipped — extend the lock/payload set"
            )
    return payloads


def _license_text(name: str) -> bytes:
    path = LICENSE_DIR / name
    if not path.is_file():
        raise SystemExit(f"missing vendored license text: {path}")
    return path.read_bytes()


def _third_party_md(lock: dict, arch: str, payloads: list[dict]) -> bytes:
    lines = [
        "# flet-proot — third-party components",
        "",
        "This wheel repackages verbatim binaries from the Termux apt repository",
        f"(architecture `{arch}`), pinned and sha256-verified at build time.",
        "",
        "| Component | Version | Upstream | License |",
        "|---|---|---|---|",
        "| PRoot (incl. unbundled loader) | "
        f"{lock['packages']['proot']['version']} | github.com/termux/proot | GPL-2.0-or-later |",
        "| Samba talloc | "
        f"{lock['packages']['libtalloc']['version']} | talloc.samba.org | GPL-3.0 |",
        "| libandroid-shmem | "
        f"{lock['packages']['libandroid-shmem']['version']} | github.com/termux/libandroid-shmem | BSD-3-Clause |",
        "",
        "Source offer: see the companion app's LICENSES/ + THIRD-PARTY-SOURCES.md",
        "(github.com/Nwokike/proot-distro) and the upstream projects above.",
        "",
    ]
    return "\n".join(lines).encode()


def build_wheel(
    out_dir: Path, lock: dict, arch: str, tag: str, downloaded: dict[str, bytes]
) -> Path:
    proot_version = lock["packages"]["proot"]["version"]
    build_tag = str(lock["wheel_build_tag"])
    payloads = collect_payloads(lock, arch, downloaded)

    sources = [
        {
            "package": pkg,
            "version": lock["packages"][pkg]["version"],
            "file": downloaded[pkg]["file"],
            "url": downloaded[pkg]["url"],
            "sha256": downloaded[pkg]["sha256"],
        }
        for pkg in ("proot", "libtalloc", "libandroid-shmem")
    ]

    manifest = (
        "# Generated by tools/build_flet_proot_wheel.py — do not edit.\n"
        f"VERSION = {proot_version!r}\n"
        f"WHEEL_BUILD_TAG = {build_tag!r}\n"
        f"ARCH = {arch!r}\n"
        f"SOURCES = {sources!r}\n"
        f"LIBS = {[{k: p[k] for k in ('jni', 'soname', 'needed', 'align', 'size', 'sha256')} for p in payloads]!r}\n"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{DIST_NAME}-{proot_version}-{build_tag}-{tag}.whl"
    wheel_path = out_dir / fname

    entries: dict[str, bytes] = {"flet_proot/__init__.py": manifest.encode()}
    for p in payloads:
        entries[f"opt/lib/{p['jni']}"] = p["data"]

    dist_info = f"{DIST_NAME}-{proot_version}.dist-info"
    lic_proot = _license_text("GPL-2.0.txt")
    lic_talloc = _license_text("GPL-3.0.txt")
    lic_shmem = _license_text("BSD-3-Clause.txt")
    entries[f"{dist_info}/METADATA"] = (
        "Metadata-Version: 2.1\n"
        "Name: flet-proot\n"
        f"Version: {proot_version}\n"
        "Summary: PRoot native payload for Flet Android apps (libproot.so + loader + deps -> jniLibs)\n"
        f"Description-Content-Type: text/markdown\n"
        f"Requires-Python: >=3.10\n"
        f"Architecture tag: {tag}\n"
        "License: GPL-2.0-or-later\n"
        "License-File: LICENSE.proot\n"
        "License-File: LICENSE.libtalloc\n"
        "License-File: LICENSE.libandroid-shmem\n"
        "License-File: THIRD-PARTY.md\n"
    ).encode()
    entries[f"{dist_info}/WHEEL"] = (
        "Wheel-Version: 1.0\n"
        "Generator: tools/build_flet_proot_wheel.py\n"
        "Root-Is-Purelib: true\n"
        f"Tag: {tag}\n"
    ).encode()
    entries[f"{dist_info}/LICENSE.proot"] = lic_proot
    entries[f"{dist_info}/LICENSE.libtalloc"] = lic_talloc
    entries[f"{dist_info}/LICENSE.libandroid-shmem"] = lic_shmem
    entries[f"{dist_info}/THIRD-PARTY.md"] = _third_party_md(lock, arch, payloads)

    lines = []
    for name, blob in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).rstrip(b"=").decode()
        lines.append(f"{name},sha256={digest},{len(blob)}")
    lines.append(f"{dist_info}/RECORD,,")
    entries[f"{dist_info}/RECORD"] = ("\n".join(lines) + "\n").encode()

    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, blob in entries.items():
            z.writestr(name, blob)

    print(f"\nwheel: {wheel_path.name} ({wheel_path.stat().st_size / 1024:.0f} KiB)")
    print("payloads:")
    for p in payloads:
        print(
            f"  opt/lib/{p['jni']:<24} soname={p['soname']!r:<24} "
            f"align={p['align']:#x} size={p['size']}"
        )
        if p["needed"]:
            print(f"      needs: {p['needed']}")
    return wheel_path


def download_sources(lock: dict, arch: str) -> dict[str, bytes]:
    downloaded: dict[str, bytes] = {}
    for pkg, spec in lock["packages"].items():
        deb = spec["debs"].get(arch)
        if deb is None:
            raise SystemExit(f"{pkg}: no {arch} deb pinned in the lock")
        url = f"{lock['pool_root']}/{spec['pool_dir']}/{deb['file']}"
        print(f"[{pkg}] {deb['file']} ...", end=" ", flush=True)
        blob = _fetch_verified(url, deb["sha256"], f"[{pkg}] {deb['file']}")
        downloaded[pkg] = {
            "blob": blob,
            "file": deb["file"],
            "url": url,
            "sha256": deb["sha256"],
        }
        print(f"sha256 OK ({len(blob)} bytes)")
    return downloaded


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", default="dist", help="output directory (default: dist)")
    ap.add_argument(
        "--arch",
        action="append",
        choices=sorted(ARCH_TAGS),
        help="architecture to build (repeatable; default: all)",
    )
    ap.add_argument(
        "--tag",
        default=None,
        help="override the platform tag (requires exactly one --arch; e.g. py3-none-any)",
    )
    args = ap.parse_args()

    lock = _PINNED_SOURCES
    arches = args.arch or sorted(ARCH_TAGS)
    if args.tag and len(arches) != 1:
        raise SystemExit("--tag requires exactly one --arch")

    out_dir = Path(args.out)
    wheels = []
    for arch in arches:
        tag = args.tag or ARCH_TAGS[arch]
        print(f"\n=== flet-proot :: {arch} :: {tag} ===")
        downloaded = download_sources(lock, arch)
        wheels.append(build_wheel(out_dir, lock, arch, tag, downloaded))

    print(f"\n{len(wheels)} wheel(s) written to {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
