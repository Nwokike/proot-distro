#!/usr/bin/env python3
"""Build the flet-pillow wheel: Pillow 13.0.0 WITH XCB screen-capture support,
repackaged from pinned Termux debs.

Why this exists: the Flet Android Pillow wheel (pypi.flet.dev) is compiled
without XCB, so `PIL.ImageGrab.grab(xdisplay=...)` — the call termux-desk's
capture loop makes — raises "Pillow was built without XCB support". Termux's
own python-pillow deb IS compiled with XCB (libxcb is one of its build
dependencies), and Termux's Python (3.14.10) is the exact CPython our embedded
runtime provisions — so the compiled extension loads verbatim.

The wheel bundles:
- the `PIL` package from the python-pillow deb (py files + core `_imaging.so`;
  the optional codec plugins (_avif/_webp/_imagingft/_imagingtk/_imagingcms)
  are LEFT OUT — they drag huge transitive libs and the capture path never
  imports them; Pillow degrades gracefully when a plugin is absent),
- the ELF closure `_imaging.so` needs at runtime (libxcb + libXau + libXdmcp +
  libtiff + libjpeg.so.8 + libopenjp2 + libz.so.1 + libimagequant + liblzma +
  libzstd + libandroid-support) into `opt/lib/<jni>/`, which the Flet Android
  build copies into the APK's per-ABI native library directory — on the
  dynamic linker's search path when the python importer dlopens `_imaging.so`.

One self-contained file: the sha256 pins and the ELF/alignment checks live
below. Bumping a source = editing _PINNED_SOURCES (one commit). Stdlib only
(elf_tools comes from this scripts/ dir, same as the proot wheel builder).

Usage: uv run python scripts/build_flet_pillow_wheel.py --out wheels
"""

from __future__ import annotations

import argparse
import hashlib
import io
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from elf_tools import ALIGN_16K, ElfError, elf_info

REPO_ROOT = Path(__file__).resolve().parent.parent

DIST_NAME = "pillow"
PILLOW_VERSION = "13.0.0"
BUILD_TAG = "1"
TIMEOUT = 120.0
UA = "kiri-flet-pillow-wheel-builder/1.0 (+https://github.com/Nwokike/proot-distro)"
_POOL = "https://packages.termux.dev/apt/termux-main/pool/main"

# The ELF closure `_imaging.so` needs at runtime (computed from the debs with
# elf_tools: expand NEEDED until nothing unmet remains). Files are copied
# under their NEEDED names — the names the dynamic linker searches.
_BUNDLED_LIBS = (
    "libtiff.so",
    "libjpeg.so.8",
    "libopenjp2.so",
    "libz.so.1",
    "libimagequant.so",
    "libxcb.so",
    "libXau.so",
    "libXdmcp.so",
    "liblzma.so.5",
    "libzstd.so.1",
    "libandroid-support.so",
)

# Pillow plugin extensions we deliberately DO NOT bundle: each drags a big
# transitive lib set (libavif→aom/dav1d/rav1e, _webp→webp, _imagingft→freetype/
# raqm, _imagingtk→tk) and the display capture path never imports them. Pillow
# suppresses missing-plugin import failures, so the absence is graceful.
_SKIPPED_PLUGINS = (
    "_avif.so",
    "_webp.so",
    "_imagingft.so",
    "_imagingtk.so",
    "_imagingcms.so",
)

