#!/usr/bin/env bash
# flet-proot recipe build.sh — repack the pinned Termux debs into opt/lib payloads.
#
# Status: prepared, NOT submitted. See README.md — the mobile-forge build
# environment conventions (build prefix, network access, per-arch packaging
# hook) are UNVERIFIED; this script encodes our best understanding and stages
# the payload as  <prefix>/opt/<arch>/lib/*.so  (one dir per ABI, ready for a
# per-arch wheel step), mirroring flet-libffmpeg's per-ABI wheel output.
#
# Reference implementation (sha256 pins, ELF checks):
#   github.com/Nwokike/proot-distro/blob/main/tools/build_flet_proot_wheel.py
set -euo pipefail

PREFIX="${PREFIX:-$PWD/build}"
mkdir -p "$PREFIX"

python3 - "$PREFIX" << 'PYEOF'
import hashlib
import io
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

PREFIX = Path(sys.argv[1])
POOL = "https://packages.termux.dev/apt/termux-main/pool/main"
UA = {"User-Agent": "mobile-forge-flet-proot-recipe/1.0"}

ARCHS = ["aarch64", "x86_64"]
# Mirror of tools/flet_proot_sources.json (package -> pool dir, version, sha256/arch).
SOURCES = {
    "proot": {
        "dir": "p/proot",
        "ver": "5.1.107.101",
        "sha": {
            "aarch64": "a28355e9be257e1f87f4e9294b3118470d4fd7a5442fed8b278f4443c83407d7",
            "x86_64": "85adb8d0d2e1edc6c56e60c17136adf05e54ce75f69407ec7116a4c5997eaed5",
        },
    },
    "libtalloc": {
        "dir": "libt/libtalloc",
        "ver": "2.5.0",
        "sha": {
            "aarch64": "556591f43bb773ad8777e1a29522640866a55f95dab71914418b94a8c58ad5a7",
            "x86_64": "b8c6d95f20075dc1f9ec6573575b2444e8d526e48e0d8d6d5cf4e071e6e06530",
        },
    },
    "libandroid-shmem": {
        "dir": "liba/libandroid-shmem",
        "ver": "0.7",
        "sha": {
            "aarch64": "0da3a24d558b93c92bcf8d611e0826a99ff96e396b148e6cdf33b47c47c57ff6",
            "x86_64": "ffa9e4c87467b158b148d0ff92dda796aa038276c2075af3269cdcdb06f25797",
        },
    },
}


def fetch(url):
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=120
    ) as resp:
        return resp.read()


def ar_members(blob):
    if not blob.startswith(b"!<arch>\n"):
        raise SystemExit("not an ar archive")
    out, off = {}, 8
    while off + 60 <= len(blob):
        header = blob[off : off + 60]
        name = header[0:16].decode("ascii", "replace").strip().rstrip("/")
        size = int(header[48:58].decode("ascii").strip() or "0")
        out[name] = blob[off + 60 : off + 60 + size]
        off += 60 + size + (size % 2)
    return out


def data_files(deb_blob):
    data = next(v for k, v in ar_members(deb_blob).items() if k.startswith("data.tar"))
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        for m in tar:
            if m.isfile():
                f = tar.extractfile(m)
                if f is not None:
                    files[m.name.lstrip("./")] = f.read()
    return files


def pick_suffix(files, suffix):
    hits = [(p, b) for p, b in files.items() if p.endswith(suffix)]
    if len(hits) != 1:
        raise SystemExit(f"expected one {suffix!r}, found {[h[0] for h in hits]}")
    return hits[0]


def pick_lib(files, stem):
    hits = [
        (p, b)
        for p, b in files.items()
        if re.fullmatch(rf"{re.escape(stem)}(\.so(\.[0-9]+)*)?", p.rsplit("/", 1)[-1])
    ]
    if not hits:
        raise SystemExit(f"{stem}.so* not found")
    hits.sort(key=lambda h: len(h[0]))
    return hits[-1]


def emit(arch, name, blob):
    dest = PREFIX / "opt" / arch / "lib" / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    print(f"{arch}: opt/{arch}/lib/{name} ({len(blob)} bytes)")


for arch in ARCHS:
    for pkg, spec in SOURCES.items():
        fname = f"{pkg}_{spec['ver']}_{arch}.deb"
        url = f"{POOL}/{spec['dir']}/{fname}"
        blob = fetch(url)
        got = hashlib.sha256(blob).hexdigest()
        want = spec["sha"][arch]
        if got != want:
            raise SystemExit(f"{fname}: sha256 {got} != pinned {want}")
        files = data_files(blob)
        if pkg == "proot":
            _, main_blob = pick_suffix(files, "files/usr/bin/proot")
            _, loader_blob = pick_suffix(files, "files/usr/libexec/proot/loader")
            if main_blob == loader_blob:
                raise SystemExit("loader and main binary identical — layout broken")
            emit(arch, "libproot.so", main_blob)
            emit(arch, "libproot-loader.so", loader_blob)
        else:
            _, lib_blob = pick_lib(files, pkg)
            emit(arch, f"{pkg}.so", lib_blob)

print("flet-proot repack complete ->", PREFIX)
PYEOF
