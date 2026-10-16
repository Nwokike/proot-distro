# Licensing & compliance reference — proot-distro (Flet Android app)

**Date:** 2026-10-16 · **Status:** reference (M6 input; checklist items land M3/M5/M6)
**Scope:** ONE document. It does not modify code, CI, or any other doc.
**Repo:** `github.com/Nwokike/proot-distro` (public). Local project name stays
`proot-distro-flet` (uv cannot self-depend on `proot-distro`).

**Verification mandate (owner rule):** every legal claim below quotes a PRIMARY
source — the license text itself, an FSF GPL FAQ entry (with URL), an official
trademark-policy page (with URL), Google Play documentation (with URL), or an
upstream repo LICENSE file. Anything that cannot be pinned to a primary source
is labeled **UNVERIFIED — needs counsel** explicitly. This document is a
research reference, not legal advice.

**Primary sources consulted (frozen 2026-10-16):**

| # | Source | URL / location | Retrieved |
|---|---|---|---|
| S1 | proot-distro 5.10.0 wheel LICENSE (GPL-3.0 text) + `License-Expression: GPL-3.0-only` METADATA + `cli.py` source header | `.venv/Lib/site-packages/proot_distro-5.10.0.dist-info/` (installed wheel); upstream `https://github.com/termux/proot-distro` | 2026-10-16 |
| S2 | termux/proot COPYING (GPL-2.0 text) + `src/cli/proot.c` header ("either version 2 … or (at your option) any later version") | `https://raw.githubusercontent.com/termux/proot/master/COPYING`, `…/src/cli/proot.c` | 2026-10-16 |
| S3 | termux-packages `packages/proot/build.sh` (`TERMUX_PKG_LICENSE="GPL-2.0"`, v5.1.107.96, deps `libandroid-shmem, libtalloc`) | `https://github.com/termux/termux-packages` | 2026-10-16 |
| S4 | termux-packages `packages/libtalloc/build.sh` (`TERMUX_PKG_LICENSE="GPL-3.0"`) | `https://github.com/termux/termux-packages` | 2026-10-16 |
| S5 | termux-packages `packages/libandroid-shmem/build.sh` (`TERMUX_PKG_LICENSE="BSD 3-Clause"`) | `https://github.com/termux/termux-packages` | 2026-10-16 |
| S6 | FSF GPL FAQ (MereAggregation, GPLPlugins, GPLAndPlugins, IfInterpreterIsGPL, AggregateContainers, LinkingOverControlledInterface) | `https://www.gnu.org/licenses/gpl-faq.html` (via `https://web.archive.org/web/2024/https://www.gnu.org/licenses/gpl-faq.html` — direct gnu.org blocked from this network) | 2026-10-16 |
| S7 | Apache License 2.0 §4, §6 (from flet upstream LICENSE) | `https://raw.githubusercontent.com/flet-dev/flet/main/LICENSE` | 2026-10-16 |
| S8 | MIT License (flet-terminal upstream LICENSE) | `https://raw.githubusercontent.com/Nwokike/flet-terminal/main/LICENSE` | 2026-10-16 |
| S9 | Canonical IP Rights Policy (Ubuntu trademark rules) | `https://ubuntu.com/legal/intellectual-property-policy` | 2026-10-16 |
| S10 | Debian Trademark Policy v2.0 (2013-01-19) | `https://www.debian.org/trademark` | 2026-10-16 |
| S11 | Kali Linux Trademark Policy | `https://www.kali.org/docs/policy/trademark/` | 2026-10-16 |
| S12 | Google "Include open source notices" (Play services OSS guidance) | `https://developers.google.com/android/guides/opensource` | 2026-10-16 |
| S13 | Google Play Developer Content Policy hub (policy index) | `https://play.google/developer-content-policy/` | 2026-10-16 |
| S14 | Google Play Deceptive Behavior policy (full policy + key considerations quoted from page body) | `https://support.google.com/googleplay/android-developer/answer/9888077` (resolves to `…/answer/17006354`) | 2026-10-16 |
| S15 | BSD-3-Clause, MIT, PSF-2.0, MPL-2.0, LGPL-2.1, BSD-ish texts from installed dist-info license files + `https://www.mozilla.org/en-US/MPL/2.0/` + Flutter LICENSE (`https://raw.githubusercontent.com/flutter/flutter/main/LICENSE`) | `.venv/.../*.dist-info/` | 2026-10-16 |
| S16 | Installed dist-info METADATA `License`/`License-Expression` fields (exact versions below) | `.venv/Lib/site-packages/*.dist-info/METADATA` | 2026-10-16 |

> Note on S6: gnu.org was unreachable from this network (TCP timeouts on 443
> and port 80); the FAQ text was pulled through the Wayback Machine snapshot
> of 2024. The FAQ content is FSF-authored; quotes below are verbatim from
> that snapshot. Re-verify against the live URL before any filing or dispute.

---

## 0. What ships inside the APK (scope of this document)

Three payload classes:

1. **Native GPL payload (M2 `flet-proot` wheel → `jniLibs`):**
   `libproot.so` (termux/proot v5.1.107.96), `libproot-loader.so` (the
   unbundled loader, `PROOT_UNBUNDLE_LOADER`), `libtalloc.so.2`
   (Samba talloc 2.5.0), `libandroid-shmem.so` (Termux shmem emulation 0.7).
2. **Python payload (Flet serious_python bundle):** `flet`, `flet-ads`,
   `flet-terminal`, `proot-distro`, plus the transitive runtime set
   (`httpx`, `httpcore`, `h11`, `anyio`, `idna`, `certifi`,
   `typing-extensions` on some interpreters, `msgpack`, `oauthlib`,
   `repath`, and `six` via `repath`/`python-dateutil` chains).
   Plus the Flutter/Dart client compiled at build time (BSD-style) and
   AdMob (`google_mobile_ads`, Apache-2.0).
3. **NOT shipped:** distro rootfs images (pulled at runtime from Docker Hub
   into app-private storage; optionally one bundled rootfs — see §4.1), and
   every dev-only package (cookiecutter tree incl. `chardet`, `flet-cli`,
   `flet-desktop`, pytest, ruff — build-host only, none in the APK).

