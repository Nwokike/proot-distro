# Third-Party Sources — proot-distro v1.0.0 (Build 1)

This application incorporates third-party software components licensed under free and
open-source software licenses, including the GNU General Public License (GPL).

## Source Code Written Offer (GPL-2.0 §3(b) / GPL-3.0 §6(b))

The complete machine-readable Corresponding Source for the GPL-licensed components
and for this application is available at:
https://github.com/Nwokike/proot-distro/tree/v1.0.0/
and via GitHub Releases at: https://github.com/Nwokike/proot-distro/releases/latest

This offer is valid for at least three (3) years from the date of release to any third
party for no charge other than the cost of physically performing source distribution.
To request source code via durable physical medium, contact: contact@nwokike.ng

## Native Payloads (Packaged in flet-proot)

The native binaries are repackaged verbatim from the Termux repository with 16 KiB
PT_LOAD segment alignment, verified at build time:

| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |
|---|---|---|---|---|---|
| `proot` (aarch64) | 5.1.107.98 | GPL-2.0-or-later | [proot](https://github.com/termux/proot) | [proot_5.1.107.98_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/proot/proot_5.1.107.98_aarch64.deb) | `29de40efea4daa2a6168b617915206511c63e8d46bf5f4b07d48723441ef7f3b` |
| `proot` (x86_64) | 5.1.107.98 | GPL-2.0-or-later | [proot](https://github.com/termux/proot) | [proot_5.1.107.98_x86_64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/proot/proot_5.1.107.98_x86_64.deb) | `1c31ad7e1046f4d418fef19b6dfaa9a14801d2047ade6ad0375b3f5501e3e227` |
| `libtalloc` (aarch64) | 2.5.0 | GPL-3.0-or-later | [libtalloc](https://talloc.samba.org) | [libtalloc_2.5.0_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libt/libtalloc/libtalloc_2.5.0_aarch64.deb) | `556591f43bb773ad8777e1a29522640866a55f95dab71914418b94a8c58ad5a7` |
| `libtalloc` (x86_64) | 2.5.0 | GPL-3.0-or-later | [libtalloc](https://talloc.samba.org) | [libtalloc_2.5.0_x86_64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libt/libtalloc/libtalloc_2.5.0_x86_64.deb) | `b8c6d95f20075dc1f9ec6573575b2444e8d526e48e0d8d6d5cf4e071e6e06530` |
| `libandroid-shmem` (aarch64) | 0.7 | BSD-3-Clause | [libandroid-shmem](https://github.com/termux/libandroid-shmem) | [libandroid-shmem_0.7_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/liba/libandroid-shmem/libandroid-shmem_0.7_aarch64.deb) | `0da3a24d558b93c92bcf8d611e0826a99ff96e396b148e6cdf33b47c47c57ff6` |
| `libandroid-shmem` (x86_64) | 0.7 | BSD-3-Clause | [libandroid-shmem](https://github.com/termux/libandroid-shmem) | [libandroid-shmem_0.7_x86_64.deb](https://packages.termux.dev/apt/termux-main/pool/main/liba/libandroid-shmem/libandroid-shmem_0.7_x86_64.deb) | `ffa9e4c87467b158b148d0ff92dda796aa038276c2075af3269cdcdb06f25797` |

## Python Dependencies

| Package | License | Upstream |
|---|---|---|
| `proot-distro` | GPL-3.0-only | https://github.com/termux/proot-distro |
| `flet` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-ads` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-terminal` | MIT | https://github.com/Nwokike/flet-terminal |
| `httpx` | BSD-3-Clause | https://github.com/encode/httpx |
| `httpcore` | BSD-3-Clause | https://github.com/encode/httpcore |
| `h11` | MIT | https://github.com/python-hyper/h11 |
| `anyio` | MIT | https://github.com/agronholm/anyio |
| `msgpack` | Apache-2.0 | https://github.com/msgpack/msgpack-python |
| `certifi` | MPL-2.0 | https://github.com/certifi/python-certifi |
| `idna` | BSD-3-Clause | https://github.com/kjd/idna |
| `typing-extensions` | PSF-2.0 | https://github.com/python/typing_extensions |
| `six` | MIT | https://github.com/benjaminp/six |
| `repath` | MIT | https://github.com/nickstenning/repath |

## License Texts

Complete license texts for all included software components are provided in the
`LICENSES/` directory and within the app under Settings → About → Open-source licenses.