# ── the pin set (bump a source = one edit here) ──────────────────────────────
_PINNED_SOURCES = {
    "aarch64": {
        "jni": "arm64-v8a",
        "ext_suffix": "cpython-314-aarch64-linux-android.so",
        "packages": {
            "python-pillow": {
                "file": "p/python-pillow/python-pillow_13.0.0_aarch64.deb",
                "sha256": "6aabed29cc98cec8ea380214194297d95f861f9a27c0f5486b0a82c6a4799050",
            },
            "libxcb": {
                "file": "libx/libxcb/libxcb_1.17.0-1_aarch64.deb",
                "sha256": "191c3642b6a8c754bc75b69b94a81858ecb5f18766dc085aff55559b8087ad34",
            },
            "libxau": {
                "file": "libx/libxau/libxau_1.0.12-2_aarch64.deb",
                "sha256": "2d86bed61ce89dd8fdb55e565aede10155f2ce3adaccb61d5f1375aec3314083",
            },
            "libxdmcp": {
                "file": "libx/libxdmcp/libxdmcp_1.1.5-2_aarch64.deb",
                "sha256": "caea0cf5c0028af0840774094b8900ef7afffd8f9bbd7b1abfbe66851f0d6077",
            },
            "libtiff": {
                "file": "libt/libtiff/libtiff_4.7.2_aarch64.deb",
                "sha256": "998c583d65d7d42dcb177548a218545661f02385a51bb9f5c24f0da4fd046574",
            },
            "libjpeg-turbo": {
                "file": "libj/libjpeg-turbo/libjpeg-turbo_3.2.1_aarch64.deb",
                "sha256": "3e46721f2fbb10d5f53a45b99e2549d18a34ca3751aa4b704b3404fcdea5f8e7",
            },
            "openjpeg": {
                "file": "o/openjpeg/openjpeg_2.5.4_aarch64.deb",
                "sha256": "93ad32c8caa0eb8943e2dd86b5c2eaf48a767709a3fa069a5b670d948656c7d8",
            },
            "zlib": {
                "file": "z/zlib/zlib_1.4_aarch64.deb",
                "sha256": "e3027565ae50bcd8ba5113c988b589754ae192c9cc3e6afbe3e4ed7c06b2598e",
            },
            "libimagequant": {
                "file": "libi/libimagequant/libimagequant_4.4.1_aarch64.deb",
                "sha256": "fdbb4f1eb6c62d76fd47bbc0d7773ba9e548eddcdf6cba0809f0b76e15da4b99",
            },
            "liblzma": {
                "file": "libl/liblzma/liblzma_5.8.4_aarch64.deb",
                "sha256": "44e95e6e60dddb3705e60a344a4f009a1085a210797342b721eaff41b44033c0",
            },
            "zstd": {
                "file": "z/zstd/zstd_1.5.7-1_aarch64.deb",
                "sha256": "e1b4a5113648da8de189620ba1fce74c48b2d0833d9043391b9a1c91fb606fd3",
            },
            "libandroid-support": {
                "file": "liba/libandroid-support/libandroid-support_29-1_aarch64.deb",
                "sha256": "f2f145d6135ad4843ac9670153be3e3944dc1e6f1736d46d2306c28f2b86f517",
            },
        },
    },
    "x86_64": {
        "jni": "x86_64",
        "ext_suffix": "cpython-314-x86_64-linux-android.so",
        "packages": {
            "python-pillow": {
                "file": "p/python-pillow/python-pillow_13.0.0_x86_64.deb",
                "sha256": "25458f8872d1a28a1b42f77bd39972a769fa55ec8931e6035518081b942031ad",
            },
            "libxcb": {
                "file": "libx/libxcb/libxcb_1.17.0-1_x86_64.deb",
                "sha256": "38da04c89e95026282c1277ca475fe02aca78735e0af48e3aada6b5aed78b894",
            },
            "libxau": {
                "file": "libx/libxau/libxau_1.0.12-2_x86_64.deb",
                "sha256": "b964143f84f11270ba14baf9a747b9732f5a9b84d2ca0e70ca26ba0364e0ce0b",
            },
            "libxdmcp": {
                "file": "libx/libxdmcp/libxdmcp_1.1.5-2_x86_64.deb",
                "sha256": "814a80d52fdfd193286f3a2e50215a10f03f6e64579cbdef3886cf499adf896d",
            },
            "libtiff": {
                "file": "libt/libtiff/libtiff_4.7.2_x86_64.deb",
                "sha256": "8548fb44835a463fa1a0c1d770c0bae9e327b0af567682113f01cac2673d3f6a",
            },
            "libjpeg-turbo": {
                "file": "libj/libjpeg-turbo/libjpeg-turbo_3.2.1_x86_64.deb",
                "sha256": "9a4399b4e26c58b98a2d9f38bfc7c0db883db273627efade044a08eabc54d04c",
            },
            "openjpeg": {
                "file": "o/openjpeg/openjpeg_2.5.4_x86_64.deb",
                "sha256": "e66866f64446380a6d8bec217d54dac08d163c6d3ce81cf341b50a218174a29a",
            },
            "zlib": {
                "file": "z/zlib/zlib_1.4_x86_64.deb",
                "sha256": "55ab8f16e492d6ed03c2e2bf701af52cf54a313442dd7adedd3d6f3e3eba2e4f",
            },
            "libimagequant": {
                "file": "libi/libimagequant/libimagequant_4.4.1_x86_64.deb",
                "sha256": "21fbf2645215cd46cac228d11d8410303a23eec115469c531dd9b25a0668664d",
            },
            "liblzma": {
                "file": "libl/liblzma/liblzma_5.8.4_x86_64.deb",
                "sha256": "100ea7503a0b9ecffa45e1f168d035651f2eb7aedbebe71dd21fc0da4a84ef16",
            },
            "zstd": {
                "file": "z/zstd/zstd_1.5.7-1_x86_64.deb",
                "sha256": "a76ba6c3d8742819bf4fff7780eb2e022269412700fc8f4471f530cc0d81833f",
            },
            "libandroid-support": {
                "file": "liba/libandroid-support/libandroid-support_29-1_x86_64.deb",
                "sha256": "665900760c05959ec076082a0941f05bd452f301e5a70bdfa7383fd3404d44d5",
            },
        },
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="wheels", help="output directory for wheels")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    wheel_paths: list[Path] = []
    for arch, spec in _PINNED_SOURCES.items():
        jni = spec["jni"]
        print(f"── {arch} ({jni}) ──────────────────────────────")
        extracted: dict[str, dict[str, bytes]] = {}
        for pkg, pin in spec["packages"].items():
            url = f"{_POOL}/{pin['file']}"
            print(f"  fetching {pin['file']} …")
            blob = fetch(url)
            got = sha256(blob)
            if got != pin["sha256"]:
                raise SystemExit(
                    f"{pin['file']}: sha256 mismatch\n  expected {pin['sha256']}\n  got      {got}"
                )
            extracted[pkg] = deb_payloads(blob)

        # PIL package root inside the python-pillow deb.
        pil_members = [k for k in extracted["python-pillow"] if "/site-packages/PIL/" in k]
        if not pil_members:
            raise SystemExit(f"{arch}: python-pillow deb has no PIL/ site-packages")
        pil_prefix = pil_members[0].rsplit("/PIL/", 1)[0] + "/PIL/"

        entries: dict[str, bytes] = {}
        for member, blob in sorted(extracted["python-pillow"].items()):
            if not member.startswith(pil_prefix):
                continue
            rel = member[len(pil_prefix) :]
            # keep ONLY the core extension; optional codec plugins are
            # skipped on purpose (see _SKIPPED_PLUGINS rationale above)
            if rel.endswith(".so") and rel != f"_imaging.{spec['ext_suffix']}":
                continue
            entries[f"PIL/{rel}"] = blob

        if f"PIL/_imaging.{spec['ext_suffix']}" not in entries:
            raise SystemExit(f"{arch}: core _imaging extension missing from deb")

        # ELF closure libraries → opt/lib/<jni>/ under their NEEDED names.
        # debs ship the real file (libjpeg.so.8.3.2) plus a SYMLINK under the
        # soname (libjpeg.so.8) — tarfile skips symlinks, so resolve each
        # wanted name to the longest real file that carries its content.
        all_lib_files: dict[str, bytes] = {}
        for pkg, data in extracted.items():
            if pkg == "python-pillow":
                continue
            for member, blob in data.items():
                base = member.rsplit("/", 1)[-1]
                if ".so" in base:
                    all_lib_files[base] = blob
        lib_blobs: dict[str, bytes] = {}
        for wanted in _BUNDLED_LIBS:
            if wanted in all_lib_files:
                lib_blobs[wanted] = all_lib_files[wanted]
                continue
            stem = wanted.split(".so")[0]
            hits = [
                (name, blob) for name, blob in all_lib_files.items() if name.startswith(stem + ".")
            ]
            if not hits:
                raise SystemExit(f"{arch}: closure lib {wanted} not found in debs")
            hits.sort(key=lambda nb: len(nb[0]))
            lib_blobs[wanted] = hits[0][1]
        for name in _BUNDLED_LIBS:
            entries[f"opt/lib/{jni}/{name}"] = lib_blobs[name]

        # Manifest inside the package documents the provenance.
        entries["PIL/_flet_xcb_manifest.py"] = (
            '"""Pillow 13.0.0 repackaged from Termux debs WITH XCB\n'
            "screen-capture support for the Flet Android runtime.\n\n"
            "Sources (Termux main pool, sha256-pinned in\n"
            "scripts/build_flet_pillow_wheel.py): "
            + ", ".join(sorted(spec["packages"]))
            + '\n"""\n'
        ).encode()

        wheel_name = f"{DIST_NAME}-{PILLOW_VERSION}-{BUILD_TAG}-cp314-cp314-android_24_{jni}.whl"
        wheel_path = out_dir / wheel_name
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, blob in sorted(entries.items()):
                zf.writestr(name, blob)
            dist_info = [
                (
                    f"pillow-{PILLOW_VERSION}.dist-info/METADATA",
                    "Metadata-Version: 2.1\n"
                    f"Name: {DIST_NAME}\n"
                    f"Version: {PILLOW_VERSION}\n"
                    "Summary: Pillow 13.0.0 with XCB screen capture (Termux repackage)\n",
                ),
                (
                    f"pillow-{PILLOW_VERSION}.dist-info/WHEEL",
                    "Wheel-Version: 1.0\n"
                    "Generator: kiri-flet-pillow-wheel-builder\n"
                    "Root-Is-Purelib: false\n"
                    f"Tag: cp314-cp314-android_24_{jni}\n",
                ),
            ]
            for name, blob in dist_info:
                zf.writestr(name, blob)

        # Alignment + parse checks on what we just wrote.
        with zipfile.ZipFile(wheel_path) as zf:
            for name in zf.namelist():
                if name.endswith(".so"):
                    blob = zf.read(name)
                    try:
                        info = elf_info(blob, name)
                    except ElfError as exc:
                        raise SystemExit(f"{wheel_name}/{name}: {exc}") from exc
                    if info["align"] is not None and info["align"] < ALIGN_16K:
                        raise SystemExit(
                            f"{wheel_name}/{name}: alignment {info['align']} < {ALIGN_16K}"
                        )
        print(f"  wrote {wheel_path} ({wheel_path.stat().st_size} bytes)")
        wheel_paths.append(wheel_path)

    print("\nOK: pillow wheels with XCB support written:")
    for path in wheel_paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
