#!/usr/bin/env python3
"""Generate THIRD-PARTY-SOURCES.md with exact provenance and source offer."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from build_flet_proot_wheel import _PINNED_SOURCES

from core.constants import (
    APP_BUILD_NUMBER,
    APP_VERSION,
    GITHUB_RELEASES_URL,
    REPO_NAME,
    REPO_OWNER,
)

OUTPUT_FILE = REPO_ROOT / "THIRD-PARTY-SOURCES.md"


def generate_markdown() -> str:
    packages = _PINNED_SOURCES["packages"]
    pool_root = _PINNED_SOURCES["pool_root"]

    lines = [
        f"# Third-Party Sources — {REPO_NAME} v{APP_VERSION} (Build {APP_BUILD_NUMBER})",
        "",
        "This application incorporates third-party software components licensed under free and",
        "open-source software licenses, including the GNU General Public License (GPL).",
        "",
        "## Source Code Written Offer (GPL-2.0 §3(b) / GPL-3.0 §6(b))",
        "",
        "The complete machine-readable Corresponding Source for the GPL-licensed components",
        "and for this application is available at:",
        f"https://github.com/{REPO_OWNER}/{REPO_NAME}/tree/v{APP_VERSION}/",
        f"and via GitHub Releases at: {GITHUB_RELEASES_URL}",
        "",
        "This offer is valid for at least three (3) years from the date of release to any third",
        "party for no charge other than the cost of physically performing source distribution.",
        f"To request source code via durable physical medium, contact: contact@{REPO_OWNER.lower()}.ng",
        "",
        "## Native Payloads (Packaged in flet-proot)",
        "",
        "The native binaries are repackaged verbatim from the Termux repository with 16 KiB",
        "PT_LOAD segment alignment, verified at build time:",
        "",
        "| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |",
        "|---|---|---|---|---|---|",
    ]

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
        [
            "",
            "## Python Dependencies",
            "",
            "| Package | License | Upstream |",
            "|---|---|---|",
            "| `proot-distro` | GPL-3.0-only | https://github.com/termux/proot-distro |",
            "| `flet` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-ads` | Apache-2.0 | https://github.com/flet-dev/flet |",
            "| `flet-terminal` | MIT | https://github.com/Nwokike/flet-terminal |",
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
