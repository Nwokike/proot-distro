#!/usr/bin/env python3
"""Build the flet-xvnc wheel: TigerVNC's Xvnc repackaged from pinned Termux debs.

Why this exists: Xvnc is an X server AND a VNC server in one process. Running it
inside the app (from the APK's native-library dir, exactly like proot) means the
guest container needs NO X packages at all — no Xvfb, no xauth, no xclip — and
the app needs no screen-capture pipeline (no Pillow/XCB, no JPEG encoder):
Xvnc pushes framebuffer updates over RFB on damage, and the app bridges
WebSocket<->RFB for the noVNC viewer. Input and clipboard ride the same VNC
connection (XTEST + ServerCutText), so the guest-side bridges disappear too.

The wheel bundles:
- the Xvnc binary as opt/lib/<jni>/libXvnc.so (jniLibs = exec-allowed, the same
  trick the proot wheel uses for libproot.so),
- xkbcomp (as libxkbcomp.so) — Xorg invokes it to compile the keymap at startup,
- the ELF closure Xvnc/xkbcomp need at runtime (libcrypto, libjpeg, the gnutls
  stack, libpixman, libXfont2, libXau, libXdmcp, libxshmfence, the libglvnd
  dispatcher chain, libxkbfile) as opt/lib/<jni>/lib*.so,
- the xkb data tree (xkeyboard-config) as package data under flet_xvnc/data/xkb.

NOT bundled (provided elsewhere): libandroid-shmem.so (the flet-proot wheel),
libc++_shared.so (the Flet runtime), libc/libm/libdl (Android itself).

One self-contained file: the sha256 pins and the ELF/alignment checks live
below. Bumping a source = editing _PINNED_SOURCES (one commit). Stdlib only
(elf_tools comes from this scripts/ dir, same as the other wheel builders).

Usage: uv run python scripts/build_flet_xvnc_wheel.py --out wheels
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from elf_tools import ALIGN_16K, ElfError, elf_info, unmet_needed

DIST_NAME = "flet_xvnc"
XVNC_VERSION = "1.16.2"
BUILD_TAG = "1"
TIMEOUT = 120.0
UA = "kiri-flet-xvnc-wheel-builder/1.0 (+https://github.com/Nwokike/proot-distro)"

# Termux repo roots: main for the libs, x11 for the server packages. Each pin's
# path is the deb's own Filename field, relative to its repo root.
_POOL_MAIN = "https://packages.termux.dev/apt/termux-main"
_POOL_X11 = "https://packages.termux.dev/apt/termux-x11"

# ELF payloads: wanted jniLibs name -> (pool, package, explicit subpath or None).
# `None` resolves by soname stem (libjpeg.so -> libjpeg.so.8.3.2 in the deb), so
# the pins survive upstream version bumps of the point release.
_ELF_PAYLOADS: dict[str, tuple[str, str, str | None]] = {
    "libXvnc.so": (_POOL_X11, "tigervnc", "data/data/com.termux/files/usr/bin/Xvnc"),
    "libxkbcomp.so": (_POOL_MAIN, "xorg-xkbcomp", "data/data/com.termux/files/usr/bin/xkbcomp"),
    "libcrypto.so": (_POOL_MAIN, "openssl", None),
    "libjpeg.so": (_POOL_MAIN, "libjpeg-turbo", None),
    "libgnutls.so": (_POOL_MAIN, "libgnutls", None),
    "libnettle.so": (_POOL_MAIN, "libnettle", None),
    "libhogweed.so": (_POOL_MAIN, "libnettle", None),
    "libgmp.so": (_POOL_MAIN, "libgmp", None),
    "libz.so": (_POOL_MAIN, "zlib", None),
    "libpixman-1.so": (_POOL_MAIN, "libpixman", None),
    "libXfont2.so": (_POOL_MAIN, "libxfont2", None),
    "libXau.so": (_POOL_MAIN, "libxau", None),
    "libXdmcp.so": (_POOL_MAIN, "libxdmcp", None),
    "libxshmfence.so": (_POOL_MAIN, "libxshmfence", None),
    "libGL.so": (_POOL_MAIN, "libglvnd", None),
    "libGLX.so": (_POOL_MAIN, "libglvnd", None),
    "libGLdispatch.so": (_POOL_MAIN, "libglvnd", None),
    "libxkbfile.so": (_POOL_MAIN, "libxkbfile", None),
    # xkbcomp's own link closure (Xorg invokes it to compile the keymap).
    "libX11.so": (_POOL_MAIN, "libx11", None),
    "libxcb.so": (_POOL_MAIN, "libxcb", None),
    "libandroid-support.so": (_POOL_MAIN, "libandroid-support", None),
    # libgnutls' link closure (Xvnc links gnutls for VeNCrypt; unused with
    # -SecurityTypes None, but DT_NEEDED makes it mandatory at load time).
    "libzstd.so": (_POOL_MAIN, "zstd", None),
    "libp11-kit.so": (_POOL_MAIN, "p11-kit", None),
    "libidn2.so": (_POOL_MAIN, "libidn2", None),
    "libunistring.so": (_POOL_MAIN, "libunistring", None),
    "libtasn1.so": (_POOL_MAIN, "libtasn1", None),
    "libffi.so": (_POOL_MAIN, "libffi", None),
    "libiconv.so": (_POOL_MAIN, "libiconv", None),
    # libXfont2's font stack (core X fonts).
    "libfontenc.so": (_POOL_X11, "libfontenc", None),
    "libfreetype.so": (_POOL_MAIN, "freetype", None),
    # termux's real file is libpng16.so (libpng.so is a symlink), so the stem
    # search cannot find it.
    "libpng.so": (_POOL_MAIN, "libpng", "data/data/com.termux/files/usr/lib/libpng16.so"),
    "libbrotlidec.so": (_POOL_MAIN, "brotli", None),
    "libbrotlicommon.so": (_POOL_MAIN, "brotli", None),
    "libbz2.so": (_POOL_MAIN, "libbz2", None),
}

# Package-data payloads: (package, source prefix, destination prefix). Termux
# ships the xkb tree under share/xkeyboard-config-2/ (not share/X11/xkb/); the
# contents ARE the standard xkb root (compat/ keycodes/ types/ symbols/ rules/…).
_DATA_PAYLOADS: tuple[tuple[str, str, str], ...] = (
    (
        "xkeyboard-config",
        "data/data/com.termux/files/usr/share/xkeyboard-config-2/",
        "flet_xvnc/data/xkb/",
    ),
)

# ── the pin set (bump a source = one edit here) ──────────────────────────────
_PINNED_SOURCES = {
    "aarch64": {
        "jni": "arm64-v8a",
        "platform": "arm64_v8a",
        "packages": {
            "tigervnc": (
                "pool/main/t/tigervnc/tigervnc_1.16.2-1_aarch64.deb",
                "3d844963554f7b5b76527312329e8834ff060d6e3512b750044b79de21aa3e11",
            ),
            "xorg-xkbcomp": (
                "pool/main/x/xorg-xkbcomp/xorg-xkbcomp_1.5.0_aarch64.deb",
                "ee52d69758a8fcebc2d7f0bd1805a300f18a3472d43fc2eb45867463448cb4a9",
            ),
            "openssl": (
                "pool/main/o/openssl/openssl_1:3.6.5_aarch64.deb",
                "a2fb7856875e63ef6b90442752e05974813372c3ca86d2513a78ea43c67a0f8b",
            ),
            "libjpeg-turbo": (
                "pool/main/libj/libjpeg-turbo/libjpeg-turbo_3.2.1_aarch64.deb",
                "3e46721f2fbb10d5f53a45b99e2549d18a34ca3751aa4b704b3404fcdea5f8e7",
            ),
            "libgnutls": (
                "pool/main/libg/libgnutls/libgnutls_3.8.13-1_aarch64.deb",
                "eb12f2cf82923caf288edd99bc4c19a9dd0cf1de4a03855ff4457a1bbdae146d",
            ),
            "libnettle": (
                "pool/main/libn/libnettle/libnettle_4.0+really3.10.2_aarch64.deb",
                "f2d2a84083e66beab642e88496eb16976ccdb12d1278466e687f01431db8a5fb",
            ),
            "libgmp": (
                "pool/main/libg/libgmp/libgmp_6.3.0-2_aarch64.deb",
                "5a3c1325638946ca212ddcb89bffb2c4459b4c90757d6e69f820e176534037fa",
            ),
            "zlib": (
                "pool/main/z/zlib/zlib_1.4_aarch64.deb",
                "e3027565ae50bcd8ba5113c988b589754ae192c9cc3e6afbe3e4ed7c06b2598e",
            ),
            "libpixman": (
                "pool/main/libp/libpixman/libpixman_0.46.4-1_aarch64.deb",
                "364b8c82ff68f8513930e5d413459fb7c52eccc7ba75a97a8c5a38760eee8d33",
            ),
            "libxfont2": (
                "pool/main/libx/libxfont2/libxfont2_2.0.9_aarch64.deb",
                "1bd623392cff4dc3fda461e31e9b5f98e7fdf5f51ad9199d2dcdf8feb3e615e2",
            ),
            "libxau": (
                "pool/main/libx/libxau/libxau_1.0.12-2_aarch64.deb",
                "2d86bed61ce89dd8fdb55e565aede10155f2ce3adaccb61d5f1375aec3314083",
            ),
            "libxdmcp": (
                "pool/main/libx/libxdmcp/libxdmcp_1.1.5-2_aarch64.deb",
                "caea0cf5c0028af0840774094b8900ef7afffd8f9bbd7b1abfbe66851f0d6077",
            ),
            "libxshmfence": (
                "pool/main/libx/libxshmfence/libxshmfence_1.3.3-1_aarch64.deb",
                "7644c2969c2ce4d763785bd2a85eb32ccf8e5ad40228cd92b193f7edb6398d92",
            ),
            "libglvnd": (
                "pool/main/libg/libglvnd/libglvnd_1.7.0-1_aarch64.deb",
                "67f3fd247e4279a7fceddbd2929f8b53e87c255edfc9c07d0dee7df5fe243d2c",
            ),
            "libxkbfile": (
                "pool/main/libx/libxkbfile/libxkbfile_1.2.0_aarch64.deb",
                "2456caefcf93f5821f6c7c753eae50ea015864c948e678f3c8e2aec9c3c3dbd5",
            ),
            "xkeyboard-config": (
                "pool/main/x/xkeyboard-config/xkeyboard-config_2.49_all.deb",
                "9523dbe04fd7fba2218451813041872957dca459d86dfed9c23a3b247e8fa371",
            ),
            "libx11": (
                "pool/main/libx/libx11/libx11_1.8.14_aarch64.deb",
                "c5206ee9cc26a63985d110b57bc24f23c7c97505e6100c4d6a8547a1aeed5532",
            ),
            "libxcb": (
                "pool/main/libx/libxcb/libxcb_1.17.0-1_aarch64.deb",
                "191c3642b6a8c754bc75b69b94a81858ecb5f18766dc085aff55559b8087ad34",
            ),
            "libandroid-support": (
                "pool/main/liba/libandroid-support/libandroid-support_29-1_aarch64.deb",
                "f2f145d6135ad4843ac9670153be3e3944dc1e6f1736d46d2306c28f2b86f517",
            ),
            "zstd": (
                "pool/main/z/zstd/zstd_1.5.7-1_aarch64.deb",
                "e1b4a5113648da8de189620ba1fce74c48b2d0833d9043391b9a1c91fb606fd3",
            ),
            "p11-kit": (
                "pool/main/p/p11-kit/p11-kit_0.26.6_aarch64.deb",
                "e6a305edbfcf6a907bd1f09bedbcbbb06ca7784116300bd297a769c971595424",
            ),
            "libidn2": (
                "pool/main/libi/libidn2/libidn2_2.3.8-1_aarch64.deb",
                "a450a1ba25759ebf78738484a3efee316c51a1fe7bafb0b01a68e2c058a91020",
            ),
            "libunistring": (
                "pool/main/libu/libunistring/libunistring_1.5_aarch64.deb",
                "8853ca1421d6472046a0683d53084b26db1caa50a3aa2bf6422a1276c7dba69b",
            ),
            "libtasn1": (
                "pool/main/libt/libtasn1/libtasn1_4.21.0_aarch64.deb",
                "1d02de3a7e5ef4ff7d893597091176b8ddf135f1ddfacff951f76c18711a7342",
            ),
            "libffi": (
                "pool/main/libf/libffi/libffi_3.8.0_aarch64.deb",
                "4f255badf74cd31f6a2801c17fa1444199c84c834b517b7c843e2fe9ebe91d77",
            ),
            "libiconv": (
                "pool/main/libi/libiconv/libiconv_1.19.1_aarch64.deb",
                "a1c6323eff4f660e16ae6f5832356444b3269c19a4f61146355a49e7c4be5ed1",
            ),
            "libfontenc": (
                "pool/main/libf/libfontenc/libfontenc_1.1.9_aarch64.deb",
                "2ce4c69bdfb7a81ea2ab1605e983a7a31302c4f0dcc4b7fab9885c34c2c3bb1c",
            ),
            "freetype": (
                "pool/main/f/freetype/freetype_2.15.0_aarch64.deb",
                "fe217807b22aa40029874eb1d9e01b89a01b5f1e4f0556c4de9c8e83c4db4256",
            ),
            "libpng": (
                "pool/main/libp/libpng/libpng_1.6.59_aarch64.deb",
                "32d61f0b1a60cf7283aa3a80e288737493df2c6b84c8c749606b77c94a10f2b2",
            ),
            "brotli": (
                "pool/main/b/brotli/brotli_1.2.1_aarch64.deb",
                "4fba29438b2b44f8470d52173b4548e938542dc2fc632f8699be5a284cbb9485",
            ),
            "libbz2": (
                "pool/main/libb/libbz2/libbz2_1.0.8-8_aarch64.deb",
                "4335d7f060650b0aabef545d1334c2f9f280223d5962e13c24a00ec934b794ba",
            ),
        },
    },
    "x86_64": {
        "jni": "x86_64",
        "platform": "x86_64",
        "packages": {
            "tigervnc": (
                "pool/main/t/tigervnc/tigervnc_1.16.2-1_x86_64.deb",
                "bdae705e72a18c74609a56b711b0e631828a97d5c1f6513ca9cf0248f6df77b1",
            ),
            "xorg-xkbcomp": (
                "pool/main/x/xorg-xkbcomp/xorg-xkbcomp_1.5.0_x86_64.deb",
                "258b913a41cc83a54564ff9748d9faee9e310c11f2323a68048d38bdbcace180",
            ),
            "openssl": (
                "pool/main/o/openssl/openssl_1:3.6.5_x86_64.deb",
                "540f144592d23d35672976e175ede1b5d8cf464f153f646df5d4e6dcd8491a15",
            ),
            "libjpeg-turbo": (
                "pool/main/libj/libjpeg-turbo/libjpeg-turbo_3.2.1_x86_64.deb",
                "9a4399b4e26c58b98a2d9f38bfc7c0db883db273627efade044a08eabc54d04c",
            ),
            "libgnutls": (
                "pool/main/libg/libgnutls/libgnutls_3.8.13-1_x86_64.deb",
                "c64e2016faba3c601deed91c94812f44636c545809c1938ebbf92c52024c273f",
            ),
            "libnettle": (
                "pool/main/libn/libnettle/libnettle_4.0+really3.10.2_x86_64.deb",
                "e754086e59615e260bdb24b8000732a3eaedefa40c8c11e30a30a9c22877e815",
            ),
            "libgmp": (
                "pool/main/libg/libgmp/libgmp_6.3.0-2_x86_64.deb",
                "743e742d1d2900bffecf17e85487c830df871653bcdaede223425d2c62ac1b49",
            ),
            "zlib": (
                "pool/main/z/zlib/zlib_1.4_x86_64.deb",
                "55ab8f16e492d6ed03c2e2bf701af52cf54a313442dd7adedd3d6f3e3eba2e4f",
            ),
            "libpixman": (
                "pool/main/libp/libpixman/libpixman_0.46.4-1_x86_64.deb",
                "169e3ce2e2adf1cbb51c39fc7e7e2532f519b3e5362fef24e895d6c98e82a8f5",
            ),
            "libxfont2": (
                "pool/main/libx/libxfont2/libxfont2_2.0.9_x86_64.deb",
                "e36df5ae9a740415dbf895180f7e1668e55b50b451d7d7f1533bef35382764bc",
            ),
            "libxau": (
                "pool/main/libx/libxau/libxau_1.0.12-2_x86_64.deb",
                "b964143f84f11270ba14baf9a747b9732f5a9b84d2ca0e70ca26ba0364e0ce0b",
            ),
            "libxdmcp": (
                "pool/main/libx/libxdmcp/libxdmcp_1.1.5-2_x86_64.deb",
                "814a80d52fdfd193286f3a2e50215a10f03f6e64579cbdef3886cf499adf896d",
            ),
            "libxshmfence": (
                "pool/main/libx/libxshmfence/libxshmfence_1.3.3-1_x86_64.deb",
                "5278f6371b1847b657bfd320d7e234c6858921737e2b14f6b2174cd46fa25732",
            ),
            "libglvnd": (
                "pool/main/libg/libglvnd/libglvnd_1.7.0-1_x86_64.deb",
                "582c1a31b84c7da44161c72a757516cda89aaa9d520a155a066ed0910db2a93d",
            ),
            "libxkbfile": (
                "pool/main/libx/libxkbfile/libxkbfile_1.2.0_x86_64.deb",
                "676c4294e85a2ca9e3f95f74e0791d0b57b4a31f28a536a5801a2d76d30b8252",
            ),
            "xkeyboard-config": (
                "pool/main/x/xkeyboard-config/xkeyboard-config_2.49_all.deb",
                "9523dbe04fd7fba2218451813041872957dca459d86dfed9c23a3b247e8fa371",
            ),
            "libx11": (
                "pool/main/libx/libx11/libx11_1.8.14_x86_64.deb",
                "e155dc1171b12a3f625e8516aa195d3c4ac63b850b079b203029b1b0874d497d",
            ),
            "libxcb": (
                "pool/main/libx/libxcb/libxcb_1.17.0-1_x86_64.deb",
                "38da04c89e95026282c1277ca475fe02aca78735e0af48e3aada6b5aed78b894",
            ),
            "libandroid-support": (
                "pool/main/liba/libandroid-support/libandroid-support_29-1_x86_64.deb",
                "665900760c05959ec076082a0941f05bd452f301e5a70bdfa7383fd3404d44d5",
            ),
            "zstd": (
                "pool/main/z/zstd/zstd_1.5.7-1_x86_64.deb",
                "a76ba6c3d8742819bf4fff7780eb2e022269412700fc8f4471f530cc0d81833f",
            ),
            "p11-kit": (
                "pool/main/p/p11-kit/p11-kit_0.26.6_x86_64.deb",
                "6fa55cdc0fb71c3f805a2362427d2063d319309baa4e4c3e8b243c8d8894d607",
            ),
            "libidn2": (
                "pool/main/libi/libidn2/libidn2_2.3.8-1_x86_64.deb",
                "4f4f91f5bc8b7b215f153fb96808f75b55a86c6e8ec66ff3286b859cb6048500",
            ),
            "libunistring": (
                "pool/main/libu/libunistring/libunistring_1.5_x86_64.deb",
                "261efedb55f20f18ea943a78f35d89791a4805e80684bdab39dc15a8f9a93af8",
            ),
            "libtasn1": (
                "pool/main/libt/libtasn1/libtasn1_4.21.0_x86_64.deb",
                "1680378db0b5350d563783eb29ffe7c2397e204c8ab031047cfc3316e61b879b",
            ),
            "libffi": (
                "pool/main/libf/libffi/libffi_3.8.0_x86_64.deb",
                "59121ca4bc5f5735d7bb603bd99548983064e8fde97d236e97122cb87d3452a3",
            ),
            "libiconv": (
                "pool/main/libi/libiconv/libiconv_1.19.1_x86_64.deb",
                "3eb0c454676ad24d26c79601721b2eb3f9485c611ad0179fb86b17229344f46d",
            ),
            "libfontenc": (
                "pool/main/libf/libfontenc/libfontenc_1.1.9_x86_64.deb",
                "41dcda5d9edc049eb84137396e6935c0f6af484a21602687dee758b535438e4f",
            ),
            "freetype": (
                "pool/main/f/freetype/freetype_2.15.0_x86_64.deb",
                "c82adef4b84b9ef502c64c23857e3d2cac611c7bfa6943f7d4c9d0fcfec733e3",
            ),
            "libpng": (
                "pool/main/libp/libpng/libpng_1.6.59_x86_64.deb",
                "b5bbc3c552255d072ac5e53ec7641128f373d09e404abd01a8285b1a4a7f324c",
            ),
            "brotli": (
                "pool/main/b/brotli/brotli_1.2.1_x86_64.deb",
                "de652571f92e74c7f0cfe71e16cfc6ead340b184dda024614e6cab3048234142",
            ),
            "libbz2": (
                "pool/main/libb/libbz2/libbz2_1.0.8-8_x86_64.deb",
                "f6f81d38a40c1626202da1e87727e5a3e6de296b1c0eb252af8948646b164ca0",
            ),
        },
    },
}

# Provided by other wheels / the runtime / Android — never shipped here.
_EXTERNAL_SONAMES = {"libandroid-shmem.so", "libc++_shared.so"}

# Packages that live in the Termux x11 repo rather than main.
_X11_PACKAGES = {
    "tigervnc",
    "xorg-xkbcomp",
    "libxfont2",
    "libxkbfile",
    "xkeyboard-config",
    "libfontenc",
}


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


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
    members = _parse_ar(deb_blob)
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


def _resolve_payload(
    pkg_files: dict[str, bytes], wanted: str, explicit: str | None
) -> tuple[str, bytes]:
    """The deb member for `wanted`: an explicit subpath, or the longest real
    file whose name is `wanted` or a versioned form of its stem."""
    if explicit is not None:
        if explicit not in pkg_files:
            raise SystemExit(f"explicit payload {explicit!r} not found")
        return explicit, pkg_files[explicit]
    if wanted in pkg_files:
        return wanted, pkg_files[wanted]
    stem = wanted[: -len(".so")]
    hits = [
        (name, blob)
        for name, blob in pkg_files.items()
        if ".so" in name.rsplit("/", 1)[-1] and name.rsplit("/", 1)[-1].startswith(stem + ".")
    ]
    if not hits:
        raise SystemExit(f"payload {wanted} not found in deb")
    hits.sort(key=lambda nb: len(nb[0].rsplit("/", 1)[-1]))
    return hits[-1]


def _soname_rewrites(resolved: dict[str, tuple[str, bytes]]) -> tuple[tuple[bytes, bytes], ...]:
    """Map each payload's real SONAME to its shipped `lib*.so` name.

    AGP only packages `lib*.so` from jniLibs, so a versioned soname
    (libjpeg.so.8) would never be found on device. Each replacement is
    strictly shorter, so null-padding preserves string length, section
    offsets and 16 KB alignment.
    """
    rewrites: list[tuple[bytes, bytes]] = []
    for wanted, (_real, blob) in resolved.items():
        try:
            soname = elf_info(blob, wanted)["soname"]
        except ElfError as exc:
            raise SystemExit(str(exc)) from exc
        if soname and soname != wanted:
            old = soname.encode() + b"\0"
            new = wanted.encode() + b"\0"
            if len(new) > len(old):
                raise SystemExit(f"{wanted}: soname {soname!r} is shorter than the shipped name")
            rewrites.append((old, new + b"\0" * (len(old) - len(new))))
    return tuple(rewrites)


def _rewrite(blob: bytes, rewrites: tuple[tuple[bytes, bytes], ...]) -> bytes:
    for old, new in rewrites:
        blob = blob.replace(old, new)
    return blob


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="wheels", help="output directory for wheels")
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    wheel_paths: list[Path] = []
    for arch, spec in _PINNED_SOURCES.items():
        jni = spec["jni"]
        tag = f"py3-none-android_24_{spec['platform']}"
        print(f"── {arch} ({jni}, tag {tag}) " + "─" * 30)

        extracted: dict[str, dict[str, bytes]] = {}
        for pkg, (rel, sha) in spec["packages"].items():
            pool = _POOL_X11 if pkg in _X11_PACKAGES else _POOL_MAIN
            url = f"{pool}/{rel}"
            print(f"  fetching {rel} …")
            blob = _fetch(url)
            got = hashlib.sha256(blob).hexdigest()
            if got != sha:
                raise SystemExit(f"{rel}: sha256 mismatch\n  expected {sha}\n  got      {got}")
            extracted[pkg] = _deb_payloads(blob)

        entries: dict[str, bytes] = {}

        # ── ELF payloads → opt/lib/<jni>/lib*.so ──────────────────────────────
        resolved: dict[str, tuple[str, bytes]] = {}
        for wanted, (_pool, pkg, explicit) in _ELF_PAYLOADS.items():
            real, blob = _resolve_payload(extracted[pkg], wanted, explicit)
            resolved[wanted] = (real, blob)
        rewrites = _soname_rewrites(resolved)
        for wanted, (_real, blob) in resolved.items():
            entries[f"opt/lib/{jni}/{wanted}"] = _rewrite(blob, rewrites)

        shipped = set(resolved) | _EXTERNAL_SONAMES
        for wanted in resolved:
            info = elf_info(entries[f"opt/lib/{jni}/{wanted}"], wanted)
            if info["align"] is not None and info["align"] < ALIGN_16K:
                raise SystemExit(f"{wanted}: PT_LOAD align {info['align']:#x} < {ALIGN_16K:#x}")
            missing = unmet_needed(info, shipped)
            if missing:
                raise SystemExit(
                    f"{wanted} needs {missing} but they are not shipped — extend the pin set"
                )

        # ── xkb data → package assets ─────────────────────────────────────────
        for pkg, src_prefix, dest_prefix in _DATA_PAYLOADS:
            members = {k: v for k, v in extracted[pkg].items() if k.startswith(src_prefix)}
            if not members:
                raise SystemExit(f"{pkg}: no files under {src_prefix}")
            for name, blob in sorted(members.items()):
                entries[f"{dest_prefix}{name[len(src_prefix) :]}"] = blob

        # ── provenance + licensing ────────────────────────────────────────────
        entries[f"{DIST_NAME}/__init__.py"] = (
            '"""Xvnc native payload for Flet Android apps (Termux repackage)."""\n'
            f"XVNC_VERSION = {XVNC_VERSION!r}\n"
        ).encode()
        entries[f"{DIST_NAME}/_sources.py"] = (
            "# Generated by build_flet_xvnc_wheel.py — do not edit.\n"
            f"XVNC_VERSION = {XVNC_VERSION!r}\n"
            f"ARCH = {arch!r}\n"
            f"SOURCES = {spec['packages']!r}\n"
        ).encode()

        dist_info = f"{DIST_NAME}-{XVNC_VERSION}.dist-info"
        lic = Path(__file__).resolve().parent.parent / "LICENSES"
        license_files = sorted(lic.glob("*.txt"))
        metadata = [
            "Metadata-Version: 2.1",
            f"Name: {DIST_NAME}",
            f"Version: {XVNC_VERSION}",
            "Summary: Xvnc (X server + VNC) native payload for Flet Android apps",
            "Requires-Python: >=3.10",
            "Requires-Dist: flet-proot==5.1.107.102",
            "License: GPL-2.0-or-later",
        ]
        metadata.extend(f"License-File: {lf.name}" for lf in license_files)
        entries[f"{dist_info}/METADATA"] = ("\n".join(metadata) + "\n").encode()
        entries[f"{dist_info}/WHEEL"] = (
            "Wheel-Version: 1.0\n"
            "Generator: kiri-flet-xvnc-wheel-builder\n"
            "Root-Is-Purelib: false\n"
            f"Tag: {tag}\n"
        ).encode()
        for lf in license_files:
            entries[f"{dist_info}/{lf.name}"] = lf.read_bytes()
        entries[f"{dist_info}/THIRD-PARTY.md"] = (
            "# flet-xvnc — third-party components\n\n"
            "Repackages verbatim binaries from the Termux apt repositories "
            "(architectures aarch64/x86_64), pinned and sha256-verified at build time.\n\n"
            "| Component | Version | License |\n|---|---|---|\n"
            "| TigerVNC (Xvnc) | 1.16.2 | GPL-2.0-or-later |\n"
            "| X.Org xkbcomp | 1.5.0 | MIT |\n"
            "| OpenSSL (libcrypto) | 3.6.5 | Apache-2.0 / SSLeay |\n"
            "| libjpeg-turbo | 3.2.1 | BSD-3-Clause |\n"
            "| GnuTLS / Nettle / Hogweed / GMP | 3.8.13 / 3.10.2 / 6.3.0 | LGPL-2.1-or-later |\n"
            "| libpixman / libXfont2 / libXau / libXdmcp / libxshmfence | — | MIT |\n"
            "| libglvnd | 1.7.0 | MIT |\n"
            "| xkeyboard-config | 2.49 | MIT |\n\n"
            "Source offer: see the companion app's LICENSES/ + THIRD-PARTY-SOURCES.md "
            "(github.com/Nwokike/proot-distro) and the upstream projects above.\n"
        ).encode()

        lines = []
        for name, blob in entries.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).rstrip(b"=").decode()
            lines.append(f"{name},sha256={digest},{len(blob)}")
        lines.append(f"{dist_info}/RECORD,,")
        entries[f"{dist_info}/RECORD"] = ("\n".join(lines) + "\n").encode()

        wheel_name = f"{DIST_NAME}-{XVNC_VERSION}-{BUILD_TAG}-{tag}.whl"
        wheel_path = out_dir / wheel_name
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, blob in sorted(entries.items()):
                zf.writestr(name, blob)

        print(f"  wrote {wheel_path.name} ({wheel_path.stat().st_size / 1e6:.1f} MB)")
        wheel_paths.append(wheel_path)

    print(f"\nOK: {len(wheel_paths)} Xvnc wheel(s) written to {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
