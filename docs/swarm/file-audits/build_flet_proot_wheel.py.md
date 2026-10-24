# build_flet_proot_wheel.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** build_flet_proot_wheel.py (502 lines), docs/requests/mobile-forge-recipe-flet-proot/{meta.yaml,build.sh,README.md,test.py,licenses/*}, pyproject.toml, .github/workflows/app.yml · Date: 2026-10-24

## What it does / how the app uses it

Stdlib-only CLI that downloads pinned Termux .deb payloads (proot 5.1.107.98, libtalloc 2.5.0, libandroid-shmem 0.7 for aarch64/x86_64), sha256-verifies each, extracts ELF shared objects from the ar data.tar, asserts 16 KiB PT_LOAD alignment, and emits per-arch flet-proot wheels (opt/lib/*.so payloads + dist-info METADATA/WHEEL/RECORD + the three license texts). The apk and aab CI jobs run `uv run python build_flet_proot_wheel.py --out wheels` and consume the output via PIP_FIND_LINKS (.github/workflows/app.yml:50, :123). pyproject.toml pins the same wheel as `flet-proot==5.1.107.98` ([tool.flet.android] dependencies). The mobile-forge directory is a drifted, prepared-but-not-submitted recipe port pinning proot 5.1.107.96.

## Findings

### F1 · P0 · Build is broken in the current tree: LICENSES/ vendored texts are deleted, and the license check runs after the full download
- **Where:** build_flet_proot_wheel.py:24 (`LICENSE_DIR = REPO_ROOT / "LICENSES"`), :330-334 (`_license_text` raises SystemExit when a license file is missing), :396-398 (the three `_license_text` calls inside `build_wheel`), :494 (`download_sources` runs first inside the per-arch loop at :491-495).
- **What:** Every wheel build reads LICENSES/GPL-2.0.txt, LICENSES/GPL-3.0.txt, LICENSES/BSD-3-Clause.txt; `git status --short` shows all of them deleted (`D LICENSES/GPL-2.0.txt`, `D LICENSES/GPL-3.0.txt`, `D LICENSES/BSD-3-Clause.txt`). The build downloads every deb (network I/O, sha256-verified) and only then fails at :333 with "missing vendored license text". License-existence is not fail-fast.
- **Evidence:** `git status --short`: `D LICENSES/GPL-2.0.txt`, `D LICENSES/GPL-3.0.txt`, `D LICENSES/BSD-3-Clause.txt`; build_flet_proot_wheel.py:24, :330-334, :396-398, :494.
- **Fix / opportunity:** Restore LICENSES/* and move the license-existence checks ahead of `download_sources` so the build fails fast before any network I/O.
- **Risk if ignored:** CI apk/aab wheel-build steps fail; no APK/AAB produced (P0 build break), and bandwidth is wasted on every failed attempt.

### F2 · P1 · Version pin drift: recipe pins proot 5.1.107.96; builder and pyproject pin 5.1.107.98
- **Where:** pyproject.toml `[tool.flet.android] dependencies = ["flet-proot==5.1.107.98"]`; build_flet_proot_wheel.py:40 (`"version": "5.1.107.98"`); docs/requests/mobile-forge-recipe-flet-proot/meta.yaml:1 (`version = "5.1.107.96"`); build.sh:35 (`"ver": "5.1.107.96"`). Sha256s also diverge: recipe build.sh:37-38 (`8199dca...`, `77ea45...`) vs builder :44 (`29de40ef...`), :48 (`1c31ad7e...`).
- **What:** Three sources disagree on the proot pin. The recipe is "prepared, NOT submitted" (README.md:1) and unused by CI, but if opened as a forge PR it would build different binaries than the CI wheel set (comment :31-32 attributes the 96→98 bump to Termux dropping 96 from the pool after a CI 404).
- **Evidence:** pyproject.toml dependency line; build_flet_proot_wheel.py:40-44, :48; meta.yaml:1; build.sh:35, :37-38; README.md:1.
- **Fix / opportunity:** Align meta.yaml/build.sh to 5.1.107.98 with the builder sha256s, or withdraw the recipe; add a CI consistency check for flet-proot pins (the app.yml release-identity step at :66-88 checks app versions only).
- **Risk if ignored:** Recipe PR ships untested, divergent payloads; silent binary mismatch between forge and CI wheels.

### F3 · P2 · No download retry/backoff; one transient network failure fails the whole build
- **Where:** build_flet_proot_wheel.py:196-199 (`_fetch`: single `urlopen`, timeout=120 only), :202-210 (`_fetch_verified`: hash checked after the full download, no retry on mismatch), :491-496 (arch loop aborts on the first `SystemExit`).
- **What:** Comment :31-32 documents a Termux pool 404 that forced the 96→98 bump, yet the code has no retry, backoff, or fallback mirror. One flaky HTTP request aborts all arches.
- **Evidence:** build_flet_proot_wheel.py:196-199, :202-210, :31-32.
- **Fix / opportunity:** Add bounded retries with backoff in `_fetch` (urllib has none built in), keeping sha256 as the acceptance gate.
- **Risk if ignored:** CI build flakiness on transient network errors; no auto-recovery.

### F4 · P2 · Wheel METADATA under-declares licenses
- **Where:** build_flet_proot_wheel.py:399-412 (METADATA carries a single "License: GPL-2.0-or-later" at :407), :409-410 (ships LICENSE.libtalloc and LICENSE.libandroid-shmem), PAYLOAD_LICENSES :189-193 (talloc = GPL-3.0, shmem = BSD-3-Clause); docs/requests/mobile-forge-recipe-flet-proot/meta.yaml:11 (`license: GPL-2.0-or-later` only).
- **What:** METADATA's License field names only GPL-2.0-or-later while the wheel ships GPL-3.0 (talloc) and BSD-3-Clause (shmem) binaries; the recipe makes the same single-license under-declaration.
- **Evidence:** build_flet_proot_wheel.py:407, :409-410, :189-193; meta.yaml:11.
- **Fix / opportunity:** Drop the single "License:" line (rely on the License-File entries at :408-411 which already cover all three) or list all three licenses.
- **Risk if ignored:** Incomplete copyleft attribution; license-compliance audit findings.

### F5 · P3 · unmet_needed hardcodes libc prefixes instead of SYSTEM_SONAMES; "optional" shmem skip can still fail late
- **Where:** build_flet_proot_wheel.py:94-101 (`SYSTEM_SONAMES` includes liblog.so, libandroid.so, libz.so), :170-178 (`unmet_needed` hardcodes `("libc.", "libdl.", "libm.")` prefixes and never consults SYSTEM_SONAMES), :314-316 (libandroid-shmem skipped with a WARNING if `pick_lib` fails).
- **What:** SYSTEM_SONAMES is declared but unused by the dependency check; shmem is "optional" yet a missing needed lib only surfaces through the same missing-need `SystemExit` after other payloads passed.
- **Evidence:** build_flet_proot_wheel.py:94-101, :170-178, :314-316.
- **Fix / opportunity:** Rewrite `unmet_needed` to check `SYSTEM_SONAMES` ∪ shipped set; decide explicitly whether libandroid-shmem is required.
- **Risk if ignored:** Platform-dependency changes (e.g. libz newly needed) pass the build check incorrectly, or an optional-skip yields an incomplete wheel detected late.

### F6 · P3 · Recipe's claimed local-provenance file does not exist
- **Where:** docs/requests/mobile-forge-recipe-flet-proot/README.md:32-34 (`tools/flet_proot_sources.json` "pins every deb with a sha256"); build.sh:31 ("Mirror of tools/flet_proot_sources.json").
- **What:** `tools/` and `tools/flet_proot_sources.json` are absent at repo root; the provenance claim is UNVERIFIED and the referenced file is missing.
- **Evidence:** `ls tools` → "No such file or directory"; root listing contains no tools/.
- **Fix / opportunity:** Create the sources-json mirror or remove the reference before submitting the recipe PR.
- **Risk if ignored:** Recipe submission references nonexistent files; reviewers cannot verify pins.

## Missed capabilities (dependency audits only)

N/A — build tool audit, not a dependency audit.

## Verified-good list

- sha256 verification gates every deb before extraction: build_flet_proot_wheel.py:202-210; mismatch aborts with expected vs actual.
- 16 KiB PT_LOAD alignment enforced per payload: :91 (`ALIGN_16K = 0x4000`), :278-282 (`SystemExit` if `align < 0x4000`); PT_LOAD offset/vaddr congruence checked at :131-135.
- Exit codes: `main()` returns 0 (:498); failure paths raise `SystemExit` (exit 1); argparse misuse exits 2 (:466-502); CI treats non-zero as step failure (app.yml wheel-build steps).
- Wheel metadata structure is standards-conformant: METADATA 2.1, WHEEL (Root-Is-Purelib: false, per-arch android tag), RECORD with base64url sha256 + size (:399-429).
- Builder and pyproject agree on flet-proot==5.1.107.98 (:40 vs pyproject android dependency).
- Stdlib-only, forward-slash zip entries, `pathlib` paths — portable in principle between Linux and Windows (UNVERIFIED on Windows; CI runs ubuntu-latest only: app.yml apk/aab jobs).

## Unverified

- sha256 pins match the live Termux pool (no network fetch attempted; pins for proot 5.1.107.98 UNVERIFIED against upstream).
- Actual ELF alignment of the pinned debs (script not executed in this session).
- Windows execution (CI only runs ubuntu-latest; app.yml apk/aab jobs).
- Recipe acceptability in mobile-forge (README.md:15 explicitly UNVERIFIED against the forge build environment).
- LICENSES/ absence is proven via git status (deleted), not unverified; check_elf_alignment.py (used by the workflow alignment step) is also deleted in the working tree — out of scope for this one-file audit.
