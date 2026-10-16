# Package request (filed on flet-dev/flet Discussions → Packages, 2026-10-16)

**Title:** Package request: `proot` (Android arm64/x86_64) — native binary for a Termux-free Linux-containers Flet app

**Body:**

**What I'm building:** a Flet Android app that wraps upstream [proot-distro](https://github.com/termux/proot-distro) v5.x to run Debian/Ubuntu/Alpine — any Docker/OCI image — on phones, with an interactive shell via my `flet-terminal` control, and **no Termux layer**. proot-distro is now pure Python (`proot-distro` on PyPI, `py3-none-any`, zero runtime dependencies), so the app's only dependency outside the usual flet set is the **`proot` binary itself**. Today that binary only ships through Termux — which is exactly the layer this app removes.

**Why it can't ride in as a normal data file:** since Android 10, apps targeting API ≥ 29 cannot `execve()` binaries in app-data dirs (W^X / SELinux `app_data_file` rule). The only sanctioned exec path for non-Play-update code is the APK **native library directory**, so the binary must land in `lib/arm64-v8a/` at build time. This is exactly what Play Store Termux and UserLAnd do in production today.

**The request:** a mobile-forge recipe (e.g. `flet-proot`) cross-building the Termux proot fork for Android:

- payload → `opt/lib/libproot.so`, `opt/lib/libproot-loader.so` (the unbundled loader, `PROOT_UNBUNDLE_LOADER`), `opt/lib/libtalloc.so`, `opt/lib/libandroid-shmem.so` — the existing `copyOpt_<abi>` step (`opt/**/*.so` → jniLibs) then does the rest, exactly like `flet-libmagic`/`flet-libffmpeg` do for their shared libs.
- ABIs: `arm64-v8a` + `x86_64` primary (armeabi-v7a welcome; ARMv9 cores dropped 32-bit EL0).
- toolchain: NDK r28+ for 16 KB page alignment (Play requirement for targetSdk 35+).
- upstream: `termux/proot` v5.1.107.96 (GPL-2.0); build flags verified from `termux-packages/packages/proot/build.sh`: `PROOT_WITH_LIBANDROID_SHMEM=true`, `PROOT_UNBUNDLE_LOADER=.../libexec/proot`, deps `libtalloc` (GPL-3.0) + `libandroid-shmem`. Prebuilt ARM `.deb`s exist at `packages.termux.dev/apt/termux-main/pool/main/p/proot/`.

I've verified the app side already works with `[tool.flet.android].legacy_packaging = true` (extracts `.so` files to `nativeLibraryDir`, exposed to Python as `ANDROID_NATIVE_LIBRARY_DIR`), and proot's own loader mmaps guest binaries (mmap `PROT_EXEC` of app-data files remains allowed), so `apt install` inside the container should work at targetSdk 36 — pending on-device verification, which I can do and report back.

Is this acceptable for pypi.flet.dev / mobile-forge? Happy to open the recipe issue there and/or contribute the `build.sh` plus test builds. The fallback if it's out of scope: I publish platform-tagged wheels from my own CI — but the official forge makes it a clean one-line dependency for every Flet app that wants a real Linux userspace on Android.

Posted: https://github.com/flet-dev/flet/discussions/6979 (2026-10-16)
