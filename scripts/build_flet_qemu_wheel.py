#!/usr/bin/env python3
"""Build the flet-qemu wheel: Termux's QEMU user-mode emulators repackaged.

Why: proot-distro runs foreign-architecture containers through `proot -q
qemu-<arch>`, locating the interpreter with `shutil.which("qemu-<arch>")`.
Bundling the emulators (all four non-host arches) lets an arm64 phone run
amd64/i386/armv7/riscv64 Linux images — and an x86_64 device run aarch64 etc.

The Termux binaries are dynamically linked (glib, libdw, libgnutls, libpixman,
libandroid-shmem), so this wheel also ships the closure NOT already provided by
flet-xvnc/flet-proot: glib(+pcre2), libdw(+libelf, liblzma), libjson-c.

AGP only packages files named lib*.so, so each emulator ships as
opt/lib/<jni>/libqemu-<arch>.so and every DT_NEEDED/SONAME that names a
versioned soname is rewritten IN PLACE to the bare shipped name (the same
trick the xvnc/proot builders use — replacements are length-checked).

Usage: uv run python scripts/build_flet_qemu_wheel.py --out wheels
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import re
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from elf_tools import ALIGN_16K, elf_info, unmet_needed

DIST_NAME = "flet_qemu"
QEMU_VERSION = "11.1.3"
BUILD_TAG = "1"
TIMEOUT = 120.0
UA = "kiri-flet-qemu-wheel-builder/1.0 (+https://github.com/Nwokike/proot-distro)"

POOL = "https://packages.termux.dev/apt/termux-main/pool/main"

# Emulator payload per Android ABI: every non-host Linux arch (owner decision:
# all four, ~2.3 MB compressed total).
_EMULATORS = {
    "aarch64": {
        "jni": "arm64-v8a",
        "platform": "arm64_v8a",
        "pkgs": ("qemu-user-x86-64", "qemu-user-i386", "qemu-user-arm", "qemu-user-riscv64"),
    },
    "x86_64": {
        "jni": "x86_64",
        "platform": "x86_64",
        "pkgs": ("qemu-user-aarch64", "qemu-user-i386", "qemu-user-arm", "qemu-user-riscv64"),
    },
}

# Versions + pins (read from the Termux Packages index, 2026-11-14).
_VERSIONS = {
    "qemu-user-x86-64": "1:11.1.3",
    "qemu-user-i386": "1:11.1.3",
    "qemu-user-arm": "1:11.1.3",
    "qemu-user-riscv64": "1:11.1.3",
    "qemu-user-aarch64": "1:11.1.3",
    "glib": "2.90.1",
    "pcre2": "10.49",
    "libdw": "0.197",
    "libelf": "0.197",
    "liblzma": "5.8.4",
    "argp": "1.5.0-1",
    "json-c": "0.19",
}
_POOL_DIRS = {
    "qemu-user-x86-64": "q/qemu-user-x86-64",
    "qemu-user-i386": "q/qemu-user-i386",
    "qemu-user-arm": "q/qemu-user-arm",
    "qemu-user-riscv64": "q/qemu-user-riscv64",
    "qemu-user-aarch64": "q/qemu-user-aarch64",
    "glib": "g/glib",
    "pcre2": "p/pcre2",
    "libdw": "libd/libdw",
    "libelf": "libe/libelf",
    "liblzma": "libl/liblzma",
    "argp": "a/argp",
    "json-c": "j/json-c",
}
_SHA = {
    "aarch64": {
        "qemu-user-x86-64": "0ab9a9b0b1587c344eea1873cb2dd8c0d63f227fc5e5c3d4271adf9cb43e913f",
        "qemu-user-i386": "09224ac69c2fc08a63594bc4b109361d2b1367a466af0b950dfe54caef0030a8",
        "qemu-user-arm": "f8f707de1c77cda50f29f95759319064af0f2b1339a27d4597b260a3f4b7384f",
        "qemu-user-riscv64": "a7c7efc9c0104dd46a48adeeaa42d55e8c4a183df45af47f6945b60eb971a7dd",
        "qemu-user-aarch64": "90808036f9a350a96e15e7af03d817a97be7ccc2df1070ff7b29171948da072d",
        "glib": "132d8ce961d96a7252fd4bc2228bddd385b1b17b706a46caae6d541ae0e4b2c0",
        "pcre2": "c27995e5f52b8ecc9b8b3e662eb08e49f82a18bfd3f34343936acc7b23964724",
        "libdw": "6c25c05cbba67671238434306ca5e55444d29c9b425600a710618a189d4f9ebb",
        "libelf": "c47ee2eee8450274f22218307b31471b76113b2825d3c69a5fdc47180cd68c13",
        "liblzma": "44e95e6e60dddb3705e60a344a4f009a1085a210797342b721eaff41b44033c0",
        "argp": "4096bfb8cba379efc3699e94e1cee400e72c274d734b5c1ed5f274ec42003405",
        "json-c": "894fef1e1001807e862f909cd5645dbb51bc77434779124f69178efe13690655",
    },
    "x86_64": {
        "qemu-user-x86-64": "7f72dcec852bb19fe273897127dfada565980f874119d5c53885396ee4c6c076",
        "qemu-user-i386": "c6ddb76135f0b4a48230bd92522c5c7ed89b068427f09e3e5cafcf0d7371fbf7",
        "qemu-user-arm": "fe95f7e519f2c26a7ce0b0e9bf589818814690d7a192142ff210fca918e6b5ee",
        "qemu-user-riscv64": "beadca9925f5e03df9a3a706fb308009191d01c1e4a2ee29c1d8b2682768d778",
        "qemu-user-aarch64": "eafda74ce364806b8946b071df8e1983173a0077e5956cb143914ab6de27f46b",
        "glib": "fb663e2222c3f7c7fb5c98b4694426665a719160adff0a6aec509b8285b63de4",
        "pcre2": "4a6f66ac12565342897ce9b5cd11ba8ce6fce1fd1a91ae679c3468d7fc2ee541",
        "libdw": "09b39adff368fe66353df537b993a66ac0384c6e4eafb03a7577545cac64723f",
        "libelf": "22446e45c0d033c3c020b02151bff4f72e21cfa49bf9b827b4242836ff0b25f1",
        "liblzma": "100ea7503a0b9ecffa45e1f168d035651f2eb7aedbebe71dd21fc0da4a84ef16",
        "argp": "7e6521f6bcb2bb76ab3db95c883fc70db536765a3f0d38fcbca3695a6d2ac60e",
        "json-c": "3817e1da4df01e43bf471ece32a8ae36327a3e56e293ec140a722de9aeb3d672",
    },
}

# Ship-name renames for the dependency closure: real soname -> bare lib*.so.
_BARE_LIBS = {
    "libglib-2.0.so": ("glib", "libglib-2.0.so.0"),
    "libgmodule-2.0.so": ("glib", "libgmodule-2.0.so.0"),
    "libgobject-2.0.so": ("glib", "libgobject-2.0.so.0"),
    "libgthread-2.0.so": ("glib", "libgthread-2.0.so.0"),
    "libpcre2-8.so": ("pcre2", "libpcre2-8.so.0"),
    "libdw.so": ("libdw", "libdw.so.1"),
    "libelf.so": ("libelf", "libelf.so.1"),
    "liblzma.so": ("liblzma", "liblzma.so.5"),
    "libjson-c.so": ("json-c", "libjson-c.so.5"),
    "libargp.so": ("argp", "libargp.so"),
}

# Sonames already provided in the APK native dir by flet-xvnc / flet-proot /
# the Flet runtime — DT_NEEDED entries naming these are rewritten to the bare
# shipped names; the libs themselves are not duplicated here.
_EXTERNAL_NEEDED = {
    "libgnutls.so.30": "libgnutls.so",
    "libnettle.so.8": "libnettle.so",
    "libhogweed.so.6": "libhogweed.so",
    "libgmp.so.10": "libgmp.so",
    "libpixman-1.so.0": "libpixman-1.so",
    "libz.so.1": "libz.so",
    "libzstd.so.1": "libzstd.so",
    "libbz2.so.1.0": "libbz2.so",
    "libffi.so.8": "libffi.so",
    "libiconv.so.2": "libiconv.so",
    "libandroid-support.so": "libandroid-support.so",
    "libandroid-shmem.so": "libandroid-shmem.so",
    "libc++_shared.so": "libc++_shared.so",
    "libcrypto.so.3": "libcrypto.so",
}

_NEEDED_REWRITES: tuple[tuple[bytes, bytes], ...] = tuple(
    (soname.encode() + b"\0", bare.encode() + b"\0" + b"\0" * (len(soname) - len(bare)))
    for soname, bare in {**_EXTERNAL_NEEDED, **{v[1]: k for k, v in _BARE_LIBS.items()}}.items()
    if len(bare) <= len(soname)
)


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _parse_ar(blob: bytes) -> dict[str, bytes]:
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


def _deb_payloads(deb_blob: bytes) -> dict[str, bytes]:
    data = next((v for k, v in _parse_ar(deb_blob).items() if k.startswith("data.tar")), None)
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


def _deb_url(arch: str, pkg: str) -> str:
    directory = _POOL_DIRS[pkg]
    filename = f"{pkg}_{_VERSIONS[pkg]}_{arch}.deb"
    encoded = filename.replace(":", "%3A")
    return f"{POOL}/{directory}/{encoded}", filename


def _rewrite(blob: bytes) -> bytes:
    for old, new in _NEEDED_REWRITES:
        blob = blob.replace(old, new)
    return blob


def _pick(files: dict[str, bytes], suffix: str) -> tuple[str, bytes]:
    hits = [(p, b) for p, b in files.items() if p.endswith(suffix)]
    if len(hits) != 1:
        raise SystemExit(f"expected exactly one {suffix!r}, found {[h[0] for h in hits]}")
    return hits[0]


def _pick_lib(files: dict[str, bytes], bare: str) -> tuple[str, bytes]:
    """The deb ships only the REAL versioned file (libglib-2.0.so.0.9000.1);
    the .so symlinks are stripped by Termux. Match on the bare stem."""
    stem = bare[: -len(".so")]
    # Termux sometimes embeds the version in the stem (libdw-0.197.so).
    pattern = rf"{re.escape(stem)}(-[0-9][0-9.]*)?\.so(\.[0-9]+)*"
    hits = [(p, b) for p, b in files.items() if re.fullmatch(pattern, p.rsplit("/", 1)[-1])]
    if not hits:
        raise SystemExit(f"library {stem}.so* not found")
    hits.sort(key=lambda h: len(h[0].rsplit("/", 1)[-1]))
    return hits[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="wheels")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for arch, spec in _EMULATORS.items():
        jni = spec["jni"]
        tag = f"py3-none-android_24_{spec['platform']}"
        print(f"── qemu {arch} ({jni}) " + "─" * 30)

        entries: dict[str, bytes] = {}
        pinned: dict[str, tuple[str, str]] = {}

        def fetch_pkg(pkg: str, _arch: str = arch, _pinned: dict = pinned) -> dict[str, bytes]:
            url, filename = _deb_url(_arch, pkg)
            print(f"  fetching {filename} …")
            blob = _fetch(url)
            sha = _SHA[_arch][pkg]
            if not sha:
                got = hashlib.sha256(blob).hexdigest()
                raise SystemExit(
                    f"{pkg} pin missing — verify and record this sha256: {got} ({url})"
                )
            got = hashlib.sha256(blob).hexdigest()
            if got != sha:
                raise SystemExit(f"{filename}: sha256 mismatch\n  expected {sha}\n  got {got}")
            _pinned[pkg] = (url, sha)
            return _deb_payloads(blob)

        # Emulators: usr/bin/qemu-<arch> -> libqemu-<arch>.so
        shipped: set[str] = set()
        for pkg in spec["pkgs"]:
            files = fetch_pkg(pkg)
            binary_arch = pkg.removeprefix("qemu-user-").replace("-", "_")
            _real, blob = _pick(files, f"files/usr/bin/qemu-{binary_arch}")
            name = f"libqemu-{binary_arch}.so"
            blob = _rewrite(blob)
            info = elf_info(blob, name)
            if not info["align"] or info["align"] < ALIGN_16K:
                raise SystemExit(f"{name}: PT_LOAD align {info['align']!r} < 16 KiB")
            entries[f"opt/lib/{jni}/{name}"] = blob
            shipped.add(name)

        # Dependency closure not already in the APK.
        for bare, (pkg, _soname) in _BARE_LIBS.items():
            files = fetch_pkg(pkg)
            _real, blob = _pick_lib(files, bare)
            blob = _rewrite(blob)
            entries[f"opt/lib/{jni}/{bare}"] = blob
            shipped.add(bare)

        # Closure gate: everything a payload needs is either shipped here or
        # provided by the other wheels / the Flet runtime (bare names above).
        external = set(_EXTERNAL_NEEDED.values()) | {
            "libc.so",
            "libm.so",
            "libdl.so",
            "liblog.so",
            "libandroid.so",
        }
        for path, blob in entries.items():
            name = path.rsplit("/", 1)[-1]
            info = elf_info(blob, name)
            missing = unmet_needed(info, shipped | external)
            if missing:
                raise SystemExit(f"{name} needs {missing} — extend _BARE_LIBS/_EXTERNAL_NEEDED")

        entries[f"{DIST_NAME}/__init__.py"] = (
            '"""QEMU user-mode payload for Flet Android apps (Termux repackage)."""\n'
            f"QEMU_VERSION = {QEMU_VERSION!r}\n"
            f"EMULATORS = {[p.removeprefix('qemu-user-').replace('-', '_') for p in spec['pkgs']]!r}\n"
        ).encode()

        dist_info = f"{DIST_NAME}-{QEMU_VERSION}.dist-info"
        entries[f"{dist_info}/METADATA"] = (
            "Metadata-Version: 2.1\n"
            "Name: flet-qemu\n"
            f"Version: {QEMU_VERSION}\n"
            "Summary: QEMU user-mode emulators (Termux repackage) for cross-arch containers\n"
            "Requires-Python: >=3.10\n"
            "License: GPL-2.0-or-later\n"
        ).encode()
        entries[f"{dist_info}/WHEEL"] = (
            "Wheel-Version: 1.0\n"
            "Generator: kiri-flet-qemu-wheel-builder\n"
            "Root-Is-Purelib: false\n"
            f"Tag: {tag}\n"
        ).encode()
        entries[f"{dist_info}/THIRD-PARTY.md"] = (
            "# flet-qemu — third-party components\n\n"
            "Repackages verbatim binaries from the Termux apt repository, pinned "
            "and sha256-verified at build time. QEMU is GPL-2.0-or-later; the "
            "source offer is in the companion app's THIRD-PARTY-SOURCES.md and at "
            "github.com/termux/termux-packages.\n"
        ).encode()

        lines = []
        for name, blob in entries.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).rstrip(b"=").decode()
            lines.append(f"{name},sha256={digest},{len(blob)}")
        lines.append(f"{dist_info}/RECORD,,")
        entries[f"{dist_info}/RECORD"] = ("\n".join(lines) + "\n").encode()

        wheel_name = f"{DIST_NAME}-{QEMU_VERSION}-{BUILD_TAG}-{tag}.whl"
        wheel_path = out_dir / wheel_name
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, blob in sorted(entries.items()):
                zf.writestr(name, blob)
        print(f"  wrote {wheel_name} ({wheel_path.stat().st_size / 1e6:.1f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