The copyleft load-bearing items are class 1 + `proot-distro` (Python). Every
permissive item needs only notice preservation (§1, column "How WE satisfy
it"). The GPL items need the full source-offer machinery (§3) and the
derivative-work decision (§2).

---

## 1. Component license inventory

Legend — **Obligation** = what the license text requires of someone who
redistributes the component in binary/object form. **How WE satisfy it** = the
concrete mechanism in this repo (file, screen, or CI step; owners in §6).

### 1a. Native binaries SHIPPED in the APK (via the M2 `flet-proot` wheel)

| Component (version · upstream) | License (primary source) | Obligation summary (quoted) | How WE satisfy it |
|---|---|---|---|
| `libproot.so` — termux/proot **v5.1.107.96** (`github.com/termux/proot`) | **GPL-2.0** (termux-packages `packages/proot/build.sh`: `TERMUX_PKG_LICENSE="GPL-2.0"` [S3]; COPYING is the GPL-2.0 text, "Version 2, June 1991" [S2]). **"Or later" allowed:** `src/cli/proot.c` header says "either version 2 of the License, or (at your option) any later version" [S2] | GPL-2.0 §3: distribute object code only if you "also do one of the following: a) Accompany it with the complete corresponding machine-readable source code … or, b) Accompany it with a written offer, valid for at least three years … or, c) Accompany it with the information you received as to the offer" (noncommercial only) [S2]. GPL-2.0 §2(b): any distributed work "in whole or in part contains or is derived from the Program" must be "licensed as a whole at no charge … under the terms of this License" [S2] | §3.2 written-offer route (6b-equivalent via GPL-2.0 §3(b)); in-app licenses screen lists proot + offer link; source points at termux/proot @ v5.1.107.96 + our build recipe pin (M2 version-tracking policy, roadmap §M2). Derivative question: §2 |
| `libproot-loader.so` — the proot loader, unbundled (`PROOT_UNBUNDLE_LOADER=$TERMUX_PREFIX/libexec/proot` [S3]) | **GPL-2.0**, same Program as proot (it is built from the same source tree; the unbundling is a build-layout choice, not a separate work — see build.sh excerpt [S3]) | Same as `libproot.so` (same corresponding source) | Same offer covers it; screen entry names the loader explicitly so users can find it |
| `libtalloc.so` — Samba talloc **2.5.0** (`talloc.samba.org`) | **GPL-3.0** (termux-packages `packages/libtalloc/build.sh`: `TERMUX_PKG_LICENSE="GPL-3.0"` [S4]) | GPL-3.0 §6 (non-source forms): convey object code only if you also convey "machine-readable Corresponding Source … in one of these ways" — (a) source on durable medium with product, (b) written offer valid ≥3 years, (d) equivalent network access "through the same place at no further charge" [S1-wheel GPL-3.0 text]. GPL-3.0 §5(c): "You must license the entire work, as a whole, under this License" [S1] | §3.1 route §6(d) (network source via our public repo + upstream links) or §6(b) written offer — pick ONE per release and state it on the screen; screen entry names talloc + version + source link |
| `libandroid-shmem.so` — Termux libandroid-shmem **0.7** (`github.com/termux/libandroid-shmem`) | **BSD 3-Clause** (termux-packages `packages/libandroid-shmem/build.sh`: `TERMUX_PKG_LICENSE="BSD 3-Clause"` [S5]) | "Redistribution and use in source and binary forms … are permitted provided that … 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution. 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission." (oauthlib copy of the same BSD-3 text, `.venv` [S15]) | In-app licenses screen reproduces the copyright + conditions + disclaimer; no endorsement claims anywhere (store listing, README) |

### 1b. Python packages SHIPPED in the APK (runtime only)

All fields below were read from the installed dist-info METADATA on 2026-10-16
[S16]; license-file heads confirmed on disk [S15]. Versions are the
currently locked ones — re-verify on every bump (checklist item A5).

| Package (locked version) | License (dist-info field) | Obligation summary (quoted from the license text) | How WE satisfy it |
|---|---|---|---|
| `flet` 1.0.4 | **Apache-2.0** (`License-Expression: Apache-2.0` [S16]; text [S7]) | Apache-2.0 §4: give recipients "a copy of this License"; "cause any modified files to carry prominent notices stating that You changed the files"; "retain … all copyright, patent, trademark, and attribution notices"; if a NOTICE file exists, include "a readable copy of the attribution notices" in the Derivative Works [S7]. §6: "This License does not grant permission to use the trade names, trademarks … except as required for reasonable and customary use in describing the origin of the Work" [S7] | Ship `LICENSE` notices file (checklist A1); in-app screen reproduces Apache text + flet copyright; no modification of flet sources (owner no-patching rule); no "Flet" branding as our own (§4.3) |
| `flet-ads` 1.0.4 | **Apache-2.0** (`License-Expression: Apache-2.0`, `License-File: LICENSE` [S16]) | Same Apache-2.0 §4 as above | Same notices file + screen entry |
| `flet-terminal` 0.3.9 | **No license field in wheel METADATA** (only `## License … licensed under the MIT License. See [LICENSE]` in the long description; no `licenses/` dir in the 0.3.9 dist-info — verified on disk [S15]). Upstream repo LICENSE is the **MIT License**, © 2026 Onyeka Nwokike ("Permission is hereby granted, free of charge … to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies … subject to … The above copyright notice and this permission notice shall be included in all copies or substantial portions" [S8]) | MIT condition (upstream text): keep "copyright notice and this permission notice … in all copies or substantial portions" [S8] | In-app screen reproduces the MIT text + © line; **M1 must add `license = "MIT"` + `license-files = ["LICENSE"]` to the flet-terminal pyproject** (roadmap M1 already requires this) so the 0.4.0 wheel carries machine-readable metadata; until then our notices file carries the text manually (checklist A1/A6) |
| `proot-distro` 5.10.0 | **GPL-3.0-only** (`License-Expression: GPL-3.0-only`, `License-File: LICENSE` [S16]; source headers say "either version 3 … or (at your option) any later version" — but the wheel metadata pins **only**, so treat as **GPL-3.0-only** for compliance) | GPL-3.0 §§4–6 as for talloc above, applied to the Python sources (Corresponding Source = the sources themselves: "The Corresponding Source for a work in source code form is that same work" [S1-text §1]). GPL-3.0 §5(c) whole-work rule [S1-text §5] | Source offer covers the exact wheel (PyPI `proot-distro==5.10.0` + `github.com/termux/proot-distro` tag); in-app screen entry; derivative question: §2 (this is the in-process import) |
| `httpx` 0.28.1 | **BSD-3-Clause** (`License: BSD-3-Clause` [S16]; "Copyright © 2019, Encode OSS Ltd." [S15]) | BSD-3 binary condition (reproduce notice + conditions + disclaimer; no endorsement) — same text as §1a shmem row | Notices file + screen |
| `httpcore` 1.0.9 | **BSD-3-Clause** (`License-Expression: BSD-3-Clause` [S16]; © 2020 Encode [S15]) | Same BSD-3 binary condition | Notices file + screen |
| `h11` 0.16.0 | **MIT** (`License: MIT` [S16]; "Copyright (c) 2016 Nathaniel J. Smith" [S15]) | MIT notice preservation [S8-pattern] | Notices file + screen |
| `anyio` 4.15.1 | **MIT** (`License-Expression: MIT` [S16]; "Copyright (c) 2018 Alex Grönholm" [S15]) | MIT notice preservation | Notices file + screen |
| `idna` 3.20 | **BSD-3-Clause** (`License-Expression: BSD-3-Clause` [S16]; "Copyright (c) 2013-2026, Kim Davies and contributors" [S15]) | Same BSD-3 binary condition | Notices file + screen |
| `certifi` 2026.7.22 | **MPL-2.0** (`License: MPL-2.0` [S16]; bundle: "a modified version of ca-bundle.crt … extracted from Mozilla's root certificates" [S15]) | MPL-2.0 §3.2 (Executable Form): "such Covered Software must also be made available in Source Code Form … and You must inform recipients of the Executable Form how they can obtain a copy of such Source Code Form"; §3.3: "You may create and distribute a Larger Work under terms of Your choice, provided that You also comply with the requirements of this License for the Covered Software" [S15]. File-level copyleft only — the rest of the APK may stay under its own terms | Notices file states where the certifi sources live (certifi PyPI sdist / `github.com/certifi/python-certifi`); screen entry (checklist A1) |
| `typing-extensions` 4.16.0 | **PSF-2.0** (`License-Expression: PSF-2.0` [S16]; bundled PSF history text [S15]) | PSF-style attribution retention ("… are retained in … any derivative version prepared by Licensee" [S15]) | Notices file + screen |
| `msgpack` 1.2.3 (desktop lock; Android resolves 1.1.x — obligation identical) | **Apache-2.0** (`License-Expression: Apache-2.0`, "Copyright (C) 2008-2011 INADA Naoki" [S15/S16]) | Same Apache-2.0 §4 as flet | Notices file + screen |
| `oauthlib` 4.0.0 | **BSD-3-Clause** (`License: BSD-3-Clause` [S16]; © The OAuthlib Community [S15]) | Same BSD-3 binary condition | Notices file + screen (note: candidate for `[tool.flet.cleanup]` pruning — roadmap M5; if pruned, drop the row and keep the audit note) |
| `repath` 0.9.0 | **MIT** (`License: MIT` [S16]; "Copyright (c) 2015 Synacor, Inc." [S15]) | MIT notice preservation | Notices file + screen |
| `six` 1.17.0 (via `repath>=six>=1.9.0`; also `python-dateutil→six`, dev chain) | **MIT** (`License: MIT`, `License-File: LICENSE` [S16]) | MIT notice preservation | Notices file + screen |

### 1c. Non-Python payload compiled into the APK at build time

| Component | License (primary source) | Obligation summary | How WE satisfy it |
|---|---|---|---|
| Flutter engine + Dart framework (compiled into every Flet APK by the build template) | **BSD-style** ("Copyright 2014 The Flutter Authors … Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution" — `flutter/flutter` LICENSE [S15]) | Binary-form notice reproduction (same shape as BSD-3, quoted above) | Notices file + screen entry for the Flutter engine |
| `google_mobile_ads` (bundled via `flet-ads` Dart side) | **Apache-2.0** (upstream LICENSE head verified [S15]) | Apache-2.0 §4 (same as flet) | Notices file + screen |
| `xterm.dart` (rendering engine inside `flet-terminal` Dart side) | **MIT** ("Copyright (c) 2020 xuty", upstream LICENSE [S15]) | MIT notice preservation | Notices file + screen |
| serious_python interpreter + stdlib (ships the Python runtime incl. `compression.zstd` question — roadmap parking lot) | **PSF-license family** (same shape as `typing-extensions` row; full text: **UNVERIFIED — needs counsel** to pin the exact file: confirm from the built artifact's license payload in M5) | Attribution retention (pending verification) | Screen entry marked provisional until M5 artifact inspection (checklist A1) |

### 1d. Dev-only / build-host-only — NEVER ships in the APK (no user-facing obligation, listed to prove the negative)

| Package | License | Why it never ships (primary evidence) |
|---|---|---|
| `chardet` 5.2.0 (pulled by `flet-cli→cookiecutter→binaryornot/…`; also `requests` extra) | **LGPL** (`License: LGPL`, classifier "GNU Lesser General Public License v2 or later (LGPLv2+)", text is LGPL-2.1 [S15/S16]) | Build-host only: `flet-cli` runs on the CI host (`flet build apk`), never bundled into the APK (roadmap dep table D1/D3: cookiecutter tree is "Build-host only (none ships to APK); pure-Python throughout (chardet LGPL — do not vendor)"). Chain: `flet-cli Requires-Dist: cookiecutter>=2.6.0`, `binaryornot Requires-Dist: chardet (>=3.0.2)` — verified in METADATA. **Guard:** never add cookiecutter-tree packages to runtime deps; the `test_imports_vs_deps.py` guard (M3 scaffold) must fail the build if `chardet`/`cookiecutter` become importable from `src/` (checklist A4) |
| `flet-cli`, `flet-desktop`, `flet-platform-assets`, `pillow` (host assets), cookiecutter + 18 deps, pytest stack, ruff, watchdog | Mixed permissive (verified per dep studies R/D-series) | Same build-host-only reasoning (roadmap §3 dep table D1–D5); `flet build apk` needs no `flet-desktop`; icons rendered on host |
| `qrcode`, `colorama` | Permissive | "`flet run` device-connect extras, zero build relevance" (roadmap dep table D1) |

---

## 2. The GPL-derivative question (the big one)

### 2.1 The facts (what our app does — roadmap + dep study, no legal gloss)

- `services/proot_service.py` is the **sole importer** of `proot_distro.*`,
  imported **in-process** (lazy import gate, `asyncio.to_thread`,
  plain-data returns). There is no subprocess boundary around the
  `proot-distro` Python API calls (install/list/remove/build paths go through
  in-process functions; only *login* is spawned, because `command_login` ends
  in `os.execvpe`) — `docs/reference/dep-proot-distro.md`, roadmap §M3.
- The app **executes** the GPL binaries `libproot.so` / `libproot-loader.so`
  (spawned as child processes via the login argv) and **ships at runtime**
  `libtalloc.so` (proot's `TERMUX_PKG_DEPENDS` includes libtalloc;
  the loader `mmap`-execs guest binaries — roadmap §M0 gate 3).
- Distribution: the APK on Google Play (and/or GitHub releases) **conveys**
  all of the above inside one installable artifact.

### 2.2 What the FSF says (verbatim quotes — the standard interpretation)

**Q: aggregation vs. modified versions** ([S6], entry `#MereAggregation`):

> "An 'aggregate' consists of a number of separate programs, distributed
> together on the same CD-ROM or other media. The GPL permits you to create
> and distribute an aggregate, even when the licenses of the other software
> are nonfree or GPL-incompatible. The only condition is that you cannot
> release the aggregate under a license that prohibits users from exercising
> rights that each program's individual license would grant them."

> "Where's the line between two separate programs, and one program with two
> parts? This is a legal question, which ultimately judges will decide. We
> believe that a proper criterion depends both on the mechanism of
> communication (exec, pipes, rpc, function calls within a shared address
> space, etc.) and the semantics of the communication (what kinds of
> information are interchanged). … If modules are designed to run linked
> together in a shared address space, that almost surely means combining them
> into one program. By contrast, pipes, sockets and command-line arguments
> are communication mechanisms normally used between two separate programs.
> So when they are used for communication, the modules normally are separate
> programs. But if the semantics of the communication are intimate enough,
> exchanging complex internal data structures, that too could be a basis to
> consider the two parts as combined into a larger program."

**Q: program + plug-ins = single combined program?** ([S6], entry
`#GPLPlugins`):

> "It depends on how the main program invokes its plug-ins. If the main
> program uses fork and exec to invoke plug-ins, and they establish intimate
> communication by sharing complex data structures, or shipping complex data
> structures back and forth, that can make them one single combined program.
> … If the main program dynamically links plug-ins, and they make function
> calls to each other and share data structures, we believe they form a
> single combined program, which must be treated as an extension of both the
> main program and the plug-ins."

**Q: writing a plug-in for a GPL program — license requirements** ([S6],
entry `#GPLAndPlugins`):

> "If the main program and the plugins are a single combined program then
> this means you must license the plug-in under the GPL or a GPL-compatible
> free software license and distribute it with source code in a
> GPL-compliant way. A main program that is separate from its plug-ins makes
> no requirements for the plug-ins."

**Q: GPL interpreter + interpreted programs** ([S6], entry
`#IfInterpreterIsGPL` — the FSF's closest written guidance to a
Python-`import` situation; note it speaks of *interpreters and bindings*,
not of `import` directly):

> "When the interpreter just interprets a language, the answer is no. The
> interpreted program, to the interpreter, is just data … However, when the
> interpreter is extended to provide 'bindings' to other facilities (often,
> but not necessarily, libraries), the interpreted program is effectively
> linked to the facilities it uses through these bindings. So if these
> facilities are released under the GPL, the interpreted program that uses
> them must be released in a GPL-compatible way."

**Containers change nothing** ([S6], entry `#AggregateContainers`):

> "When it comes to determining whether two pieces of software form a single
> work, does the fact that the code is in one or more containers have any
> effect? … No, the analysis of whether they are a single work or an
> aggregate is unchanged by the involvement of containers."

(Equally: shipping the APK as one file, or splitting ABI APKs with
`--split-per-abi`, does not by itself settle the question either way.)

### 2.3 Applying the FSF criteria to OUR architecture (reading, not ruling)

Walk through each GPL component against the quoted tests:

1. **`proot-distro` Python package (GPL-3.0-only), imported in-process.**
   Our code calls its functions in a shared address space ("function calls
   … and share data structures" is the FAQ's own combining criterion
   [S6-#GPLPlugins]). `proot_service.py` passes paths, file descriptors,
   and config structures back and forth and reads its return values
   (the Data Formulator facade still crosses the boundary in-process).
   Under the FSF reading, this is the **strongest combination signal** in
   the whole design — the FAQ's interpreter entry says a program using
   GPL facilities "through these bindings" is "effectively linked" and
   "must be released in a GPL-compatible way" [S6-#IfInterpreterIsGPL].
   Counter-reading (honestly noted): the service owns a *narrow,
   data-only* boundary and never patches upstream; some practitioners argue
   a clean API boundary with no shared internals weakens the claim — but
   **no FSF text supports an API-cleanliness exception**, and the FAQ says
   the line "ultimately judges will decide" [S6-#MereAggregation].
2. **`libproot.so` / loader (GPL-2.0), spawned as child processes.**
   Spawn is via command-line argv (the mechanism the FAQ lists as
   "normally … separate programs" [S6-#MereAggregation]), BUT the
   integration is deep: we construct its environment, bind-mounts, and
   rootfs layout, parse its stderr for install progress, and ship its exact
   binaries inside our APK. Whether that depth crosses into "intimate
   enough" semantics is precisely the judgment call the FAQ reserves to
   courts. Stronger separation (user installs proot separately; app only
   `exec`s an independent binary) would help — that is Option B below.
3. **`libtalloc.so` (GPL-3.0), runtime-linked by proot.**
   We ship it because proot needs it; users get it only inside our APK.
   Same whole-work analysis as (1) if the work is one program; if the work
   is an aggregate, the talloc sources must still be offered (§3).
4. **Distro rootfs images (Ubuntu/Debian/Alpine/Kali userlands).**
   Downloaded at runtime, never shipped (except possibly one bundled
   rootfs — §4.1). Under the FAQ's communication-mechanism test,
   guest programs run *under* proot via exec, and the FAQ's container
   entry keeps the single-work-vs-aggregate analysis unchanged by
   packaging [S6-#AggregateContainers]. The guest userlands' own licenses
   (mostly GPL + permissive, per each distro's archive) travel with the
   images from Docker Hub — we do not relicense them and must not strip
   their `/usr/share/doc/*/copyright` files (checklist item under §4.1).

**The Python-`import` question specifically:** there is **no FSF FAQ entry
about Python `import`** (verified: no `id="Python…"` anchor exists in the
2024 FAQ snapshot [S6]). The community-standard reading (import = linking
into one process = combination when the imported module is GPL) is
widespread practitioner consensus and matches the FAQ's shared-address-space
criterion — but it is *interpretation*, not FSF text. Hence the
UNVERIFIED marking on the options below where they go beyond quoted text.

### 2.4 The three options, honestly presented

**Option A — License the app GPL (GPL-3.0-only recommended, matching
`proot-distro`; or GPL-2.0-or-later to also cover proot's "or later"
grant).**
*What it implies:* publish our `src/` under the GPL, keep the repo public
(already public per D-007), ship full Corresponding Source with every
release (§3), keep AdMob (no license conflict — ads are a service, not a
license term; UMP consent unchanged). The permissive deps stay as-is
(Apache/MIT/BSD are GPL-compatible one-way). Trademark posture unchanged.
*Cost:* copyleft reach extends to any code we combine (our screens, services,
bridges — all ours anyway); the only real cost is strategic (proprietary
relicensing later becomes impossible without contributor agreements) and
the discipline cost (every release needs the source bundle).
*Status:* **This is the only option fully supported by the quoted FSF text
without needing counsel.** Everything else is a risk-managed alternative.

**Option B — Process-separate everything (engineer the combination away).**
*What it implies:* move ALL `proot-distro` usage behind a subprocess/CLI
boundary (the public `pd` CLI contract — roadmap M3 already names this as
the update-safer route: "documented CLI contract may beat internal APIs"),
ship the GPL binaries as a **separately-installable component** (own APK /
own Forge wheel the user installs independently, or a Termux-style
bootstrap the app downloads with consent), communicate only via
argv/stdin/stdout (the FAQ's "normally separate programs" mechanisms
[S6-#MereAggregation]). Then argue aggregate, not combination.
*Cost:* major architecture rework (M0–M4 assume in-process install paths
and stderr capture); UX friction (two installs); the "intimate semantics"
question does not fully vanish (we still orchestrate mounts/env).
*Status:* **UNVERIFIED — needs counsel.** Whether a CLI-only boundary
suffices for THESE facts (shared rootfs layout, env construction, bundled
delivery) is exactly the "judges will decide" zone [S6-#MereAggregation].
Do not claim safety without an opinion letter.

**Option C — Accept community practice (ship, attribute, offer source, stay
small and compliant-looking).**
*What it implies:* keep the in-process architecture, satisfy every
*mechanical* obligation perfectly (notices, source offer, no stripping,
prompt upstream for an exception/clarification), and accept the residual
derivative-work risk on the theory that enforcement follows egregious
violators, not good-faith attributors. Precedent often cited: UserLAnd,
Andronix-style wrappers (all **UNVERIFIED — needs counsel**: their license
posture was NOT examined for this document; do not rely on "others do it").
*Cost:* the §5(c)/§2(b) whole-work exposure remains open indefinitely; any
relicense, acquisition diligence, or Play complaint reopens it.
*Status:* **UNVERIFIED — needs counsel.** This is a risk-acceptance
decision only the owner (not this document) can make, and only with advice.

**Recommendation of this reference (not legal advice):** proceed as if
Option A is the default (keep the repo public, keep sources shippable,
design the licenses screen and source bundle for full GPL compliance from
M3 onward), and put the A-vs-B decision + counsel engagement on the M3
plan-mode agenda — because M3 is where `proot_service.py` (the importer)
is written, and retrofitting a process boundary later costs 10×.
Whichever option is chosen, §3 (source-offer mechanics) is mandatory in
all three worlds: even a pure aggregate must offer the GPL components'
sources.

---

## 3. Source-offer mechanics (what GPL-2.0 and GPL-3.0 require for APKs)

### 3.1 GPL-3.0 components (`proot-distro`, `libtalloc`) — §6 routes

Quoted verbatim (GPL-3.0 §6 [S1-text]):

> "You may convey a covered work in object code form under the terms of
> sections 4 and 5, provided that you also convey the machine-readable
> Corresponding Source under the terms of this License, in one of these
> ways: (a) Convey the object code in, or embodied in, a physical product
> … accompanied by the Corresponding Source fixed on a durable physical
> medium … (b) Convey the object code in, or embodied in, a physical
> product …, accompanied by a written offer, valid for at least three years
> … (d) Convey the object code by offering access from a designated place
> (gratis or for a charge), and offer equivalent access to the Corresponding
> Source in the same way through the same place at no further charge. …
> If the place to copy the object code is a network server, the Corresponding
> Source may be on a different server (operated by you or a third party)
> … provided you maintain clear directions next to the object code saying
> where to find the Corresponding Source."

> "The Corresponding Source for a work in source code form is that same
> work." (§1 [S1-text].)

> "A compilation of a covered work with other separate and independent
> works, which are not by their nature extensions of the covered work, and
> which are not combined with it such as to form a larger program … is
> called an 'aggregate' … Inclusion of a covered work in an aggregate does
> not cause this License to apply to the other parts of the aggregate."
> (§5 [S1-text].)

**Our route: §6(d) network access (primary) + §6(b)-style written offer
text (belt and braces).** Concretely:

- The APK is "offering access from a designated place" (Play listing /
  GitHub release page). We "offer equivalent access to the Corresponding
  Source in the same way through the same place": every release page links
  the source bundle; the in-app licenses screen links it too ("clear
  directions next to the object code" — the screen IS next to the object
  code, on-device).
- Corresponding Source for `proot-distro` = the exact wheel sources
  (`proot-distro==5.10.0` sdist from PyPI + `github.com/termux/proot-distro`
  at the matching tag). Corresponding Source for `libtalloc.so` =
  `termux/termux-packages` recipe @ pinned commit + upstream Samba talloc
  2.5.0 tarball (mirrored or linked). Our own `src/` (Option A world) =
  this repo at the release tag.
- The §6(b) written-offer wording is ALSO carried on the licenses screen
  (valid ≥3 years), so compliance survives even if a court reads our
  layout as a "physical product" distribution rather than §6(d).

**User Product / Installation Information (the anti-tivoization clause):**
§6 requires "Installation Information" only "If you convey an object code
work … in, or with, or specifically for use in, a User Product, and the
conveying occurs as part of a transaction in which the right of possession
and use of the User Product is transferred" [S1-text §6]. A free Play
download to the user's own phone is repo precedent for NOT triggering
installation-info duties — but that reading is **UNVERIFIED — needs
counsel** (it turns on whether a gratis app install counts as the §6
transaction). Mitigation regardless: we do not lock the bootloader, sign
restrictions, or otherwise "retain the ability to install modified object
code" beyond normal Play signing; the GPL binaries live in the app-private
native library dir and any user with `adb`/root can already replace them.
Document this posture in M6; counsel confirms.

### 3.2 GPL-2.0 components (`libproot.so`, loader) — §3 routes

Quoted verbatim (GPL-2.0 §3 [S2]):

> "You may copy and distribute the Program (or a work based on it, under
> Section 2) in object code or executable form under the terms of Sections
> 1 and 2 above provided that you also do one of the following: (a)
> Accompany it with the complete corresponding machine-readable source
> code … or, (b) Accompany it with a written offer, valid for at least
> three years, to give any third party, for a charge no more than your
> cost of physically performing source distribution, a complete
> machine-readable copy of the corresponding source code … or, (c) Accompany
> it with the information you received as to the offer to distribute
> corresponding source code. (This alternative is allowed only for
> noncommercial distribution and only if you received the program in object
> code or executable form with such an offer, in accord with Subsection b
> above.)"

> "If distribution of executable or object code is made by offering access
> to copy from a designated place, then offering equivalent access to copy
> the source code from the same place counts as distribution of the source
> code" (GPL-2.0 §3, final paragraph [S2]).

**Our route: §3(a)-equivalent network source + §3(b) written offer.**
§3(c) is unavailable (our distribution is commercial — AdMob monetization —
so the "only for noncommercial distribution" condition fails [S2]).
Corresponding Source for proot = `github.com/termux/proot` @ v5.1.107.96
tag + the `termux-packages` `packages/proot/build.sh` recipe @ pinned
commit (which records the `PROOT_UNBUNDLE_LOADER` layout and
`PROOT_WITH_LIBANDROID_SHMEM=true` flags [S3]). Note proot's
"or (at your option) any later version" header [S2] means we MAY satisfy
via GPL-3.0 terms instead — but we offer the v2 sources as tagged, which
satisfies either reading.

### 3.3 Exact suggested wording (in-app licenses screen + repo file)

Coordinate with the planned LICENSES screen (roadmap M6: "in-app licenses
screen + source links") and the M5 `LICENSES/` notices file. Suggested text
(adapt per release; keep the offer live ≥3 years after EACH release):

> **Open-source licenses.** This app includes third-party software:
> PRoot (GPL-2.0, © STMicroelectronics and contributors,
> github.com/termux/proot @ v5.1.107.96), PRoot-Distro (GPL-3.0-only,
> github.com/termux/proot-distro @ 5.10.0), Samba talloc (GPL-3.0,
> talloc.samba.org 2.5.0), libandroid-shmem (BSD 3-Clause, Termux),
> Flet + flet-ads (Apache-2.0), flet-terminal (MIT, © 2026 Onyeka
> Nwokike), msgpack (Apache-2.0), httpx/httpcore (BSD-3-Clause),
> h11/anyio/oauthlib/repath/six (MIT/BSD), idna (BSD-3-Clause), certifi
> (MPL-2.0), typing-extensions (PSF-2.0), Flutter engine (BSD-style),
> google_mobile_ads (Apache-2.0), xterm.dart (MIT).
>
> **Source code offer (GPL-2.0 §3(b) / GPL-3.0 §6(b)).** The complete
> machine-readable Corresponding Source for the GPL-licensed components
> above — and, [Option A: for this application as a whole, which is
> licensed under GPL-3.0-only] — is available at
> `https://github.com/Nwokike/proot-distro/tree/<release-tag>/third-party-sources`
> and will remain available for at least three (3) years from the date of
> this release. To receive the source on a durable physical medium for no
> more than the reasonable cost of copying, write to <owner-contact>.
> Upstream projects: termux/proot, termux/proot-distro,
> termux/termux-packages (build recipes), samba talloc.
>
> Full license texts: [GPL-2.0] [GPL-3.0] [Apache-2.0] [MIT] [BSD-3-Clause]
> [MPL-2.0] [PSF-2.0] (each scrollable in-app; same texts in `LICENSES/`).

Also add a `THIRD-PARTY-SOURCES.md` at repo root per release (checklist
A1/A3) recording exact tags, tarball SHAs, and recipe commits — that file
IS the §6(d) "clear directions."

---

## 4. Trademarks & naming

### 4.1 Ubuntu (Canonical IP Rights Policy — [S9],
`https://ubuntu.com/legal/intellectual-property-policy`)

 operative line is in the summary and repeated in §3.
> "You can **redistribute Ubuntu, but only where there has been no
> modification** to it." (§1 Summary [S9].)

> "You can **redistribute Ubuntu in its unmodified form**, complete with
> the installer images and packages provided by Canonical (this includes
> the publication or launch of virtual machine images). **Any redistribution
> of modified versions of Ubuntu must be approved, certified or provided by
> Canonical if you are going to associate it with the Trademarks.**
> Otherwise you **must remove and replace the Trademarks** and will need to
> recompile the source code to create your own binaries. **This does not
> affect your rights under any open source licence applicable to any of the
> components of Ubuntu.**" (§3 [S9].)

> "**This policy should be read together with the licence(s) of the
> relevant packages.** For the avoidance of doubt, where any other licence
> grants rights, this policy does not modify or reduce those rights under
> those licences." (§2 [S9].)

> "Canonical's Trademarks (registered in word and logo form) include:
> **UBUNTU KUBUNTU EDUBUNTU XUBUNTU JUJU LANDSCAPE** … **You cannot use the
> Trademarks in software titles.** If you are producing software for use
> with or on Ubuntu you may **reference Ubuntu, but must avoid: (i) any
> implication of endorsement, or (ii) any attempt to unfairly or confusingly
> capitalise on the goodwill** of Canonical or Ubuntu." (§4 [S9].)

**What this means for us:** we do NOT ship Ubuntu (we pull official
`ubuntu:24.04` OCI images at runtime = unmodified redistribution of
Canonical's binaries, which the policy expressly permits). So: name the
distro "Ubuntu" in text (descriptive reference is allowed), never in OUR
app title, never the logo without written permission, never imply
Canonical endorsement/certification. If M3 ever bundles a rootfs IN the
APK: only a byte-unmodified Canonical-published image, and the screen
must state it is unmodified; any customization (preinstalled packages,
locale seeding) = "modified version" needing Canonical approval OR
trademark stripping — decide in M3 planning, default to runtime-pull.
Same rule covers Docker Hub pulls: do not retag/mutate and keep calling
it Ubuntu.

### 4.2 Debian (Debian Trademark Policy v2.0, 2013-01-19 — [S10],
`https://www.debian.org/trademark`)

> "The Debian trademark is a registered United States trademark of
> **Software in the Public Interest, Inc.**, managed by the Debian project."
> (intro [S10].)

> "You **can use Debian trademarks to make true factual statements** about
> Debian or communicate compatibility with your product truthfully. Your
> intended use qualifies as **nominative fair use** … merely identifying
> that you are talking about Debian in a text, **without suggesting
> sponsorship or endorsement**." (When You Can Use … Without Asking [S10].)

> "You **cannot use Debian trademarks in a company or organization name or
> as the name of a product or service. You cannot use a name that is
> confusingly similar** to Debian trademarks. You **cannot use Debian
> trademarks in a domain name**, with or without commercial intent."
> (When You Can NEVER Use … [S10].)

> "Use the Debian trademarks in a manner that makes it clear that your
> project is **related to the Debian project, but … is not part of Debian,
> produced by the Debian project, or endorsed** by the Debian project.
> **Acknowledge Software in the Public Interest, Inc.'s ownership** …
> Include a **disclaimer of sponsorship, affiliation, or endorsement** …
> Example: **X PROJECT is not affiliated with Debian. Debian is a
> registered trademark owned by Software in the Public Interest, Inc.**"
> (How to Use … [S10].)

**What this means for us:** "Debian" appears in distro lists/descriptions
only (nominative fair use); add the SPI attribution + non-affiliation
disclaimer to the licenses screen and store listing (checklist A7 gives
the exact lines); never in the app name, package id, or domain.

### 4.3 Alpine (position — [S11-alpine page] `https://alpinelinux.org/about/`)

Alpine publishes **no trademark policy** on its about page (verified
2026-10-16: the page describes the distro — "independent, non-commercial
… musl libc and busybox" — with no trademark, naming, or logo terms).
So: there is no primary-source permission NOR prohibition to quote.
Conservative posture: treat "Alpine" exactly like Debian (nominative
descriptive use only, no logo, no endorsement implication) — that posture
is **our caution, not their rule**, and the absence of a policy is
**UNVERIFIED — needs counsel** if Alpine assets are ever bundled or the
logo displayed. (Alpine's wiki/docs carry their own CC-style content
licenses per-page; rootfs `/usr/share/doc` notices, if present, must be
preserved regardless.)

### 4.4 Kali (if ever added — Kali Linux Trademark Policy — [S11],
`https://www.kali.org/docs/policy/trademark/`)

> "Kali Linux and OffSec want to promote the widespread recognition of our
> trademarks … however, we also need to ensure our trademarks solely
> identify our company and our products."; "**Please do not modify the
> marks.** Examples of modifying the marks include abbreviating names,
> adding logos to the marks, or **combining the marks with other
> words**."; "We … **encourage others to use the marks so long as they are
> used to identify the products and services of OffSec**."; "The
> **first mention of an OffSec trademark should be accompanied by a symbol**
> … **™** … **provide a statement** … For example: '**KALI LINUX ™ is a
> trademark of OffSec.**'"; "**The use of OffSec trademarks in your domain
> names is prohibited**"; "Any other use outside of the scope … is not
> permitted **without express written permission of OffSec**." ([S11].)

**What this means for us:** certified set is Ubuntu/Debian/Alpine — Kali
is NOT in scope. If M3+ ever adds Kali: exact-form "Kali Linux" + ™ on
first mention + OffSec attribution line, no domain-name use, no
modification/combination. (Also note Kali's Network Service Policy exists
on the same docs site — penetration-testing-tooling positioning may draw
extra Play scrutiny; that interaction is **UNVERIFIED — needs counsel**.)

### 4.5 Our own app name — is "proot-distro" safe/hygienic?

- No upstream trademark policy was found for the strings "proot" or
  "proot-distro" (Termux projects publish no TM policy located in this
  research; absence noted, not relied upon). Descriptive use ("runs
  proot-distro containers") is the lowest-risk posture in any event.
- Hygiene risk is **confusion, not infringement**: our repo is now literally
  named `Nwokike/proot-distro`, identical to `termux/proot-distro`
  (decisions D-009). Mitigations (checklist A7): product/brand name decided
  in M0/M1 must NOT be "proot-distro" or "Termux …"; GitHub repo ABOUT
  field + README first line must disambiguate ("Unofficial Flet-based
  Android client. Not affiliated with the Termux project."); never claim
  to BE upstream. Whether a rename of the repo itself is needed is
  **UNVERIFIED — needs counsel** (GitHub namespace collisions are handled
  by GitHub, not trademark law, but user confusion is a Play
  Impersonation-policy vector — §5.2).
- Apache-2.0 §6 reminder for OUR notices: the license "does not grant
  permission to use the trade names, trademarks … except as required for
  reasonable and customary use in describing the origin of the Work"
  [S7] — so our attributions say "Flet (flet.dev)" descriptively and stop
  there.

### 4.6 Store-listing phrasing guidance (trademark-safe)

- Title: brand-only (no distro names, no "Ubuntu/Debian" anywhere in the
  title — Canonical forbids TM in software titles [S9]; Debian forbids TM
  as product names [S10]).
- Short description: "Run real Linux (Ubuntu, Debian, Alpine…) on your
  phone — no root." (nominative, factual, no endorsement words).
- Full description: add the disclaimer block (checklist A7: non-affiliation
  + SPI ownership + Canonical IP acknowledgment + "KALI LINUX ™ is a
  trademark of OffSec" ONLY if Kali is ever listed).
- Screenshots: terminal output showing `cat /etc/os-release` is factual
  use; do NOT use distro logos as feature graphic / icon elements (Ubuntu
  logo guidelines require permission [S9]; Debian logo-as-branding is
  restricted [S10]).
- Category/rating honest; no "Official" anywhere without rights (Play
  Misleading Claims policy [S14] — see §5.2).

---

## 5. Google Play expectations

### 5.1 OSS license notices — encouraged by Google, required by the licenses

Google's "Include open source notices" guidance ([S12],
`https://developers.google.com/android/guides/opensource`):

> "**As a developer, you are responsible for displaying open source library
> notices** used in your app **to comply with license requirements.**"

Google's tooling (oss-licenses Gradle plugin + `OssLicensesMenuActivity`)
is Play-services-native and does not apply to a Flet/serious_python build
— but the *responsibility sentence* is platform-agnostic, and our licenses
independently require the notices (§1). Our in-app LICENSES screen is the
Flet equivalent of `OssLicensesMenuActivity`. No Play policy was found that
mandates a specific OSS-notice *format* — only the developer responsibility
for compliance ([S12]) plus the license texts themselves.

### 5.2 Play policies that touch THIS app (with primary-source quotes)

1. **Deceptive Behavior — "download size first" rule** ([S14]). The full
   policy states: "3.2 Additional app resources (for example, game assets)
   may only be downloaded if they are necessary for the users' use of the
   app. Downloaded resources must be compliant with all Google Play
   policies, and **before beginning the download, the app should prompt
   users and clearly disclose the download size**." And: "Apps with content
   delivery network (CDN) facilitated downloads that **fail to prompt the
   user and disclose the download size prior to downloading**" are listed
   as common violations. **Directly relevant:** every distro install pulls
   hundreds of MB from Docker Hub. The install flow MUST show an explicit
   size prompt with consent before download (M3 UI requirement, not
   optional). This is the single highest-probability Play review tripwire
   in the app.
2. **Impersonation / IP policy family** ([S13] policy index lists
   "Impersonation" and "Intellectual Property" as standalone policies).
   Article bodies are JS-rendered (retrieved index only) — exact operative
   sentences are **UNVERIFIED — needs counsel** beyond the index. Posture:
   the trademark-safe listing rules in §4.6 (brand-only title, factual
   descriptions, non-affiliation disclaimers, no logos, no "Official")
   are designed to satisfy both the distro trademark policies AND Play's
   impersonation rules simultaneously.
3. **"Use of SDKs In Apps: If you include an SDK in your app, you are
   responsible for ensuring that their third-party code and practices do
   not cause your app to violate Google Play Developer Program Policies"**
   ([S13] hub summary). Relevant to AdMob (`flet-ads`) and any bundled
   rootfs: SDK/data declarations in the Data safety form must match what
   the SDKs actually do.
4. **Functionality / User Experience** ([S13] hub: "apps should provide
   users with a basic degree of functionality and a respectful user
   experience"). An app that downloads a rootfs but cannot execute proot
   (M0 red) would fail review on functionality grounds — another reason
   M0 is the go/no-go gate.

### 5.3 Data-safety interaction (only what is directly relevant)

The Data safety form asks what user data the app collects/shares. Directly
relevant touchpoints: (a) AdMob SDK collection (declared per Google's AdMob
guidance — follow the AdMob data-safety instructions, not this document);
(b) Docker Hub pulls (registry sees the device IP — a network disclosure,
not app collection; the download-size consent in 5.2(1) covers the user
facing side); (c) rootfs contents never leave the device (no app-collected
account data inside guests by default). Nothing in the Data safety form
changes the license analysis. Anything beyond this paragraph (e.g. whether
guest-OS telemetry counts as app collection) is **UNVERIFIED — needs
counsel** and is out of scope for this reference.

---

## 6. Action checklist (owners of record + milestones)

Conventions: owner = the repo surface that must carry the item (all work
lands via the owning milestone's plan mode). Re-verify every version bump
(item A5 is the standing guard).

| # | Action | Owner of record | Milestone |
|---|---|---|---|
| A1 | Create `LICENSES/` notices file in repo root: full texts of GPL-2.0, GPL-3.0, Apache-2.0, MIT, BSD-3-Clause, MPL-2.0, PSF-2.0 + per-component copyright lines (§1 tables) + serious_python entry once M5 artifact is inspected | `LICENSES/` + §3.3 wording | **M3** (scaffold; screen reads from it later) |
| A2 | Implement in-app LICENSES screen (Settings → Open-source licenses): §3.3 wording, per-component entries, scrollable full texts, source-offer link; coordinate with the planned screen (roadmap M6) — build the content contract in M3, wire the UI in M4/M6 | `src/screens/licenses_screen.py` (proposed) | **M3** content, **M6** ship |
| A3 | Per-release `THIRD-PARTY-SOURCES.md`: exact tags/SHAs/recipe commits for proot v5.1.107.96, proot-distro wheel, talloc 2.5.0, shmem 0.7 + written-offer contact; link from release notes (house release-notes-finalize step, roadmap M5) | release notes + repo root file | **M5** (first artifact), every release after |
| A4 | `test_imports_vs_deps.py` guard (M3 scaffold): fail CI if `chardet`/`cookiecutter`/any dev-only package is importable from `src/`; companion audit that `[tool.flet.cleanup]` globs match the ACTUAL tree (oauthlib prune decision recorded, never copied blind — roadmap M5) | `tests/test_imports_vs_deps.py` + `pyproject.toml [tool.flet.cleanup]` | **M3** guard, **M5** cleanup audit |
| A5 | License re-verification on every dependency bump: re-read dist-info `License`/`License-Expression` + `licenses/` for the bumped package; any GPL-version or new-copyleft change re-opens §2 with counsel before merge | `uv.lock` diff + this doc's §1 tables | Every bump (standing) |
| A6 | Upstream fix: flet-terminal 0.4.0 must ship `license = "MIT"` + `license-files = ["LICENSE"]` + narrowed data glob (roadmap M1 already requires); until then our notices file carries the MIT text manually | `Nwokike/flet-terminal` repo (M1) | **M1** |
| A7 | Trademark-safe naming + listing: brand name ≠ proot-distro/Termux/Ubuntu/Debian (M0/M1 brand decision); README + repo ABOUT disambiguation line; store-listing disclaimer block (SPI ownership, Canonical IP acknowledgment, non-affiliation); no distro logos in icon/feature graphic; §4.6 phrasing | README + Play listing + licenses screen | **M3** (README), **M6** (listing) |
| A8 | **Counsel engagement + Option A/B/C decision** (M3 plan-mode agenda): the in-process `proot_distro` import (§2.3(1)) is the strongest combination signal; retrofitting a process boundary later costs 10×. Until decided, proceed as Option A (repo stays public, sources shippable) | M3 plan mode | **M3** |
| A9 | Download-size consent in install flow (Play Deceptive Behavior §3.2 [S14]): explicit size prompt + user consent before every OCI pull; bundled-rootfs decision (unmodified Canonical image only, or runtime-pull default) with TM review | install flow UI | **M3** |
| A10 | M6 distribution review: source-offer link live ≥3 years per release; Installation-Information posture memo (counsel); F-Droid/GitHub fallback build assessment (Play review behavior for OCI pulls — roadmap open item 3); Kali addition needs §4.4 TM pass first | M6 plan mode | **M6** |

---

## 7. UNVERIFIED list (everything in this document needing counsel)

1. Whether the in-process `proot_distro` import makes our app a GPL
   derivative work (§2.3(1), Options B/C in §2.4).
2. Whether a CLI/subprocess-only boundary would suffice (Option B, §2.4).
3. Community-practice safety / UserLAnd-Andronix precedent (§2.4-C).
4. Installation-Information duties for a free Play download (§3.1).
5. Alpine's trademark position (no policy found — §4.3).
6. App-name ("proot-distro" repo collision) risk level (§4.5).
7. Kali Network-Service-Policy / pen-test-tooling Play interaction (§4.4).
8. Play Impersonation/IP article operative text (index only retrieved —
   §5.2(2)).
9. serious_python runtime's exact license file (provisional entry — §1c).
10. Docker Hub ToS / OCI-registry redistribution terms for guest images
    (not examined — §4.1/§6-A9 context).
11. Data-safety edge questions beyond §5.3.

*This document is a research reference compiled from the primary sources
listed at the top. It is not legal advice. Engage counsel at M3 (item A8)
before the importer architecture freezes.*