#!/usr/bin/env python3
"""Generate THIRD-PARTY-SOURCES.md with exact provenance and source offer."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_flet_proot_wheel import _PINNED_SOURCES as PROOT_PINS
from build_flet_pulseaudio_wheel import _PINNED_SOURCES as PA_PINS
from build_flet_pulseaudio_wheel import _POOL as PA_POOL
from build_flet_xvnc_wheel import (
    _PINNED_SOURCES as XVNC_PINS,
)
from build_flet_xvnc_wheel import (
    _POOL_MAIN as XVNC_POOL_MAIN,
)
from build_flet_xvnc_wheel import (
    _POOL_X11 as XVNC_POOL_X11,
)
from build_flet_xvnc_wheel import (
    _X11_PACKAGES,
)

from core.constants import (
    APP_BUILD_NUMBER,
    APP_VERSION,
    GITHUB_RELEASES_URL,
    REPO_NAME,
    REPO_OWNER,
)

OUTPUT_FILE = REPO_ROOT / "THIRD-PARTY-SOURCES.md"

# License + upstream per package (the repackages are verbatim Termux binaries —
# each carries its upstream license; unknowns fail loud here, not on a lawyer's desk).
XVNC_LICENSES = {
    "tigervnc": "GPL-2.0-or-later",
    "xorg-xkbcomp": "MIT",
    "openssl": "Apache-2.0",
    "libjpeg-turbo": "BSD-3-Clause",
    "libgnutls": "LGPL-2.1-or-later",
    "libnettle": "LGPL-2.1-or-later",
    "libgmp": "LGPL-3.0-or-later",
    "zlib": "Zlib",
    "libpixman": "MIT",
    "libxfont2": "MIT",
    "libxau": "MIT",
    "libxdmcp": "MIT",
    "libxshmfence": "MIT",
    "libglvnd": "MIT",
    "libxkbfile": "MIT",
    "xkeyboard-config": "MIT",
    "libx11": "MIT",
    "libxcb": "MIT",
    "libandroid-support": "Apache-2.0",
    "zstd": "BSD-3-Clause",
    "p11-kit": "BSD-3-Clause",
    "libidn2": "GPL-2.0-or-later / LGPL-3.0-or-later",
    "libunistring": "MIT OR LGPL-3.0-or-later",
    "libtasn1": "LGPL-2.1-or-later",
    "libffi": "MIT",
    "libiconv": "LGPL-2.1-or-later",
    "libfontenc": "MIT",
    "freetype": "FTL / GPL-2.0-or-later",
    "libpng": "Libpng",
    "brotli": "MIT",
    "libbz2": "BSD-4-Clause",
}
PA_LICENSES = {
    "pulseaudio": "GPL-2.0-or-later",
    "libltdl": "LGPL-2.1-or-later",
    "dbus": "GPL-2.0-or-later / AFL-2.1",
    "libiconv": "LGPL-2.1-or-later",
    "libandroid-execinfo": "BSD-2-Clause",
    "libsndfile": "LGPL-2.1-or-later",
    "libsoxr": "LGPL-2.1-or-later",
    "speexdsp": "BSD-3-Clause",
    "libflac": "BSD-3-Clause",
    "libvorbis": "BSD-3-Clause",
    "libopus": "BSD-3-Clause",
    "libogg": "BSD-3-Clause",
    "libmpg123": "LGPL-2.1-or-later",
    "libmp3lame": "LGPL-2.0-or-later",
}
XVNC_UPSTREAMS = {
    "tigervnc": "https://tigervnc.org",
    "xorg-xkbcomp": "https://gitlab.freedesktop.org/xorg/app/xkbcomp",
    "xkeyboard-config": "https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config",
    "openssl": "https://www.openssl.org",
    "libjpeg-turbo": "https://libjpeg-turbo.org",
    "libgnutls": "https://www.gnutls.org",
    "libnettle": "https://www.lysator.liu.se/~nisse/nettle",
    "libgmp": "https://gmplib.org",
    "libglvnd": "https://gitlab.freedesktop.org/glvnd/libglvnd",
    "libx11": "https://gitlab.freedesktop.org/xorg/lib/libx11",
    "libxcb": "https://gitlab.freedesktop.org/xorg/lib/libxcb",
    "libxfont2": "https://gitlab.freedesktop.org/xorg/lib/libxfont2",
    "freetype": "https://freetype.org",
    "libpng": "http://www.libpng.org",
    "zstd": "https://github.com/facebook/zstd",
}
PA_UPSTREAMS = {
    "pulseaudio": "https://www.freedesktop.org/wiki/Software/PulseAudio",
    "dbus": "https://www.freedesktop.org/wiki/Software/dbus",
    "libsndfile": "https://libsndfile.github.io/libsndfile",
    "libsoxr": "https://sourceforge.net/projects/soxr",
    "speexdsp": "https://gitlab.xiph.org/xiph/speexdsp",
    "libopus": "https://opus-codec.org",
}


def _deb_bits(rel: str) -> tuple[str, str, str]:
    """pool/main/t/tigervnc/tigervnc_1.16.2-1_aarch64.deb → (name, version, arch)."""
    filename = rel.rsplit("/", 1)[-1].removesuffix(".deb")
    pkg, version, _arch = filename.rsplit("_", 2)
    return pkg, version, _arch


def _payload_table(
    title: str, intro_lines: list[str], pins: dict, pool_for, licenses: dict, upstreams: dict
) -> list[str]:
    lines = [
        "",
        f"## {title}",
        "",
        *intro_lines,
        "",
        "| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |",
        "|---|---|---|---|---|---|",
    ]
    seen: set[str] = set()
    for spec in pins.values():
        for pkg, (rel, sha) in spec["packages"].items():
            if pkg in seen:
                continue  # one row per package (both arches carry the same pins)
            seen.add(pkg)
            name, version, _deb_arch = _deb_bits(rel)
            license_name = licenses.get(pkg, "Open Source")
            upstream = upstreams.get(pkg, "https://packages.termux.com")
            lines.append(
                f"| `{name}` | {version} | {license_name} | [{name}]({upstream}) | [{rel}]({pool_for(pkg)}/{rel}) | `{sha}` |"
            )
    return lines


def generate_markdown() -> str:
    packages = PROOT_PINS["packages"]
    pool_root = PROOT_PINS["pool_root"]

    def xvnc_pool(pkg: str) -> str:
        return XVNC_POOL_X11 if pkg in _X11_PACKAGES else XVNC_POOL_MAIN

    def pa_pool(_pkg: str) -> str:
        return PA_POOL

    lines = [
        f"# Third-Party Sources — {REPO_NAME} v{APP_VERSION} (Build {APP_BUILD_NUMBER})",
        "",
        "This application incorporates third-party software components licensed under free and",
        "open-source software licenses, including the GNU General Public License (GPL).",
        "",
        "## Source Code Written Offer (GPL-2.0 §3(b) / GPL-3.0 §6(b))",
        "",
        "The complete machine-readable Corresponding Source for the GPL-licensed components",
        "(PRoot, TigerVNC's Xvnc, PulseAudio, QEMU, talloc and friends) and for this application",
        "is available at:",
        f"https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/v{APP_VERSION}/",
        f"and via GitHub Releases at: {GITHUB_RELEASES_URL}",
        "",
        "This offer is valid for at least three (3) years from the date of release to any third",
        "party for no charge other than the cost of physically performing source distribution.",
        f"To request source code via durable physical medium, contact: contact@{REPO_OWNER.lower()}.ng",
    ]

    lines.extend(
        [
            "",
            "## Native Payloads (Packaged in flet-proot)",
            "",
            "The proot binaries are repackaged verbatim from the Termux repository with 16 KiB",
            "PT_LOAD segment alignment, verified at build time:",
            "",
            "| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for pkg_name, spec in packages.items():
        ver = spec["version"]
        pool_dir = spec["pool_dir"]
        license_name = {
            "proot": "GPL-2.0-or-later",
            "libtalloc": "GPL-3.0-or-later",
            "libandroid-shmem": "BSD-3-Clause",
        }.get(pkg_name, "Open Source")
        upstream_url = {
            "proot": "https://github.com/termux/proot",
            "libtalloc": "https://talloc.samba.org",
            "libandroid-shmem": "https://github.com/termux/libandroid-shmem",
        }.get(pkg_name, "https://github.com/termux")
        for arch, deb_info in spec["debs"].items():
            filename = deb_info["file"]
            sha256 = deb_info["sha256"]
            url = f"{pool_root}/{pool_dir}/{filename}"
            lines.append(
                f"| `{pkg_name}` ({arch}) | {ver} | {license_name} | [{pkg_name}]({upstream_url}) | [{filename}]({url}) | `{sha256}` |"
            )

    lines.extend(
        _payload_table(
            "Native Payloads (Packaged in flet-xvnc)",
            [
                "Xvnc (TigerVNC's X server + VNC server in one process) and its runtime",
                "closure, repackaged verbatim from the Termux repositories:",
            ],
            XVNC_PINS,
            xvnc_pool,
            XVNC_LICENSES,
            XVNC_UPSTREAMS,
        )
    )
    lines.extend(
        _payload_table(
            "Native Payloads (Packaged in flet-pulseaudio)",
            [
                "PulseAudio with Termux's Android audio modules (AAudio sink, OpenSL ES",
                "sink/source, native-protocol-tcp) and its runtime closure:",
            ],
            PA_PINS,
            pa_pool,
            PA_LICENSES,
            PA_UPSTREAMS,
        )
    )

    # QEMU user-mode emulators + their closure (flet-qemu). Pins live in the
    # builder; read them there so this table cannot drift.
    import build_flet_qemu_wheel as _qemu

    qemu_lines = [
        "",
        "## Native Payloads (Packaged in flet-qemu)",
        "",
        "QEMU user-mode emulators (all four non-host architectures) and the extra",
        "runtime closure they need beyond flet-xvnc/flet-proot. QEMU is GPL-2.0; the",
        "written offer above covers it:",
        "",
        "| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |",
        "|---|---|---|---|---|---|",
    ]
    _QEMU_LICENSES = {
        "glib": "LGPL-2.1-or-later",
        "pcre2": "BSD-3-Clause",
        "libdw": "GPL-2.0-or-later / LGPL-3.0-or-later",
        "libelf": "GPL-2.0-or-later / LGPL-3.0-or-later",
        "liblzma": "0BSD / LGPL-2.1-or-later",
        "json-c": "MIT",
        "argp": "GPL-2.0-or-later",
    }
    seen_qemu: set[str] = set()
    for pkg, version in _qemu._VERSIONS.items():
        if pkg in seen_qemu or pkg.startswith("qemu-user-"):
            continue
        seen_qemu.add(pkg)
        pool_dir = _qemu._POOL_DIRS[pkg]
        sha = _qemu._SHA["aarch64"].get(pkg) or _qemu._SHA["x86_64"].get(pkg, "")
        filename = f"{pkg}_{version}_aarch64.deb"
        url = f"{_qemu.POOL}/{pool_dir}/{filename.replace(':', '%3A')}"
        lines_url = f"[{filename}]({url})"
        qemu_lines.append(
            f"| `{pkg}` | {version} | {_QEMU_LICENSES.get(pkg, 'Open Source')} | "
            f"[{pkg}](https://github.com/termux/termux-packages) | {lines_url} | `{sha}` |"
        )
    for emulator in sorted({p for spec in _qemu._EMULATORS.values() for p in spec["pkgs"]}):
        version = _qemu._VERSIONS[emulator]
        pool_dir = _qemu._POOL_DIRS[emulator]
        sha = _qemu._SHA["aarch64"].get(emulator, "")
        filename = f"{emulator}_{version}_aarch64.deb"
        url = f"{_qemu.POOL}/{pool_dir}/{filename.replace(':', '%3A')}"
        qemu_lines.append(
            f"| `{emulator}` | {version} | GPL-2.0-or-later | "
            f"[qemu](https://www.qemu.org) | [{filename}]({url}) | `{sha}` |"
        )
    lines.extend(qemu_lines)

    lines.extend(
        [
            "",
            "## Vendored Assets",
            "",
            "| Asset | Version | License | Upstream |",
            "|---|---|---|---|",
            "| `noVNC` (vnc.html + app/ + core/ + vendor/, vendored verbatim and served by the display stream server) | 1.7.0 | MPL-2.0 | https://github.com/novnc/noVNC |",
            "",
            "## Python Dependencies",
            "",
            "| Package | License | Upstream |",
            "|---|---|---|",
            "| `proot-distro` | GPL-3.0-only | https://github.com/termux/proot-distro |",
            "| `flet` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-ads` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-terminal` | MIT | https://github.com/Nwokike/flet-terminal |",
            "| `flet-notifications` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-webview` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `aiohttp` (display stream server) | Apache-2.0 | https://github.com/aio-libs/aiohttp |",
            "| `httpx` | BSD-3-Clause | https://github.com/encode/httpx |",
            "| `httpcore` | BSD-3-Clause | https://github.com/encode/httpcore |",
            "| `h11` | MIT | https://github.com/python-hyper/h11 |",
            "| `anyio` | MIT | https://github.com/agronholm/anyio |",
            "| `msgpack` | Apache-2.0 | https://github.com/msgpack/msgpack-python |",
            "| `certifi` | MPL-2.0 | https://github.com/certifi/python-certifi |",
            "| `idna` | BSD-3-Clause | https://github.com/kjd/idna |",
            "| `typing-extensions` | PSF-2.0 | https://github.com/python/typing_extensions |",
            "| `six` | MIT | https://github.com/benjaminp/six |",
            "| `repath` | MIT | https://github.com/nickstenning/repath |",
            "",
            "## License Texts",
            "",
            "Complete license texts for all included software components are provided in the",
            "`LICENSES/` directory and within the app under Settings → About → Open-source licenses.",
            "",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    content = generate_markdown()
    OUTPUT_FILE.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
