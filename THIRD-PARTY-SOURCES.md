# Third-Party Sources — proot-distro v1.2.0 (Build 4)

This application incorporates third-party software components licensed under free and
open-source software licenses, including the GNU General Public License (GPL).

## Source Code Written Offer (GPL-2.0 §3(b) / GPL-3.0 §6(b))

The complete machine-readable Corresponding Source for the GPL-licensed components
(PRoot, TigerVNC's Xvnc, PulseAudio, QEMU, talloc and friends) and for this application
is available at:
https://github.com/Nwokike/proot-distro/tree/v1.2.0/
and via GitHub Releases at: https://github.com/Nwokike/proot-distro/releases/latest

This offer is valid for at least three (3) years from the date of release to any third
party for no charge other than the cost of physically performing source distribution.
To request source code via durable physical medium, contact: contact@nwokike.ng

## Native Payloads (Packaged in flet-proot)

The proot binaries are repackaged verbatim from the Termux repository with 16 KiB
PT_LOAD segment alignment, verified at build time:

| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |
|---|---|---|---|---|---|
| `proot` (aarch64) | 5.1.107.102 | GPL-2.0-or-later | [proot](https://github.com/termux/proot) | [proot_5.1.107.102_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/proot/proot_5.1.107.102_aarch64.deb) | `10a394b585c2fc2b2c8502544f4e5f1be581dc8bfff79e8ba62f16207423e030` |
| `proot` (x86_64) | 5.1.107.102 | GPL-2.0-or-later | [proot](https://github.com/termux/proot) | [proot_5.1.107.102_x86_64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/proot/proot_5.1.107.102_x86_64.deb) | `2497064226c15971be8131c7facead94a06c225347796326a383c832dca57758` |
| `libtalloc` (aarch64) | 2.5.0 | GPL-3.0-or-later | [libtalloc](https://talloc.samba.org) | [libtalloc_2.5.0_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libt/libtalloc/libtalloc_2.5.0_aarch64.deb) | `556591f43bb773ad8777e1a29522640866a55f95dab71914418b94a8c58ad5a7` |
| `libtalloc` (x86_64) | 2.5.0 | GPL-3.0-or-later | [libtalloc](https://talloc.samba.org) | [libtalloc_2.5.0_x86_64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libt/libtalloc/libtalloc_2.5.0_x86_64.deb) | `b8c6d95f20075dc1f9ec6573575b2444e8d526e48e0d8d6d5cf4e071e6e06530` |
| `libandroid-shmem` (aarch64) | 0.7 | BSD-3-Clause | [libandroid-shmem](https://github.com/termux/libandroid-shmem) | [libandroid-shmem_0.7_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/liba/libandroid-shmem/libandroid-shmem_0.7_aarch64.deb) | `0da3a24d558b93c92bcf8d611e0826a99ff96e396b148e6cdf33b47c47c57ff6` |
| `libandroid-shmem` (x86_64) | 0.7 | BSD-3-Clause | [libandroid-shmem](https://github.com/termux/libandroid-shmem) | [libandroid-shmem_0.7_x86_64.deb](https://packages.termux.dev/apt/termux-main/pool/main/liba/libandroid-shmem/libandroid-shmem_0.7_x86_64.deb) | `ffa9e4c87467b158b148d0ff92dda796aa038276c2075af3269cdcdb06f25797` |

## Native Payloads (Packaged in flet-xvnc)

Xvnc (TigerVNC's X server + VNC server in one process) and its runtime
closure, repackaged verbatim from the Termux repositories:

| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |
|---|---|---|---|---|---|
| `tigervnc` | 1.16.2-1 | GPL-2.0-or-later | [tigervnc](https://tigervnc.org) | [pool/main/t/tigervnc/tigervnc_1.16.2-1_aarch64.deb](https://packages.termux.dev/apt/termux-x11/pool/main/t/tigervnc/tigervnc_1.16.2-1_aarch64.deb) | `3d844963554f7b5b76527312329e8834ff060d6e3512b750044b79de21aa3e11` |
| `xorg-xkbcomp` | 1.5.0 | MIT | [xorg-xkbcomp](https://gitlab.freedesktop.org/xorg/app/xkbcomp) | [pool/main/x/xorg-xkbcomp/xorg-xkbcomp_1.5.0_aarch64.deb](https://packages.termux.dev/apt/termux-x11/pool/main/x/xorg-xkbcomp/xorg-xkbcomp_1.5.0_aarch64.deb) | `ee52d69758a8fcebc2d7f0bd1805a300f18a3472d43fc2eb45867463448cb4a9` |
| `openssl` | 1:3.6.5 | Apache-2.0 | [openssl](https://www.openssl.org) | [pool/main/o/openssl/openssl_1:3.6.5_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/o/openssl/openssl_1:3.6.5_aarch64.deb) | `a2fb7856875e63ef6b90442752e05974813372c3ca86d2513a78ea43c67a0f8b` |
| `libjpeg-turbo` | 3.2.1 | BSD-3-Clause | [libjpeg-turbo](https://libjpeg-turbo.org) | [pool/main/libj/libjpeg-turbo/libjpeg-turbo_3.2.1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libj/libjpeg-turbo/libjpeg-turbo_3.2.1_aarch64.deb) | `3e46721f2fbb10d5f53a45b99e2549d18a34ca3751aa4b704b3404fcdea5f8e7` |
| `libgnutls` | 3.8.13-1 | LGPL-2.1-or-later | [libgnutls](https://www.gnutls.org) | [pool/main/libg/libgnutls/libgnutls_3.8.13-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libg/libgnutls/libgnutls_3.8.13-1_aarch64.deb) | `eb12f2cf82923caf288edd99bc4c19a9dd0cf1de4a03855ff4457a1bbdae146d` |
| `libnettle` | 4.0+really3.10.2 | LGPL-2.1-or-later | [libnettle](https://www.lysator.liu.se/~nisse/nettle) | [pool/main/libn/libnettle/libnettle_4.0+really3.10.2_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libn/libnettle/libnettle_4.0+really3.10.2_aarch64.deb) | `f2d2a84083e66beab642e88496eb16976ccdb12d1278466e687f01431db8a5fb` |
| `libgmp` | 6.3.0-2 | LGPL-3.0-or-later | [libgmp](https://gmplib.org) | [pool/main/libg/libgmp/libgmp_6.3.0-2_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libg/libgmp/libgmp_6.3.0-2_aarch64.deb) | `5a3c1325638946ca212ddcb89bffb2c4459b4c90757d6e69f820e176534037fa` |
| `zlib` | 1.4 | Zlib | [zlib](https://packages.termux.com) | [pool/main/z/zlib/zlib_1.4_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/z/zlib/zlib_1.4_aarch64.deb) | `e3027565ae50bcd8ba5113c988b589754ae192c9cc3e6afbe3e4ed7c06b2598e` |
| `libpixman` | 0.46.4-1 | MIT | [libpixman](https://packages.termux.com) | [pool/main/libp/libpixman/libpixman_0.46.4-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libp/libpixman/libpixman_0.46.4-1_aarch64.deb) | `364b8c82ff68f8513930e5d413459fb7c52eccc7ba75a97a8c5a38760eee8d33` |
| `libxfont2` | 2.0.9 | MIT | [libxfont2](https://gitlab.freedesktop.org/xorg/lib/libxfont2) | [pool/main/libx/libxfont2/libxfont2_2.0.9_aarch64.deb](https://packages.termux.dev/apt/termux-x11/pool/main/libx/libxfont2/libxfont2_2.0.9_aarch64.deb) | `1bd623392cff4dc3fda461e31e9b5f98e7fdf5f51ad9199d2dcdf8feb3e615e2` |
| `libxau` | 1.0.12-2 | MIT | [libxau](https://packages.termux.com) | [pool/main/libx/libxau/libxau_1.0.12-2_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libx/libxau/libxau_1.0.12-2_aarch64.deb) | `2d86bed61ce89dd8fdb55e565aede10155f2ce3adaccb61d5f1375aec3314083` |
| `libxdmcp` | 1.1.5-2 | MIT | [libxdmcp](https://packages.termux.com) | [pool/main/libx/libxdmcp/libxdmcp_1.1.5-2_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libx/libxdmcp/libxdmcp_1.1.5-2_aarch64.deb) | `caea0cf5c0028af0840774094b8900ef7afffd8f9bbd7b1abfbe66851f0d6077` |
| `libxshmfence` | 1.3.3-1 | MIT | [libxshmfence](https://packages.termux.com) | [pool/main/libx/libxshmfence/libxshmfence_1.3.3-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libx/libxshmfence/libxshmfence_1.3.3-1_aarch64.deb) | `7644c2969c2ce4d763785bd2a85eb32ccf8e5ad40228cd92b193f7edb6398d92` |
| `libglvnd` | 1.7.0-1 | MIT | [libglvnd](https://gitlab.freedesktop.org/glvnd/libglvnd) | [pool/main/libg/libglvnd/libglvnd_1.7.0-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libg/libglvnd/libglvnd_1.7.0-1_aarch64.deb) | `67f3fd247e4279a7fceddbd2929f8b53e87c255edfc9c07d0dee7df5fe243d2c` |
| `libxkbfile` | 1.2.0 | MIT | [libxkbfile](https://packages.termux.com) | [pool/main/libx/libxkbfile/libxkbfile_1.2.0_aarch64.deb](https://packages.termux.dev/apt/termux-x11/pool/main/libx/libxkbfile/libxkbfile_1.2.0_aarch64.deb) | `2456caefcf93f5821f6c7c753eae50ea015864c948e678f3c8e2aec9c3c3dbd5` |
| `xkeyboard-config` | 2.49 | MIT | [xkeyboard-config](https://gitlab.freedesktop.org/xkeyboard-config/xkeyboard-config) | [pool/main/x/xkeyboard-config/xkeyboard-config_2.49_all.deb](https://packages.termux.dev/apt/termux-x11/pool/main/x/xkeyboard-config/xkeyboard-config_2.49_all.deb) | `9523dbe04fd7fba2218451813041872957dca459d86dfed9c23a3b247e8fa371` |
| `libx11` | 1.8.14 | MIT | [libx11](https://gitlab.freedesktop.org/xorg/lib/libx11) | [pool/main/libx/libx11/libx11_1.8.14_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libx/libx11/libx11_1.8.14_aarch64.deb) | `c5206ee9cc26a63985d110b57bc24f23c7c97505e6100c4d6a8547a1aeed5532` |
| `libxcb` | 1.17.0-1 | MIT | [libxcb](https://gitlab.freedesktop.org/xorg/lib/libxcb) | [pool/main/libx/libxcb/libxcb_1.17.0-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libx/libxcb/libxcb_1.17.0-1_aarch64.deb) | `191c3642b6a8c754bc75b69b94a81858ecb5f18766dc085aff55559b8087ad34` |
| `libandroid-support` | 29-1 | Apache-2.0 | [libandroid-support](https://packages.termux.com) | [pool/main/liba/libandroid-support/libandroid-support_29-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/liba/libandroid-support/libandroid-support_29-1_aarch64.deb) | `f2f145d6135ad4843ac9670153be3e3944dc1e6f1736d46d2306c28f2b86f517` |
| `zstd` | 1.5.7-1 | BSD-3-Clause | [zstd](https://github.com/facebook/zstd) | [pool/main/z/zstd/zstd_1.5.7-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/z/zstd/zstd_1.5.7-1_aarch64.deb) | `e1b4a5113648da8de189620ba1fce74c48b2d0833d9043391b9a1c91fb606fd3` |
| `p11-kit` | 0.26.6 | BSD-3-Clause | [p11-kit](https://packages.termux.com) | [pool/main/p/p11-kit/p11-kit_0.26.6_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/p11-kit/p11-kit_0.26.6_aarch64.deb) | `e6a305edbfcf6a907bd1f09bedbcbbb06ca7784116300bd297a769c971595424` |
| `libidn2` | 2.3.8-1 | GPL-2.0-or-later / LGPL-3.0-or-later | [libidn2](https://packages.termux.com) | [pool/main/libi/libidn2/libidn2_2.3.8-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libi/libidn2/libidn2_2.3.8-1_aarch64.deb) | `a450a1ba25759ebf78738484a3efee316c51a1fe7bafb0b01a68e2c058a91020` |
| `libunistring` | 1.5 | MIT OR LGPL-3.0-or-later | [libunistring](https://packages.termux.com) | [pool/main/libu/libunistring/libunistring_1.5_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libu/libunistring/libunistring_1.5_aarch64.deb) | `8853ca1421d6472046a0683d53084b26db1caa50a3aa2bf6422a1276c7dba69b` |
| `libtasn1` | 4.21.0 | LGPL-2.1-or-later | [libtasn1](https://packages.termux.com) | [pool/main/libt/libtasn1/libtasn1_4.21.0_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libt/libtasn1/libtasn1_4.21.0_aarch64.deb) | `1d02de3a7e5ef4ff7d893597091176b8ddf135f1ddfacff951f76c18711a7342` |
| `libffi` | 3.8.0 | MIT | [libffi](https://packages.termux.com) | [pool/main/libf/libffi/libffi_3.8.0_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libf/libffi/libffi_3.8.0_aarch64.deb) | `4f255badf74cd31f6a2801c17fa1444199c84c834b517b7c843e2fe9ebe91d77` |
| `libiconv` | 1.19.1 | LGPL-2.1-or-later | [libiconv](https://packages.termux.com) | [pool/main/libi/libiconv/libiconv_1.19.1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libi/libiconv/libiconv_1.19.1_aarch64.deb) | `a1c6323eff4f660e16ae6f5832356444b3269c19a4f61146355a49e7c4be5ed1` |
| `libfontenc` | 1.1.9 | MIT | [libfontenc](https://packages.termux.com) | [pool/main/libf/libfontenc/libfontenc_1.1.9_aarch64.deb](https://packages.termux.dev/apt/termux-x11/pool/main/libf/libfontenc/libfontenc_1.1.9_aarch64.deb) | `2ce4c69bdfb7a81ea2ab1605e983a7a31302c4f0dcc4b7fab9885c34c2c3bb1c` |
| `freetype` | 2.15.0 | FTL / GPL-2.0-or-later | [freetype](https://freetype.org) | [pool/main/f/freetype/freetype_2.15.0_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/f/freetype/freetype_2.15.0_aarch64.deb) | `fe217807b22aa40029874eb1d9e01b89a01b5f1e4f0556c4de9c8e83c4db4256` |
| `libpng` | 1.6.59 | Libpng | [libpng](http://www.libpng.org) | [pool/main/libp/libpng/libpng_1.6.59_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libp/libpng/libpng_1.6.59_aarch64.deb) | `32d61f0b1a60cf7283aa3a80e288737493df2c6b84c8c749606b77c94a10f2b2` |
| `brotli` | 1.2.1 | MIT | [brotli](https://packages.termux.com) | [pool/main/b/brotli/brotli_1.2.1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/b/brotli/brotli_1.2.1_aarch64.deb) | `4fba29438b2b44f8470d52173b4548e938542dc2fc632f8699be5a284cbb9485` |
| `libbz2` | 1.0.8-8 | BSD-4-Clause | [libbz2](https://packages.termux.com) | [pool/main/libb/libbz2/libbz2_1.0.8-8_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libb/libbz2/libbz2_1.0.8-8_aarch64.deb) | `4335d7f060650b0aabef545d1334c2f9f280223d5962e13c24a00ec934b794ba` |
| `libc++` | 30 | Open Source | [libc++](https://packages.termux.com) | [pool/main/libc/libc++/libc++_30_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libc/libc++/libc++_30_aarch64.deb) | `53d0b84a7ba7459024257cb94d5b136fe13ef858567f65a8064b35950799f2ca` |

## Native Payloads (Packaged in flet-pulseaudio)

PulseAudio with Termux's Android audio modules (AAudio sink, OpenSL ES
sink/source, native-protocol-tcp) and its runtime closure:

| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |
|---|---|---|---|---|---|
| `pulseaudio` | 17.0-5 | GPL-2.0-or-later | [pulseaudio](https://www.freedesktop.org/wiki/Software/PulseAudio) | [pool/main/p/pulseaudio/pulseaudio_17.0-5_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/pulseaudio/pulseaudio_17.0-5_aarch64.deb) | `4e110e32007fee5aaf67cfa2f35ae67c11ed53f45da857d0def426e2ca66f8c8` |
| `libltdl` | 2.6.2 | LGPL-2.1-or-later | [libltdl](https://packages.termux.com) | [pool/main/libl/libltdl/libltdl_2.6.2_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libl/libltdl/libltdl_2.6.2_aarch64.deb) | `7b4643fe9d0ab42c0c3c8a1018640816bdb43d422f2268a5e4ea80675624f539` |
| `dbus` | 1.16.2-3 | GPL-2.0-or-later / AFL-2.1 | [dbus](https://www.freedesktop.org/wiki/Software/dbus) | [pool/main/d/dbus/dbus_1.16.2-3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/d/dbus/dbus_1.16.2-3_aarch64.deb) | `1b6d5e349708414acbbb1404210e32d4e3f390890d02e162639dec1016a8657b` |
| `libiconv` | 1.19.1 | LGPL-2.1-or-later | [libiconv](https://packages.termux.com) | [pool/main/libi/libiconv/libiconv_1.19.1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libi/libiconv/libiconv_1.19.1_aarch64.deb) | `a1c6323eff4f660e16ae6f5832356444b3269c19a4f61146355a49e7c4be5ed1` |
| `libandroid-execinfo` | 0.1-3 | BSD-2-Clause | [libandroid-execinfo](https://packages.termux.com) | [pool/main/liba/libandroid-execinfo/libandroid-execinfo_0.1-3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/liba/libandroid-execinfo/libandroid-execinfo_0.1-3_aarch64.deb) | `725dd2c6da7fc96e860fcc928e18aa9fb0e85e0bdcaf4f8ce0f0654ca6860fc2` |
| `libsndfile` | 1.2.2-3 | LGPL-2.1-or-later | [libsndfile](https://libsndfile.github.io/libsndfile) | [pool/main/libs/libsndfile/libsndfile_1.2.2-3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libs/libsndfile/libsndfile_1.2.2-3_aarch64.deb) | `1e1fb77b14ec26f3ff6ded069e9ec816ab7535ae5d074122c6727b0f59d8aff3` |
| `libsoxr` | 0.1.3-8 | LGPL-2.1-or-later | [libsoxr](https://sourceforge.net/projects/soxr) | [pool/main/libs/libsoxr/libsoxr_0.1.3-8_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libs/libsoxr/libsoxr_0.1.3-8_aarch64.deb) | `a1c5f66aae3b9900e9a492b43901b2b98586870c7905feb9f3c835cc9af464be` |
| `speexdsp` | 1.2.1-1 | BSD-3-Clause | [speexdsp](https://gitlab.xiph.org/xiph/speexdsp) | [pool/main/s/speexdsp/speexdsp_1.2.1-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/s/speexdsp/speexdsp_1.2.1-1_aarch64.deb) | `21cd5d122a8d24dffb9b2926dff7059f8f42cde7c5a91f27ea5c9b4f40356be0` |
| `libflac` | 1.5.0-1 | BSD-3-Clause | [libflac](https://packages.termux.com) | [pool/main/libf/libflac/libflac_1.5.0-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libf/libflac/libflac_1.5.0-1_aarch64.deb) | `d1d6fcac6fd6d15c36f34464cb01d5e2140e321d8448dfc396cd7eb1536b1f6c` |
| `libvorbis` | 1.3.7-4 | BSD-3-Clause | [libvorbis](https://packages.termux.com) | [pool/main/libv/libvorbis/libvorbis_1.3.7-4_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libv/libvorbis/libvorbis_1.3.7-4_aarch64.deb) | `6bfd70c4b570b85594bd06116b75a6f8109ec58cbc123e938b630a6eefdedf4e` |
| `libopus` | 1.6.1 | BSD-3-Clause | [libopus](https://opus-codec.org) | [pool/main/libo/libopus/libopus_1.6.1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libo/libopus/libopus_1.6.1_aarch64.deb) | `005a9335ce0ec0f510bbe6e0229c901d6f920cc375fcda56461e96cef70f8ff0` |
| `libogg` | 1.3.6-1 | BSD-3-Clause | [libogg](https://packages.termux.com) | [pool/main/libo/libogg/libogg_1.3.6-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libo/libogg/libogg_1.3.6-1_aarch64.deb) | `4f1700a532f251ad3600f44f88cd764f1f6b0542d3343391117944b47a92802d` |
| `libmpg123` | 1.33.7 | LGPL-2.1-or-later | [libmpg123](https://packages.termux.com) | [pool/main/libm/libmpg123/libmpg123_1.33.7_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libm/libmpg123/libmpg123_1.33.7_aarch64.deb) | `883b104faae53820b2e758363300ccf99e28f627a263d766af61ae07b73b07b3` |
| `libmp3lame` | 4.0-1 | LGPL-2.0-or-later | [libmp3lame](https://packages.termux.com) | [pool/main/libm/libmp3lame/libmp3lame_4.0-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libm/libmp3lame/libmp3lame_4.0-1_aarch64.deb) | `59f70ad8885578063bcbea3b11e74fb69e2416ca036b47aa255c1fa4f074565e` |

## Native Payloads (Packaged in flet-qemu)

QEMU user-mode emulators (all four non-host architectures) and the extra
runtime closure they need beyond flet-xvnc/flet-proot. QEMU is GPL-2.0; the
written offer above covers it:

| Package | Version | License | Upstream Source | Termux Pool URL | SHA-256 |
|---|---|---|---|---|---|
| `glib` | 2.90.1 | LGPL-2.1-or-later | [glib](https://github.com/termux/termux-packages) | [glib_2.90.1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/g/glib/glib_2.90.1_aarch64.deb) | `132d8ce961d96a7252fd4bc2228bddd385b1b17b706a46caae6d541ae0e4b2c0` |
| `pcre2` | 10.49 | BSD-3-Clause | [pcre2](https://github.com/termux/termux-packages) | [pcre2_10.49_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/p/pcre2/pcre2_10.49_aarch64.deb) | `c27995e5f52b8ecc9b8b3e662eb08e49f82a18bfd3f34343936acc7b23964724` |
| `libdw` | 0.197 | GPL-2.0-or-later / LGPL-3.0-or-later | [libdw](https://github.com/termux/termux-packages) | [libdw_0.197_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libd/libdw/libdw_0.197_aarch64.deb) | `6c25c05cbba67671238434306ca5e55444d29c9b425600a710618a189d4f9ebb` |
| `libelf` | 0.197 | GPL-2.0-or-later / LGPL-3.0-or-later | [libelf](https://github.com/termux/termux-packages) | [libelf_0.197_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libe/libelf/libelf_0.197_aarch64.deb) | `c47ee2eee8450274f22218307b31471b76113b2825d3c69a5fdc47180cd68c13` |
| `liblzma` | 5.8.4 | 0BSD / LGPL-2.1-or-later | [liblzma](https://github.com/termux/termux-packages) | [liblzma_5.8.4_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/libl/liblzma/liblzma_5.8.4_aarch64.deb) | `44e95e6e60dddb3705e60a344a4f009a1085a210797342b721eaff41b44033c0` |
| `argp` | 1.5.0-1 | GPL-2.0-or-later | [argp](https://github.com/termux/termux-packages) | [argp_1.5.0-1_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/a/argp/argp_1.5.0-1_aarch64.deb) | `4096bfb8cba379efc3699e94e1cee400e72c274d734b5c1ed5f274ec42003405` |
| `json-c` | 0.19 | MIT | [json-c](https://github.com/termux/termux-packages) | [json-c_0.19_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/j/json-c/json-c_0.19_aarch64.deb) | `894fef1e1001807e862f909cd5645dbb51bc77434779124f69178efe13690655` |
| `qemu-user-aarch64` | 1:11.1.3 | GPL-2.0-or-later | [qemu](https://www.qemu.org) | [qemu-user-aarch64_1:11.1.3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/q/qemu-user-aarch64/qemu-user-aarch64_1%3A11.1.3_aarch64.deb) | `90808036f9a350a96e15e7af03d817a97be7ccc2df1070ff7b29171948da072d` |
| `qemu-user-arm` | 1:11.1.3 | GPL-2.0-or-later | [qemu](https://www.qemu.org) | [qemu-user-arm_1:11.1.3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/q/qemu-user-arm/qemu-user-arm_1%3A11.1.3_aarch64.deb) | `f8f707de1c77cda50f29f95759319064af0f2b1339a27d4597b260a3f4b7384f` |
| `qemu-user-i386` | 1:11.1.3 | GPL-2.0-or-later | [qemu](https://www.qemu.org) | [qemu-user-i386_1:11.1.3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/q/qemu-user-i386/qemu-user-i386_1%3A11.1.3_aarch64.deb) | `09224ac69c2fc08a63594bc4b109361d2b1367a466af0b950dfe54caef0030a8` |
| `qemu-user-riscv64` | 1:11.1.3 | GPL-2.0-or-later | [qemu](https://www.qemu.org) | [qemu-user-riscv64_1:11.1.3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/q/qemu-user-riscv64/qemu-user-riscv64_1%3A11.1.3_aarch64.deb) | `a7c7efc9c0104dd46a48adeeaa42d55e8c4a183df45af47f6945b60eb971a7dd` |
| `qemu-user-x86-64` | 1:11.1.3 | GPL-2.0-or-later | [qemu](https://www.qemu.org) | [qemu-user-x86-64_1:11.1.3_aarch64.deb](https://packages.termux.dev/apt/termux-main/pool/main/q/qemu-user-x86-64/qemu-user-x86-64_1%3A11.1.3_aarch64.deb) | `0ab9a9b0b1587c344eea1873cb2dd8c0d63f227fc5e5c3d4271adf9cb43e913f` |

## Vendored Assets

| Asset | Version | License | Upstream |
|---|---|---|---|
| `noVNC` (vnc.html + app/ + core/ + vendor/, vendored verbatim and served by the display stream server) | 1.7.0 | MPL-2.0 | https://github.com/novnc/noVNC |

## Python Dependencies

| Package | License | Upstream |
|---|---|---|
| `proot-distro` | GPL-3.0-only | https://github.com/termux/proot-distro |
| `flet` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-ads` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-terminal` | MIT | https://github.com/Nwokike/flet-terminal |
| `flet-notifications` | Apache-2.0 | https://github.com/flet-dev/flet |
| `flet-webview` | Apache-2.0 | https://github.com/flet-dev/flet |
| `aiohttp` (display stream server) | Apache-2.0 | https://github.com/aio-libs/aiohttp |
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

