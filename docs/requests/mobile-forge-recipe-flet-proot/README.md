# mobile-forge recipe bundle — `flet-proot` (prepared, not yet submitted)

Status: **prepared 2026-10-16** in response to keeping flet-dev/flet discussions
[#6979](https://github.com/flet-dev/flet/discussions/6979) alive. The app ships
its own-CI platform-tagged wheels today (see `tools/build_flet_proot_wheel.py`);
this directory is the candidate `recipes/flet-proot/` submission for
[`flet-dev/mobile-forge`](https://github.com/flet-dev/mobile-forge) if the
maintainers want it.

## Files

| File | Notes |
|---|---|
| `meta.yaml` | Minimal recipe metadata. Field set mirrors the fields visibly used by `recipes/flet-libffmpeg/meta.yaml` (version set-block, `name`, `build.number`, `license`). The full schema lives in the forge's `meta-schema.yaml` — **re-check against it before opening the PR**. |
| `build.sh` | Repack build: downloads the pinned Termux `.deb`s (proot 5.1.107.101, libtalloc 2.5.0, libandroid-shmem 0.7), verifies sha256, extracts, and stages the payload at `opt/lib/*.so` (the layout `copyOpt_<abi>` consumes). **UNVERIFIED against the forge build environment** — whether `$SRC_DIR`/`$PREFIX` conventions and network access match what a forge `build.sh` is given has not been checked (no forge build has been run). |
| `test.py` | Target-installation sanity test (manifest + payload presence + 16 KiB PT_LOAD alignment). |
| `licenses/` | Full canonical texts: GPL-2.0 (proot + loader), GPL-3.0 (libtalloc), BSD-3-Clause (libandroid-shmem). |

## The open question for maintainers

Is a `build.sh` that **downloads and sha256-verifies pinned Termux `.deb`s** and
repacks their ELF payloads acceptable for the forge, or must recipes build from
source inside the forge environment? The repack path is what the consuming app
already ships and device-verifies; a from-source build would need the
termux-packages cross toolchain (not the NDK flow `flet-libffmpeg` uses).

Precedent for the output shape: `flet-libffmpeg-8.1.2-1-py3-none-android_24_arm64_v8a.whl`
(per-ABI android-tagged wheels carrying `opt/lib` payloads).

## Local provenance (source of truth for the PR's content)

`tools/flet_proot_sources.json` (repo root) pins every deb with a sha256;
`tools/build_flet_proot_wheel.py` is the reference implementation this
`build.sh` is a port of.
