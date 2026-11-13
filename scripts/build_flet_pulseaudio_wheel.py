#!/usr/bin/env python3
"""Build the flet-pulseaudio wheel: PulseAudio repackaged from pinned Termux debs.

Why this exists: Termux's PulseAudio is patched with the Android audio modules —
the deb ships module-aaudio-sink.so, module-sles-sink.so AND module-sles-source.so
(microphone), plus module-native-protocol-tcp.so to serve guests. Running the
daemon inside the app (from the APK's native-library dir, exactly like proot)
means guest apps play sound and record the mic with NO guest packages: the app
exports PULSE_SERVER=127.0.0.1 into the session, and guest apps that link
libpulse (their own dependency) connect over the shared loopback.

The wheel bundles:
- the pulseaudio daemon binary as opt/lib/<jni>/libpulseaudio.so (jniLibs =
  exec-allowed, the same trick the proot wheel uses for libproot.so),
- its core libs (libpulse, libpulsecore-17.0, libpulsecommon-17.0,
  libprotocol-native, libprotocol-cli, libcli, librtp, libwebrtc-util,
  libpulse-simple),
- the modules the app loads (aaudio sink, sles sink+source, native-protocol-tcp,
  null/always sinks, pipe sink/source),
- the link closure those need (libltdl, libdbus-1, libiconv,
  libandroid-execinfo, libsndfile, libsoxr, libspeexdsp,
  libwebrtc-audio-processing),
- the stock pulse config as package data under flet_pulseaudio/data/pulse.

NOT bundled (provided elsewhere): libc++_shared.so (the Flet runtime),
libc/libm/libdl (Android itself).

One self-contained file: the sha256 pins and the ELF/alignment checks live
below. Bumping a source = editing _PINNED_SOURCES (one commit). Stdlib only
(elf_tools comes from this scripts/ dir, same as the other wheel builders).

Usage: uv run python scripts/build_flet_pulseaudio_wheel.py --out wheels
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

DIST_NAME = "flet_pulseaudio"
PA_VERSION = "17.0"
BUILD_TAG = "1"
TIMEOUT = 120.0
UA = "kiri-flet-pulseaudio-wheel-builder/1.0 (+https://github.com/Nwokike/proot-distro)"
_POOL = "https://packages.termux.dev/apt/termux-main"

# ELF payloads: wanted jniLibs name -> (package, explicit subpath or None).
_ELF_PAYLOADS: dict[str, tuple[str, str | None]] = {
    "libpulseaudio.so": ("pulseaudio", "data/data/com.termux/files/usr/bin/pulseaudio"),
    "libpulse.so": ("pulseaudio", None),
    "libpulsecore-17.0.so": ("pulseaudio", None),
    "libpulsecommon-17.0.so": ("pulseaudio", None),
    "libprotocol-native.so": ("pulseaudio", None),
    "libprotocol-cli.so": ("pulseaudio", None),
    "libcli.so": ("pulseaudio", None),
    "librtp.so": ("pulseaudio", None),
    "libpulse-simple.so": ("pulseaudio", None),
    # modules the app loads by absolute path (pulseaudio accepts a path in
    # --load; the compiled module dir is the Termux prefix, which does not
    # exist in our app).
    "module-aaudio-sink.so": ("pulseaudio", None),
    "module-sles-sink.so": ("pulseaudio", None),
    "module-sles-source.so": ("pulseaudio", None),
    "module-native-protocol-tcp.so": ("pulseaudio", None),
    "module-null-sink.so": ("pulseaudio", None),
    "module-always-sink.so": ("pulseaudio", None),
    "module-pipe-sink.so": ("pulseaudio", None),
    "module-pipe-source.so": ("pulseaudio", None),
    # link closure
    "libltdl.so": ("libltdl", None),
    "libdbus-1.so": ("dbus", None),
    "libiconv.so": ("libiconv", None),
    "libandroid-execinfo.so": ("libandroid-execinfo", None),
    "libsndfile.so": ("libsndfile", None),
    "libsoxr.so": ("libsoxr", None),
    "libspeexdsp.so": ("speexdsp", None),
    # libsndfile's codec closure (linked, though we never play files).
    "libFLAC.so": ("libflac", None),
    "libvorbis.so": ("libvorbis", None),
    "libvorbisenc.so": ("libvorbis", None),
    "libopus.so": ("libopus", None),
    "libogg.so": ("libogg", None),
    "libmpg123.so": ("libmpg123", None),
    "libmp3lame.so": ("libmp3lame", None),
}

# Package-data payloads: (package, source prefix, destination prefix).
_DATA_PAYLOADS: tuple[tuple[str, str, str], ...] = (
    (
        "pulseaudio",
        "data/data/com.termux/files/usr/etc/pulse/",
        "flet_pulseaudio/data/pulse/",
    ),
)

# ── the pin set (bump a source = one edit here) ──────────────────────────────
_PINNED_SOURCES = {
    "aarch64": {
        "jni": "arm64-v8a",
        "platform": "arm64_v8a",
        "packages": {
            "pulseaudio": (
                "pool/main/p/pulseaudio/pulseaudio_17.0-5_aarch64.deb",
                "4e110e32007fee5aaf67cfa2f35ae67c11ed53f45da857d0def426e2ca66f8c8",
            ),
            "libltdl": (
                "pool/main/libl/libltdl/libltdl_2.6.2_aarch64.deb",
                "7b4643fe9d0ab42c0c3c8a1018640816bdb43d422f2268a5e4ea80675624f539",
            ),
            "dbus": (
                "pool/main/d/dbus/dbus_1.16.2-3_aarch64.deb",
                "1b6d5e349708414acbbb1404210e32d4e3f390890d02e162639dec1016a8657b",
            ),
            "libiconv": (
                "pool/main/libi/libiconv/libiconv_1.19.1_aarch64.deb",
                "a1c6323eff4f660e16ae6f5832356444b3269c19a4f61146355a49e7c4be5ed1",
            ),
            "libandroid-execinfo": (
                "pool/main/liba/libandroid-execinfo/libandroid-execinfo_0.1-3_aarch64.deb",
                "725dd2c6da7fc96e860fcc928e18aa9fb0e85e0bdcaf4f8ce0f0654ca6860fc2",
            ),
            "libsndfile": (
                "pool/main/libs/libsndfile/libsndfile_1.2.2-3_aarch64.deb",
                "1e1fb77b14ec26f3ff6ded069e9ec816ab7535ae5d074122c6727b0f59d8aff3",
            ),
            "libsoxr": (
                "pool/main/libs/libsoxr/libsoxr_0.1.3-8_aarch64.deb",
                "a1c5f66aae3b9900e9a492b43901b2b98586870c7905feb9f3c835cc9af464be",
            ),
            "speexdsp": (
                "pool/main/s/speexdsp/speexdsp_1.2.1-1_aarch64.deb",
                "21cd5d122a8d24dffb9b2926dff7059f8f42cde7c5a91f27ea5c9b4f40356be0",
            ),
            "libflac": (
                "pool/main/libf/libflac/libflac_1.5.0-1_aarch64.deb",
                "d1d6fcac6fd6d15c36f34464cb01d5e2140e321d8448dfc396cd7eb1536b1f6c",
            ),
            "libvorbis": (
                "pool/main/libv/libvorbis/libvorbis_1.3.7-4_aarch64.deb",
                "6bfd70c4b570b85594bd06116b75a6f8109ec58cbc123e938b630a6eefdedf4e",
            ),
            "libopus": (
                "pool/main/libo/libopus/libopus_1.6.1_aarch64.deb",
                "005a9335ce0ec0f510bbe6e0229c901d6f920cc375fcda56461e96cef70f8ff0",
            ),
            "libogg": (
                "pool/main/libo/libogg/libogg_1.3.6-1_aarch64.deb",
                "4f1700a532f251ad3600f44f88cd764f1f6b0542d3343391117944b47a92802d",
            ),
            "libmpg123": (
                "pool/main/libm/libmpg123/libmpg123_1.33.7_aarch64.deb",
                "883b104faae53820b2e758363300ccf99e28f627a263d766af61ae07b73b07b3",
            ),
            "libmp3lame": (
                "pool/main/libm/libmp3lame/libmp3lame_4.0-1_aarch64.deb",
                "59f70ad8885578063bcbea3b11e74fb69e2416ca036b47aa255c1fa4f074565e",
            ),
        },
    },
    "x86_64": {
        "jni": "x86_64",
        "platform": "x86_64",
        "packages": {
            "pulseaudio": (
                "pool/main/p/pulseaudio/pulseaudio_17.0-5_x86_64.deb",
                "1930e52ba1c15b9489eebf54dadea1719cbd0c41d9cbd51eacd575c1527ac058",
            ),
            "libltdl": (
                "pool/main/libl/libltdl/libltdl_2.6.2_x86_64.deb",
                "9a71bef5c3ba9da2a90ec6dfa0fd99e1802cb03cc3ec37059340c6c7b7f441fd",
            ),
            "dbus": (
                "pool/main/d/dbus/dbus_1.16.2-3_x86_64.deb",
                "7860940419ff89270227063267f7aab3e3b7a91789359d9296190e50a361aff7",
            ),
            "libiconv": (
                "pool/main/libi/libiconv/libiconv_1.19.1_x86_64.deb",
                "3eb0c454676ad24d26c79601721b2eb3f9485c611ad0179fb86b17229344f46d",
            ),
            "libandroid-execinfo": (
                "pool/main/liba/libandroid-execinfo/libandroid-execinfo_0.1-3_x86_64.deb",
                "348582b47b4b6dec8c13147437d8bd93d029239bc95f30635074cad08efb6220",
            ),
            "libsndfile": (
                "pool/main/libs/libsndfile/libsndfile_1.2.2-3_x86_64.deb",
                "5c2a37ce7703dc05fc1eb014ced672e4783eae7929983c3d4298a3b1eb500361",
            ),
            "libsoxr": (
                "pool/main/libs/libsoxr/libsoxr_0.1.3-8_x86_64.deb",
                "3cd66761119a4f4cb621a701279c2b2edc9a6c4e9f1872dbfc8058fb76c6a66f",
            ),
            "speexdsp": (
                "pool/main/s/speexdsp/speexdsp_1.2.1-1_x86_64.deb",
                "9d8b3656fb666b524cd46ef6c37b3323033e7398400746fc09945dc004fb0e7f",
            ),
            "libflac": (
                "pool/main/libf/libflac/libflac_1.5.0-1_x86_64.deb",
                "2f07360bfa8c876eeb73cd566c4c0bde19345645dcae4fbc6db14cc12301c6e3",
            ),
            "libvorbis": (
                "pool/main/libv/libvorbis/libvorbis_1.3.7-4_x86_64.deb",
                "9515c03de58faa17e2e19deb78da09289c90b939c17fcbaf4b171aebfefb65bf",
            ),
            "libopus": (
                "pool/main/libo/libopus/libopus_1.6.1_x86_64.deb",
                "724f0215e78a21a02f8dd01dd6c78d6cea71457c8080be99f984f5d8c8f5e4d9",
            ),
            "libogg": (
                "pool/main/libo/libogg/libogg_1.3.6-1_x86_64.deb",
                "55dd0908feb56bec69fdf1c0aaeedb73f6c74cc28495c0d640172845863c9eed",
            ),
            "libmpg123": (
                "pool/main/libm/libmpg123/libmpg123_1.33.7_x86_64.deb",
                "d39a982b5080b1a01f3d21707d4de72ea6ce13ab795548fa307bafdb4c4c0323",
            ),
            "libmp3lame": (
                "pool/main/libm/libmp3lame/libmp3lame_4.0-1_x86_64.deb",
                "1599ab4003ae944c648d5bd7a9b00001bf4ef34a2dde6cf8c23b7ea58a2174a5",
            ),
        },
    },
}

# Provided by the Flet runtime / Android — never shipped here. libaaudio and
# libOpenSLES are the platform audio APIs the sink/source modules link.
_EXTERNAL_SONAMES = {"libc++_shared.so", "libaaudio.so", "libOpenSLES.so"}


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
            url = f"{_POOL}/{rel}"
            print(f"  fetching {rel} …")
            blob = _fetch(url)
            got = hashlib.sha256(blob).hexdigest()
            if got != sha:
                raise SystemExit(f"{rel}: sha256 mismatch\n  expected {sha}\n  got      {got}")
            extracted[pkg] = _deb_payloads(blob)

        entries: dict[str, bytes] = {}

        resolved: dict[str, tuple[str, bytes]] = {}
        for wanted, (pkg, explicit) in _ELF_PAYLOADS.items():
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

        for pkg, src_prefix, dest_prefix in _DATA_PAYLOADS:
            members = {k: v for k, v in extracted[pkg].items() if k.startswith(src_prefix)}
            if not members:
                raise SystemExit(f"{pkg}: no files under {src_prefix}")
            for name, blob in sorted(members.items()):
                entries[f"{dest_prefix}{name[len(src_prefix) :]}"] = blob

        entries[f"{DIST_NAME}/__init__.py"] = (
            '"""PulseAudio native payload for Flet Android apps (Termux repackage)."""\n'
            f"PA_VERSION = {PA_VERSION!r}\n"
            f"LIBS = {sorted(resolved)!r}\n"
        ).encode()
        entries[f"{DIST_NAME}/_sources.py"] = (
            "# Generated by build_flet_pulseaudio_wheel.py — do not edit.\n"
            f"PA_VERSION = {PA_VERSION!r}\n"
            f"ARCH = {arch!r}\n"
            f"SOURCES = {spec['packages']!r}\n"
        ).encode()

        dist_info = f"{DIST_NAME}-{PA_VERSION}.dist-info"
        lic = Path(__file__).resolve().parent.parent / "LICENSES"
        license_files = sorted(lic.glob("*.txt"))
        metadata = [
            "Metadata-Version: 2.1",
            f"Name: {DIST_NAME}",
            f"Version: {PA_VERSION}",
            "Summary: PulseAudio (Android audio modules) native payload for Flet Android apps",
            "Requires-Python: >=3.10",
            "License: GPL-2.0-or-later",
        ]
        metadata.extend(f"License-File: {lf.name}" for lf in license_files)
        entries[f"{dist_info}/METADATA"] = ("\n".join(metadata) + "\n").encode()
        entries[f"{dist_info}/WHEEL"] = (
            "Wheel-Version: 1.0\n"
            "Generator: kiri-flet-pulseaudio-wheel-builder\n"
            "Root-Is-Purelib: false\n"
            f"Tag: {tag}\n"
        ).encode()
        for lf in license_files:
            entries[f"{dist_info}/{lf.name}"] = lf.read_bytes()
        entries[f"{dist_info}/THIRD-PARTY.md"] = (
            "# flet-pulseaudio — third-party components\n\n"
            "Repackages verbatim binaries from the Termux apt repository "
            "(architectures aarch64/x86_64), pinned and sha256-verified at build time. "
            "Termux's PulseAudio carries the Android audio modules "
            "(module-aaudio-sink, module-sles-sink, module-sles-source).\n\n"
            "| Component | Version | License |\n|---|---|---|\n"
            "| PulseAudio | 17.0 | GPL-2.0-or-later |\n"
            "| libltdl / libdbus-1 / libiconv / libsndfile / libsoxr / speexdsp | — | LGPL-2.1+/GPL-2.0+ |\n"
            "| libandroid-execinfo | 0.1 | Apache-2.0 |\n"
            "| libwebrtc-audio-processing | 2.1 | BSD-3-Clause |\n\n"
            "Source offer: see the companion app's LICENSES/ + THIRD-PARTY-SOURCES.md "
            "(github.com/Nwokike/proot-distro) and the upstream projects above.\n"
        ).encode()

        lines = []
        for name, blob in entries.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).rstrip(b"=").decode()
            lines.append(f"{name},sha256={digest},{len(blob)}")
        lines.append(f"{dist_info}/RECORD,,")
        entries[f"{dist_info}/RECORD"] = ("\n".join(lines) + "\n").encode()

        wheel_name = f"{DIST_NAME}-{PA_VERSION}-{BUILD_TAG}-{tag}.whl"
        wheel_path = out_dir / wheel_name
        with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, blob in sorted(entries.items()):
                zf.writestr(name, blob)

        print(f"  wrote {wheel_path.name} ({wheel_path.stat().st_size / 1e6:.1f} MB)")
        wheel_paths.append(wheel_path)

    print(f"\nOK: {len(wheel_paths)} PulseAudio wheel(s) written to {out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
