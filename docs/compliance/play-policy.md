# Play policy compliance reference — proot-distro (Flet/Android)

**Date:** 2026-10-16 · **Status:** pre-M1 reference; re-verify each milestone (policy pages change; quotes below are pinned to fetch date)
**App:** Flet/Python Android app running Linux containers via bundled `libproot.so` (proot rides in the APK through `jniLibs`/legacy-packaging); pulls Ubuntu/Debian/Alpine OCI images from Docker Hub **at runtime, user-initiated**; monetized via AdMob through `flet-ads` 1.0.4; public repo `github.com/Nwokike/proot-distro`.
**Context read first:** `docs/roadmap.md`, `docs/decisions.md`, `docs/reference/app-ffmpeg.md` (Play-facing CI guards), `docs/m0-checklist.md` (device evidence runs #1–3), `docs/reference/dep-flet-ads.md` + `docs/dependency-studies/flet-ads.md` (ConsentManager/UMP flow), `m0-spike/tools/check_apk_alignment.py` (ELF alignment evidence tooling).
**Verification rule used throughout:** every policy claim quotes Google's official docs (`support.google.com/googleplay/android-developer/…`, `developer.android.com`, AdMob help, UMP developer docs) with URLs. Anything that cannot be pinned to an official page is labeled **UNVERIFIED**.

## Source index (all fetched 2026-10-16)

| # | Page | URL |
|---|---|---|
| S1 | Device and Network Abuse | https://support.google.com/googleplay/android-developer/answer/9888379 |
| S2 | Target API level requirements | https://support.google.com/googleplay/android-developer/answer/11926878 |
| S3 | Support 16 KB page sizes | https://developer.android.com/guide/practices/page-sizes |
| S4 | Support 64-bit architectures | https://developer.android.com/google/play/requirements/64-bit |
| S5 | Foreground service types are required (Android 14) | https://developer.android.com/about/versions/14/changes/fgs-types-required |
| S6 | Foreground services overview | https://developer.android.com/guide/components/foreground-services |
| S7 | Provide information for Google Play's Data safety section | https://support.google.com/googleplay/android-developer/answer/10787469 |
| S8 | User Data policy | https://support.google.com/googleplay/android-developer/answer/10144311 |
| S9 | Prepare your app for review (App content) | https://support.google.com/googleplay/android-developer/answer/9859455 |
| S10 | Create and set up your app (AAB delivery) | https://support.google.com/googleplay/android-developer/answer/113469 |
| S11 | Use Play App Signing | https://support.google.com/googleplay/android-developer/answer/9842756 |
| S12 | AdMob policies and restrictions | https://support.google.com/admob/answer/6128543 |
| S13 | Banner ad guidance | https://support.google.com/admob/answer/6128877 |
| S14 | Discouraged banner implementations | https://support.google.com/admob/answer/6275345 |
| S15 | Set up UMP SDK (Android) | https://developers.google.com/admob/ump/android/quick-start |
| S16 | Meet target API level requirement (developer guide) | https://developer.android.com/google/play/requirements/target-sdk |

---

## 1. Device & Network Abuse deep-dive (the load-bearing policy)

### 1.1 Exact policy text (S1)

> "An app distributed via Google Play may not modify, replace, or update itself using any method other than Google Play's update mechanism. Likewise, an app may not download executable code (such as dex, JAR, .so files) from a source other than Google Play. This restriction does not apply to code that runs in a virtual machine or an interpreter where either provides indirect access to Android APIs (such as JavaScript in a webview or browser)."
> — https://support.google.com/googleplay/android-developer/answer/9888379

The same page adds the interpreted-language clause, which is the sentence most likely to be quoted back at us in a review rejection:

> "Apps or third-party code, like SDKs, with interpreted languages (JavaScript, Python, Lua, etc.) loaded at run time (for example, not packaged with the app) must not allow potential violations of Google Play policies."
> — https://support.google.com/googleplay/android-developer/answer/9888379

And the adjacent self-install clause (relevant to §7 "install external apps"):

> "Apps that install other apps on a device without the user's prior consent."
> — listed as a violation example, https://support.google.com/googleplay/android-developer/answer/9888379

### 1.2 Flow (a): rootfs OCI images pulled at runtime — legal analysis

**What happens technically.** On a user tap ("Install Ubuntu"), `services/proot_service.py` calls proot-distro's in-process install path (`pull_image(ref, rootfs_fd, …)` → layer download from Docker Hub → digest verify → tar extract into the app-private `containers/<name>/rootfs/`), proven on-device (M0 G2 alpine 7.4 s, G4 debian:bookworm 40.1 s; `docs/m0-checklist.md` runs #2–3). The extracted tree contains full Linux userlands — including ELF binaries for `aarch64` Linux (guest `sh`, `apt-get`, `dpkg`, etc.).

**The three-pronged argument that this is user data, not "executable code" under the policy:**

1. **Nothing downloaded is Android-executable.** The policy's examples are parenthesized precisely: "(such as dex, JAR, .so files)". A Debian `arm64` ELF (`/bin/sh` built for Linux glibc against the guest loader) is not a dex file, not a JAR, not an Android `.so`; the Android runtime (`app_process64`, ART, `linker64`) cannot load or execute it. It executes only inside the proot-translated guest environment, which the app itself ships (see flow (c)). The downloaded bytes are inert data until our shipped binary interprets the syscalls — structurally closer to a document opened by a viewer than to a downloaded `.so` loaded with `dlopen`.
2. **User-initiated content, not a self-update.** The first sentence of the rule targets self-modification: "may not modify, replace, or update itself using any method other than Google Play's update mechanism." A rootfs download does not modify, replace, or update the app: no APK code path changes, no app `.so` is replaced, no behavior of the Android app itself changes. It is content the user explicitly requests (tap → progress → cancelable), stored in app-private storage, deletable per-container from the UI (roadmap M3 container actions: open/stop/reset/remove). This is the same legal shape as a podcast app downloading episodes or a game downloading level packs.
3. **Community precedent of live listings.** UserLAnd (`tech.ula`, "Run Linux on Android. No root required."), Termux (`com.termux`, "Terminal emulator and Linux environment."), and Andronix ("Linux on Android, fully automated: Ubuntu, Debian, Kali and desktops, no root.") all ship on Google Play today (store pages fetched live 2026-10-16; see §8) and all download Linux rootfs content at runtime. UserLAnd in particular executes downloaded guest binaries through a bundled proot — the identical architecture to ours.

**Honest risk calibration (UNVERIFIED as to reviewer outcome).** No Google page states "downloading Linux rootfs images is permitted." The VM/interpreter carve-out ("code that runs in a virtual machine or an interpreter where either provides indirect access to Android APIs") does **not** cleanly cover us: our guest code does not run in a VM/interpreter that mediates Android APIs — proot translates Linux syscalls, and the guest has *no* Android API access at all (which is arguably safer, but it is not the carve-out as written). The interpreted-language clause ("Python … loaded at run time … must not allow potential violations") is aimed at remotely-loaded scripts, not at user-downloaded filesystem images, but a hostile reviewer could cite it. So: the legal analysis above is our best good-faith reading, the precedent is real and current, but **whether a given reviewer accepts the "user data, not executable code" framing is UNVERIFIED** — it can only be settled by submitting (roadmap open item §5.3). Mitigations below are designed so that even a skeptical reviewer sees a user-data-shaped product.

### 1.3 Flow (b): `apt-get` inside the guest — why this is different

When the user runs `apt-get install cowsay` in a session, package downloads happen **inside the Linux sandbox**: the guest `apt` (a Linux binary running under proot translation) fetches `.deb` files from Debian/Ubuntu mirrors into the guest filesystem and unpacks them there. At no point does the *Android app* download executable code:

- The downloader is guest code (Debian's apt), not app code; the app's Android-side network calls are only the OCI layer pulls of flow (a) plus AdMob traffic.
- The artifacts (`.deb`s, unpacked ELF binaries with Linux ABI) are, again, not Android-loadable: not dex, not JAR, not Android `.so`. They cannot be `dlopen`ed by the app process, cannot reach ART, cannot touch Android APIs.
- This is indistinguishable, policy-wise, from a browser app downloading files the user asked for, or a torrent client writing bytes to disk. The app never executes what apt fetched *as Android code* — guest binaries only ever run under proot translation, mediated by our shipped binary.

M0 device note: `apt-get update && apt-get install cowsay` inside Debian is the last M0 blocker (G4-apt rc=100, `link()` denied by SELinux; fix = Termux-mode `--link2symlink` + `-L` + `--kill-on-exit` + `--sysvipc`, `docs/m0-checklist.md` run #3). The SELinux denial itself is evidence *for* our case: the platform treats guest file operations as ordinary app-data writes, not as code installation.

### 1.4 Flow (c): our app never downloads Android executables — the D-002-era reasoning

The complete Android-executable chain ships **inside the APK** and never changes without a Play update:

- `libproot.so` + loader + `libtalloc.so` + `libandroid-shmem.so` ride in the APK (`jniLibs` via the `flet-proot` native wheel, M2; M0 proven with hand-staged libs + `legacy_packaging = true` extracting to `nativeLibraryDir`, exposed to Python as `ANDROID_NATIVE_LIBRARY_DIR`).
- M0 G1 proved `nativeLibraryDir/libproot.so --version` executes on-device (`proot 5.1.107.96`, `process_vm = yes, seccomp_filter = yes`).
- The Python layer (`proot-distro` 5.10.0, pure-Python, zero deps) ships in the APK's Python bundle; it is never fetched at runtime.
- The only runtime downloads are (a) OCI layers (user data, §1.2) and (b) AdMob ad assets (Google's own SDK).

So the sentence a reviewer checks — "may not download executable code (such as dex, JAR, .so files) from a source other than Google Play" — is satisfied literally: **zero dex/JAR/.so bytes reach the device from any source other than the Play-delivered APK/AAB itself**. State this verbatim in the review-notes / appeal text if ever asked.

### 1.5 Mitigation checklist with current state

| # | Mitigation | State (2026-10-16) |
|---|---|---|
| D-1 | All downloads are explicit user taps with progress + cancel + size display (never silent background fetch) | Design locked (roadmap M3 install flow); not yet built — M3 |
| D-2 | Bundle one default rootfs in the APK so first-run is fully offline (download is an *option*, not a requirement) | Planned (roadmap M3 exit: "offline first-boot with one bundled rootfs", ~30 MB budget); not yet built — M3 |
| D-3 | Per-container delete/reset from UI (user data lifecycle, like downloads in any content app) | Planned M3 container actions; not yet built — M3 |
| D-4 | Never download Android executables: proot + loader + Python layer all ship in APK | Proven M0 G1; wheel-ify in M2 |
| D-5 | Never install APKs / never trigger installs of other apps (no `REQUEST_INSTALL_PACKAGES`, no sideload prompts) | By design (no such flow exists); assert in M5 manifest audit |
| D-6 | Reviewer-facing text prepared: store listing + "app access" instructions frame rootfs as user-downloaded Linux content, exec chain ships in-app | To write — M5/M6 |
| D-7 | Fallback distribution ready if Play rejects: F-Droid/GitHub APK + GitHub Releases ritual already house-standard (D-006) | Releases-via-prerelease proven in M0; F-Droid track is M6 fallback |
| D-8 | Keep UserLAnd/Termux/Andronix precedent fresh (re-check listings before each submission) | Baseline in §8; re-check at M5/M6 |

---

## 2. Technical Play requirements

### 2.1 targetSdk timeline (S2, S16)

> "Starting August 31, 2026: New apps and app updates must target Android 16 (API level 36) or higher to be submitted to Google Play; except for Wear OS, and Android Automotive OS apps…"
> — https://support.google.com/googleplay/android-developer/answer/11926878

> "Existing apps must target Android 15 (API level 35) or higher to remain available to new users on devices running Android OS higher than your app's target API level."
> — https://support.google.com/googleplay/android-developer/answer/11926878

> "You will be able to request an extension to November 1, 2026 if you need more time to update your app."
> — https://support.google.com/googleplay/android-developer/answer/11926878

Schedule table on the same page pins the prior step: Android 15 (API 35) since **August 31, 2025**; Android 16 (API 36) from **August 31, 2026**. Our app is a phone app (none of the Wear/TV/Auto/XR exceptions apply), so the operative rule is: **target API 36+ at first Play submission** (our submission will necessarily postdate 2026-08-31).

Flet-template implication (verified in-repo): **`target_sdk_version` / `min_sdk_version` do NOT exist as keys in flet 1.0.4** — "SDK levels come from the build template" (`docs/reference/dep-flet-cli.md`; roadmap §1 D1 row). So targetSdk is inherited from whatever template the pinned flet-cli bakes at `flet build` time. Action: at M5, read the merged manifest / `aapt` dump of the CI AAB and assert `targetSdkVersion ≥ 36`; if the template lags, the only levers are bumping the flet family or a documented manifest patch (FFmpeg-study discipline: comment with the exact error). Owner of this check: repo config + CI (M5 floor-inspection step — the exact step FFmpeg's runbook promised but never implemented; `docs/reference/app-ffmpeg.md` drift #5).

Behavioral risk of API 36 worth naming now: `targetSdk 35/36 behavior` is explicitly **unverified** for our stack (`docs/dependency-studies/flet-ads.md` §7 — nothing in the installed Python/Dart sources references targetSdk, edge-to-edge, or FGS types). Known exposure surface at 35+: 16 KB pages (§2.2), edge-to-edge enforcement, and Android 14+ FGS rules (§6). All must be shaken out on the CI-built AAB, not reasoned about from source.

### 2.2 16 KB pages (S3)

> "To ensure your app works correctly on the latest versions of Android, all apps targeting Android 15 (API level 35) and higher must support 16 KB memory page sizes on 64-bit devices on Google Play. Starting February 1, 2027, if your app updates don't support 16 KB memory page sizes, you won't be able to release these updates."
> — https://developer.android.com/guide/practices/page-sizes

What "support" means in practice (same page):

> "For any shared libraries, verify that the shared libraries' ELF segments are aligned properly using 16 KB ELF alignment."
> — https://developer.android.com/guide/practices/page-sizes

> "you can use the APK Analyzer to identify whether any native code is present and then check the alignment of ELF segments for any shared libraries that you find."
> — https://developer.android.com/guide/practices/page-sizes

> "Remove any hard-coded dependencies that reference the PAGE_SIZE constant or instances in your code logic that assume that a device's page size is 4 KB (4096). Use getpagesize() or sysconf(_SC_PAGESIZE) instead."
> — https://developer.android.com/guide/practices/page-sizes

> "run the following command to verify that it's using a 16 KB environment: adb shell getconf PAGE_SIZE. The command should return a value of 16384."
> — https://developer.android.com/guide/practices/page-sizes

**Our evidence.** `tools/check_apk_alignment.py` exists precisely for this: every CI build runs it against the built APKs. As of **M2 (2026-10-16)** it is *enforcing* for the flet-proot payload libs (`libproot.so`, `libproot-loader.so`, `libtalloc.so`, `libandroid-shmem.so`): each must be present in every inspected APK and each must have all PT_LOAD segments aligned to ≥ `0x4000` (16 KiB) — the Play requirement for targetSdk 35+; the CPython stdlib libs that serious_python bundles stay report-only. The wheel builder itself (`tools/build_flet_proot_wheel.py`) asserts the same alignment **before writing the wheel** from sha256-pinned Termux debs, so a regression fails at the earliest possible point with a named offender. Recorded output (first green run 38906734815, repeated every build since, re-verified by the M2 dual-ABI spike legs) shows every payload lib at `align=0x4000 (16K-OK)`; the excerpt is recorded in `docs/m0-checklist.md` §"CI evidence — APK alignment". The once-planned **NDK-r28+ rebuild is not required while the Termux prebuilts stay 16K-aligned** — the pin lock + build-time assert + APK gate are the guarantee (the NDK route remains a documented fallback if an upstream deb ever regresses). M5 keeps gating releases on this check.

### 2.3 minSdk floors

**UNVERIFIED — no Play page mandating a minimum minSdk was pinned.** Play's requirement is on *target* API (§2.1), not minimum; minSdk remains our choice (trade-off: wider device reach vs. API surface). Two in-repo facts constrain it: (1) flet 1.0.4 exposes no `min_sdk_version` key — the floor comes from the build template (`docs/reference/dep-flet-cli.md`); (2) FFmpeg drift #5 requires our CI to actually inspect the AAB's minSdk/versionCode ("implement it for real in ours — assert `libproot.so` ABI floor," `docs/reference/app-ffmpeg.md`). Action: M5 reads the floor from the built AAB and records it here; revisit only if the template floor excludes devices we care about (M0 already validated on Android 16 aarch64; an older-device run is still owed per M0 gate 5).

### 2.4 64-bit (S4)

> "Apps published on Google Play need to support 64-bit architectures."
> — https://developer.android.com/google/play/requirements/64-bit

> "For the ARM architecture, the 32-bit libraries are located in armeabi-v7a. The 64-bit equivalent is arm64-v8a. For the x86 architecture, look for x86 for 32-bit and x86_64 for 64-bit."
> — https://developer.android.com/google/play/requirements/64-bit

> "It isn't required to support every 64-bit architecture, but for each native 32-bit architecture you support you must include the corresponding 64-bit architecture."
> — https://developer.android.com/google/play/requirements/64-bit

Our posture: `arm64-v8a` is the ship ABI (M0 device truth is Android 16 aarch64); `--split-per-abi` planned (roadmap M5); x86_64 inclusion is an explicit open decision (O-6, emulator QA vs. what the forge wheel ships) — note the CollabShell precedent in-repo: x86_64 was dropped there because a dependency's x86_64 wheel lacked 16 KB ELF alignment (`docs/reference/app-collabshell.md`… wait, that path is `docs/reference/app-collabshell.md` per the reference dir listing; the in-repo citation is the CollabShell study row). Per the 64-bit rule, whatever 32-bit ABIs we ship (if any — roadmap currently implies 64-bit-only + possible x86_64) must be paired with their 64-bit counterparts; shipping arm64-v8a-only satisfies the rule outright. Assert ABI set from the AAB in the M5 inspection step.

### 2.5 AAB vs APK

> "[Google Play] uses Android App Bundles to generate and deliver APKs that are optimized for each device configuration, providing users with more efficient apps. This means you only need to build, sign, and upload a single app bundle…"
> — https://support.google.com/googleplay/android-developer/answer/113469

House pipeline builds both: `flet build apk --split-per-abi` (device QA + GitHub Releases sideload) and AAB (the Play upload), per roadmap M5. **The claim "new apps must upload AAB (APK upload not accepted)" is UNVERIFIED** (no pinned quote located; stated here as widely-understood console behavior, to be confirmed in-console at M5). Either way our M5 produces a signed release AAB, so we are covered under both readings.

### 2.6 Play App Signing interplay with our keystore (S11)

> "With Play App Signing, Google manages and protects your app's signing key on the same secure infrastructure that Google uses to store its own keys."
> — https://support.google.com/googleplay/android-developer/answer/9842756

> "When you use Play App Signing, you deal with two distinct keys… Upload key — You (Keep this secure!)… Format: Stored in a Java keystore (.jks or .keystore)… Requirement: Must be an RSA key of 2048 bits or more… Purpose: You use this key to sign your app bundle before uploading it…"
> — https://support.google.com/googleplay/android-developer/answer/9842756

> "When Google generates and signs your APKs with the app signing key, it uses apksigner to add two stamps to your app's manifest (com.android.stamp.source and com.android.stamp.type)."
> — https://support.google.com/googleplay/android-developer/answer/9842756 (raw-page extraction)

Our setup (D-008): house kiri keystore recovered, alias `upload`, secrets `KEYSTORE_BASE64`/`KEY_ALIAS`/`KEYSTORE_PASSWORD`/`KEY_PASSWORD` set on the repo; CI decodes and signs via `FLET_ANDROID_SIGNING_*` env; pyproject carries the `[tool.flet.android.signing]` block. Interplay notes: (1) the house key is the **upload** key — first Play enrollment decides whether Google generates the app-signing key or we transfer ours; record that choice in Play Console at M5 and never rotate casually (rotation = update-trust event). (2) Passwords only via env (`FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD` / `_KEY_PASSWORD`); `key_store`/`key_alias` may live in pyproject (D1 study). (3) F-Droid/GitHub fallback builds (M6) must use the same signing story deliberately — a differently-signed sideload APK cannot update-install over the Play one; document which key signs the fallback channel at M6.

---

## 3. Data safety form — the actual answer map

### 3.1 The governing quotes (S7, S8)

> "All developers must declare how they collect and handle user data for the apps they publish on Google Play, and provide details about how they protect this data through security practices like encryption. This includes data collected and handled through any third-party libraries or SDKs used in their apps."
> — https://support.google.com/googleplay/android-developer/answer/10787469

> "In addition to reviewing how your app collects and shares user data, you should also review how any third-party code (such as third-party libraries or SDKs) in your app collects and shares such data. It's your responsibility to ensure that any such code used in your app is compliant with Play Developer Program policies. You must reflect data collection or sharing carried out by such third-party code in the Data safety form for your app."
> — https://support.google.com/googleplay/android-developer/answer/10787469

> "You may want to refer to your SDK providers' published Data safety information for details. Check Google Play SDK Index to see if your provider has provided a link to their guidance."
> — https://support.google.com/googleplay/android-developer/answer/10787469

> "All apps must post a privacy policy link in the designated field within Play Console, and a privacy policy link or text within the app itself."
> — https://support.google.com/googleplay/android-developer/answer/10144311

> "Prominent disclosure: You must provide an in-app disclosure of your data access, collection, use, and sharing."
> — https://support.google.com/googleplay/android-developer/answer/10144311 (section header)

### 3.2 Data our app itself handles

| Data | Our handling | Form implication (maintainer judgment — not a Google quote) |
|---|---|---|
| Personal info (name, email, accounts) | None. No login flow exists (`Page.login()` unused; `oauthlib` is a prune candidate per roadmap M5 cleanup globs). Nothing personal is stored anywhere. | No "personal info" collection declared for first-party code. |
| Files / storage | Rootfs trees + manifests under app-private dirs (`containers/<name>/{rootfs,manifest.json,shm}`, `oci_layers/`, `oci_manifests/`; `docs/reference/dep-proot-distro.md`). User's *own* Linux files live inside the guest fs. Nothing leaves the device. | Local-only user files; "collected" = No (on-device only, not transmitted). The form asks about collection *off-device* — confirm exact wording in-console at M5. |
| Network (first-party) | OCI layer pulls from Docker Hub/registry (`registry-1.docker.io` via proot-distro's urllib, 120 s timeout, 5×5 s retries) + distro metadata. No analytics, no crash reporting, no first-party servers at all. | Disclose network use in privacy policy; registry hostnames see IP + TLS handshake (standard). No data "shared" with third parties by our code. |
| Diagnostics | None shipped (no crash reporter in the frozen dep set, D-003). | Nothing to declare unless added later. |

### 3.3 AdMob SDK data collection (the part that dominates the form)

The form for this app will be ~90% AdMob. Per §3.1, **we must reflect the ads SDK's collection in our form** even though our code collects nothing.

> "In the Overview section, we added a line encouraging certain developers to refer to their SDK providers' published data safety information for details, like Firebase and AdMob."
> — https://support.google.com/googleplay/android-developer/answer/10787469 (changelog entry on the Data safety page)

**UNVERIFIED — Google's own AdMob data-safety guidance page could not be pinned** (the developers.google.com AdMob data-safety URL 404'd on fetch; AdMob help answer IDs tried for interstitial/data-safety content returned "Sorry, this page can't be found"). The Play SDK Index pointer above is the verified fallback: at M5, open the Play SDK Index entry for Google Mobile Ads (`google_mobile_ads ^9.0.0`, resolved minor TBD at build time) and transcribe its declared data types into the form. Do not guess AdMob's collected types here.

### 3.4 "No data collected" vs. ads SDK nuance

Because the AdMob SDK collects and shares data (advertising IDs, etc. — specifics per its SDK Index entry, **UNVERIFIED** until transcribed), this app **cannot** truthfully select "No data collected / no data shared" in the Data safety form even though first-party code collects nothing. The form is answered for the *shipped artifact including SDKs* (§3.1 quotes). Concretely at M5: answer the form's collection/sharing questions from the AdMob SDK Index entry + `google_mobile_ads` SDK behavior, mark first-party answers as none, and keep the privacy policy (§3.5) consistent with the form — mismatches between policy text and form answers are a classic review flag.

### 3.5 Privacy policy requirement + where it lives

> "The privacy policy must, together with any in-app disclosures, comprehensively disclose how your app collects, uses, and shares user data. This includes the types of parties with whom it's shared."
> — https://support.google.com/googleplay/android-developer/answer/9859455 (Prepare-your-app-for-review page)

> "Make sure your privacy policy is available on an active URL, applies to your app, and specifically covers user privacy."
> — https://support.google.com/googleplay/android-developer/answer/9859455

Proposal (decision for M5/M6): host the policy at a stable URL under our control — either the public repo (`https://github.com/Nwokike/proot-distro` — e.g. a `PRIVACY.md` rendered page; repo is already public per D-007) or the kiri site if one exists for this product. Requirements the URL must satisfy: active at review time, app-specific (names the app, the Docker Hub pulls, the AdMob SDK, the in-app licenses screen), plus a matching in-app link (settings/about screen → policy URL; S8 requires link-or-text *within the app itself*). Also declare ads in App content ("Declare whether or not your app contains ads" — S9) and complete the ads/target-audience/content-rating questionnaires there.

---

## 4. Ads policies (AdMob via flet-ads 1.0.4)

### 4.1 Program-policy umbrella (S12)

> "Publishers who wish to participate in AdMob must comply with our online AdSense Program policies."
> — https://support.google.com/admob/answer/6128543

> "All publishers are required to adhere to the following policies… If you fail to comply with these policies without permission from Google, we reserve the right to disable ad serving to your app and/or disable your AdMob account at any time."
> — https://support.google.com/admob/answer/6128543

Terminal/utility apps are not a restricted category per se, but a terminal screen is a *continuous-interaction* surface — which is exactly what the placement rules below care about.

### 4.2 Placement rules that bite a terminal app (S13, S14)

> "Close proximity of banner ads to other elements within an app is one of the biggest causes of accidental clicks. To avoid accidental clicks, banner ads should not be placed next to interactive buttons, such as a 'next' button or a custom app menu bar, next to interactive content like a text chat box or an image in an image gallery, or on a game play screen where users are continuously interacting with the app."
> — https://support.google.com/admob/answer/6128877

> "Banner ads should not float or hover over app content… Also, banner ads should not move as a user scrolls, as users may try to click on the menu but end up clicking on the ad accidentally instead. This specific implementation is against policy and we reserve the right to disable ad serving to your app."
> — https://support.google.com/admob/answer/6275345

> "Close proximity of banner ads to other elements within an app is one of the biggest causes of accidental clicks… This banner ad placement can put your app or your account at risk if too many accidental clicks occur, and we recommend against such an implementation."
> — https://support.google.com/admob/answer/6275345

Mapping to our surfaces (verified flet-ads capabilities: `BannerAd` fixed 320×50 `AdSize.banner`, `InterstitialAd` single-show service, no rewarded/native/app-open in 1.0.4 — `docs/dependency-studies/flet-ads.md` §§3–4):

- **Terminal/session screens: NO banner, ever.** A terminal is "interactive content like a text chat box" plus "continuously interacting" — the two named danger cases. This ratifies the roadmap's reserved-row design (banner only on non-terminal screens: distro list, install progress, settings) and the parking-lot default (interstitial-only).
- **Banner rows must be layout-reserved and static** — never overlay the terminal view, never float, never move with scroll. `BannerAd` is a layout control (occupies space), which composes well with a fixed-height row — but only where the row exists permanently so layout never jumps on `on_load`.
- **Interstitials only at natural breaks** (after install completes, after container removal, return-to-list) — never mid-typing, never on first launch; one live instance at a time (Dart static-slot constraint, flet-ads study §3.3). No rewarded ads exist to be misused; no policy surface there.

### 4.3 UMP consent in EEA/UK → flet-ads ConsentManager (S15)

> "You should request an update of user consent information at every app launch using requestConsentInfoUpdate() to check if consent is required or if a privacy options entry point is needed."
> — https://developers.google.com/admob/ump/android/quick-start

> "After updating consent status, use loadAndShowConsentFormIfRequired() to display any necessary forms for collecting user consent."
> — https://developers.google.com/admob/ump/android/quick-start

> "The Google User Messaging Platform (UMP) SDK helps manage user privacy choices and requires Android API level 21 or higher."
> — https://developers.google.com/admob/ump/android/quick-start

One-to-one mapping to our `ConsentManager` service (`docs/dependency-studies/flet-ads.md` §3.4): `request_consent_info_update` → `load_and_show_consent_form_if_required` → gate everything on `can_request_ads()`; settings screen hosts `show_privacy_options_form` behind the `get_privacy_options_requirement_status() == REQUIRED` check (the "privacy options entry point" in Google's words). `APPLICATION_ID` comes from our own `[tool.flet.android.meta_data]` (no patcher in the package — `docs/reference/dep-flet-ads.md`); CI carries the production-ID guard (FFmpeg precedent). `reset()` stays out of shipped code paths (testing only).

**UNVERIFIED specifics:** the exact EEA/UK enforcement wording for consent (IAB TCF v2 messaging, "privacy options entry point" UI requirements) was not pinned to a Play-side quote — the UMP quick-start above is developer guidance, and AdMob-side consent-policy answer IDs returned not-found pages. Treat EEA behavior as: implement the full UMP flow + persistent entry point, verify the form renders on a real device with `DebugGeography.EEA` during M3/M5, and re-check AdMob's consent policy text before first submission.

---

## 5. Export / crypto self-classification

**UNVERIFIED — no citable page pinned.** The Play Console "Export compliance" declaration flow (the standard questionnaire asking whether the app uses cryptography, with the widely-used "HTTPS-only / standard encryption exemption" path) could not be verified against an official URL in this pass (candidate answer IDs returned not-found; the developer.android.com export-compliance URL 404'd). What can be stated from the frozen dep set (not a policy quote): our app's cryptography is limited to standard TLS (HTTPS pulls from Docker Hub/registries via Python `urllib` + certifi CA bundle; AdMob SDK traffic) — no custom crypto, no VPN, no encrypted-storage claims. **Action (M5, Play Console step):** complete the export-compliance declaration in-console truthfully (standard-TLS-only posture), and only then transcribe the exact question/answer pair back into this section with its URL. Until that happens, make no exemption claim in review-facing text.

---

## 6. Foreground service / background execution (M4 open item)

### 6.1 The Android 14+ rule (S5)

> "If your app targets Android 14, it must specify appropriate foreground service types."
> — https://developer.android.com/about/versions/14/changes/fgs-types-required

> "If an app that targets Android 14 doesn't define types for a given service in the manifest, then the system will raise MissingForegroundServiceTypeException upon calling startForeground() for that service."
> — https://developer.android.com/about/versions/14/changes/fgs-types-required

> "If apps that target Android 14 use a foreground service, they must declare a specific permission, based on the foreground service type, that Android 14 introduces."
> — https://developer.android.com/about/versions/14/changes/fgs-types-required

Available types (same page): `camera`, `connectedDevice`, `dataSync`, `health`, `location`, `mediaPlayback`, `mediaProjection`, `microphone`, `phoneCall`, `remoteMessaging`, `shortService`, `specialUse`, `systemExempted` — plus the migration nudge: "If a use case in your app isn't associated with any of these types, we strongly recommend that you migrate your logic to use WorkManager or user-initiated data transfer jobs." Manifest shape (same page): declare `FOREGROUND_SERVICE` + the type-specific permission, and `android:foregroundServiceType="…"` on the `<service>` element.

### 6.2 Application to our sessions

Default posture (roadmap M4): **NO foreground service, NO flet-notifications** — sessions live while the app is foregrounded; screen switches keep sessions via in-app refcounting, not via FGS. This default requires no FGS declaration at all and is the lowest-review-risk option.

If M4 device testing shows sessions die unacceptably on screen-off/background (OEM task-killer behavior), the fallback is a foreground service with a persistent notification — which then triggers: (a) the type + permission declarations above (none of the 13 types names "terminal session"; closest candidates would be `specialUse` with a Play-Console declaration, or `dataSync` only if framed around transfers — **the correct type choice is UNVERIFIED and must be decided with the manifest in hand at M4**); (b) the `flet-notifications` patcher complication the roadmap already flags; (c) a Play "foreground service permission" declaration in App content. Decision point: M4 plan mode, informed by on-device background-kill evidence — not before.

---

## 7. Listing hygiene

### 7.1 Verified questionnaire items (S9)

> "Add your privacy policy to share how you treat sensitive user and device data."
> "Declare whether or not your app contains ads."
> "Receive content ratings from official rating authorities."
> "Tell us about your app's privacy and security practices."
> — https://support.google.com/googleplay/android-developer/answer/9859455 (App content checklist)

> "To prevent your apps from being listed as 'Unrated,' sign in to Play Console and fill out the questi[onnaire]…"
> — https://support.google.com/googleplay/android-developer/answer/9859455

Concretely for us: privacy-policy URL (§3.5); ads declaration = Yes (AdMob); content rating via the IARC questionnaire (a terminal that can fetch arbitrary internet content via apt/Docker Hub should be answered honestly — generic Linux shell with unrestricted network access; expect a teen-or-higher outcome depending on questionnaire answers — **the rating outcome itself is UNVERIFIED**, answer the questionnaire truthfully at M5); target-audience + data-safety + (if FGS chosen) FGS declarations.

### 7.2 Category, listing text, screenshots — UNVERIFIED specifics

No citable quote was pinned for: the exact category taxonomy (recommendation, not policy: **Tools** — label as judgment), store-listing text constraints for this category, or screenshot/graphic-asset rules. **Do not invent requirements here.** At M5, transcribe the live console requirements (character limits, required graphic sizes, feature-graphic rules) into this section with URLs. Drafting guidance only (judgment, not policy): name the app as a Linux-container utility, never as "Ubuntu/Debian on Android" in a way that implies endorsement (trademark care — M6 item; Ubuntu/Debian marks belong to Canonical/the Debian project — specific license texts **UNVERIFIED** in this pass); describe rootfs downloads as user-requested content; screenshots must show actual app UI (terminal + manager screens), never misleading system imagery.

### 7.3 "Install external apps" — we stay clear (S1)

> "Apps that install other apps on a device without the user's prior consent."
> — violation example, https://support.google.com/googleplay/android-developer/answer/9888379

Our flows install **zero APKs**: no `REQUEST_INSTALL_PACKAGES`, no sideload prompts, no APK bytes anywhere in the OCI/apt pipelines (§1.2–1.4). Container "install" means extracting a Linux tree into app-private storage — no Android package manager involvement. Confirm at the M5 manifest audit: the permission set stays `INTERNET` + `ACCESS_NETWORK_STATE` only (roadmap M5 scope; AdMob needs exactly these two — `docs/dependency-studies/flet-ads.md` §7), and no install-related permission or intent ever appears.

---

## 8. Precedent scan (live Play listings, fetched 2026-10-16)

All three category neighbors resolve live on `play.google.com` (meta-description taglines quoted from the fetched pages):

| App | Package (URL) | Live tagline (page `<meta name="description">`) | Positioning notes (observation, not policy) |
|---|---|---|---|
| UserLAnd | `tech.ula` — https://play.google.com/store/apps/details?id=tech.ula | "Run Linux on Android. No root required." | Closest architecture precedent: bundled proot + runtime-downloaded distros. Live = the single strongest datum for §1.2. |
| Termux | `com.termux` — https://play.google.com/store/apps/details?id=com.termux | "Terminal emulator and Linux environment." | The upstream of our wrapped `proot-distro` package; minimal tagline, utility framing. Note: main Termux distribution has partly moved off-Play (F-Droid/GitHub) over the years — **any claim about *why* is UNVERIFIED**; do not cite Termux history as policy evidence without a source. |
| Andronix | `studio.com.techriz.andronix` — https://play.google.com/store/apps/details?id=studio.com.techriz.andronix | "Linux on Android, fully automated: Ubuntu, Debian, Kali and desktops, no root." | Names the distros directly in the tagline (informative for our trademark-care drafting — they do it, but that does not make it risk-free; M6). |

**How to use this scan at submission time:** re-fetch all three before M5/M6 submission; if any has been removed or restricted, treat that as a signal to re-read §1 (a disappearance is weak evidence of enforcement — **UNVERIFIED** as to cause — but it changes our risk posture). **Policy notes on the precedents themselves: UNVERIFIED** — no public Play-side document explains individual app review outcomes; "live on Play" proves existence, not approval rationale.

---

## 9. Action checklist (milestone × owner)

Owner key: **repo config** = code/pyproject/workflow change in `github.com/Nwokike/proot-distro`; **console step** = human action in Play Console / AdMob console.

| # | Action | Milestone | Owner |
|---|---|---|---|
| A-1 | OCI-pull UX: explicit tap → progress + cancel + size; per-container delete/reset; offline bundled rootfs first-run | M3 | repo config |
| A-2 | `flet-proot` wheel via NDK r28+ with 16 KB ELF alignment; `target_arch` from what the index actually publishes | M2 | repo config |
| A-3 | Gate CI on `check_apk_alignment.py` printing `16K-OK` (≥0x4000) for every `lib/arm64-v8a/*.so`; record result in this doc | M5 (tool exists M0) | repo config |
| A-4 | Read `targetSdkVersion`/`minSdkVersion`/ABI set from CI-built AAB; assert target ≥ 36; record minSdk here | M5 | repo config |
| A-5 | ConsentManager UMP flow at launch + `can_request_ads()` gate + settings privacy-options entry; production-ID guard in CI; `reset()` never shipped | M3 (flow) / M5 (guard) | repo config |
| A-6 | Banner rows only on non-terminal screens, reserved + static; interstitials at natural breaks only; no ads on first launch | M3/M4 | repo config |
| A-7 | EEA verification: `DebugGeography.EEA` device sighting of the consent form before submission | M5 | repo config (device QA) |
| A-8 | Data safety form answers transcribed from Play SDK Index (Mobile Ads) entry; first-party = none; policy ↔ form consistency check | M5 | console step (+ policy text repo config) |
| A-9 | Privacy policy published at stable URL (repo `PRIVACY.md` page or kiri site) + in-app link; ads declared in App content; IARC questionnaire answered truthfully | M5 | repo config + console step |
| A-10 | Export-compliance declaration completed in-console; exact Q/A transcribed back into §5 with URL | M5 | console step |
| A-11 | FGS decision (default NO service) from M4 background-kill evidence; if YES: type + permissions + notification + console FGS declaration | M4 | repo config + console step |
| A-12 | Manifest audit: permissions stay INTERNET + ACCESS_NETWORK_STATE only; no install-related permission/intent (AAB inspection step — the FFmpeg-missing step, implemented for real) | M5 | repo config |
| A-13 | Release-notes finalize step + version-identity chain (fix FFmpeg drifts #2/#4 in our workflow, not inherited) | M5 | repo config |
| A-14 | In-app licenses screen + source links (GPL: proot GPL-2.0, libtalloc GPL-3.0, proot-distro GPL-3.0-only); Ubuntu/Debian trademark care; listing text review | M6 | repo config |
| A-15 | Play App Signing enrollment choice recorded (Google-generated vs transferred key); fallback-channel (F-Droid/GitHub) signing documented | M5/M6 | console step |
| A-16 | Precedent re-check (UserLAnd/Termux/Andronix live?) + policy-quote refresh of this doc before submission; 3-agent verification swarm per release ritual | M5/M6 | console step + repo ritual |

---

## Appendix A — verbatim quote bank (fetch date 2026-10-16; pages change — re-pull before submission)

- DNA core + interpreter clause + install clause: S1 (https://support.google.com/googleplay/android-developer/answer/9888379) — §1.1.
- Target API 36/35 schedule + Nov-1-2026 extension: S2 (https://support.google.com/googleplay/android-developer/answer/11926878) — §2.1.
- 16 KB mandate + ELF-alignment + PAGE_SIZE + `getconf` checks: S3 (https://developer.android.com/guide/practices/page-sizes) — §2.2.
- 64-bit mandate + ABI folders: S4 (https://developer.android.com/google/play/requirements/64-bit) — §2.4.
- FGS types + MissingForegroundServiceTypeException + per-type permissions: S5 (https://developer.android.com/about/versions/14/changes/fgs-types-required) — §6.1.
- Upload-key RSA-2048 + Google-signed APK stamps: S11 (https://support.google.com/googleplay/android-developer/answer/9842756) — §2.6.
- SDK data-safety responsibility + SDK Index pointer: S7 (https://support.google.com/googleplay/android-developer/answer/10787469) — §3.1.
- Privacy-policy link (console + in-app) + prominent disclosure: S8 (https://support.google.com/googleplay/android-developer/answer/10144311) — §3.1.
- App-content checklist (policy/ads/ratings/practices): S9 (https://support.google.com/googleplay/android-developer/answer/9859455) — §§3.5, 7.1.
- AAB single-bundle delivery: S10 (https://support.google.com/googleplay/android-developer/answer/113469) — §2.5.
- AdMob program policies + account/ad-serving jeopardy: S12 (https://support.google.com/admob/answer/6128543) — §4.1.
- Banner placement + floating-over-content ban: S13/S14 (https://support.google.com/admob/answer/6128877, https://support.google.com/admob/answer/6275345) — §4.2.
- UMP launch flow (`requestConsentInfoUpdate` → `loadAndShowConsentFormIfRequired`, API 21+): S15 (https://developers.google.com/admob/ump/android/quick-start) — §4.3.

## Appendix B — UNVERIFIED ledger (must resolve before first submission)

1. Reviewer acceptance of the "rootfs = user data" framing (§1.2) — settable only by submitting.
2. ~~M0 APK 16 KB-alignment claim~~ — **RESOLVED 2026-10-16**: CI evidence recorded in `docs/m0-checklist.md` §"CI evidence — APK alignment" (all libs `0x4000` (16K-OK), run 38906734815 onward). Keep gating in M5.
3. AdMob's own data-safety declared types — transcribe from Play SDK Index at M5 (§3.3).
4. Export-compliance Q/A + exemption wording — complete in-console at M5 (§5).
5. FGS type choice if sessions need persistence (§6.2).
6. minSdk floor value; "AAB required for new apps"; category/screenshot/text rules; IARC outcome; Termux off-Play history; precedent-removal causality (§§2.3, 2.5, 7.1, 7.2, 8).
