# Request record (filed on flet-dev/python-build, 2026-10-16)

**Title:** Android: ship stdlib `grp` module (Termux-style getgrent stub) — needed by proot-distro in Flet container apps

**Body:**

**Request:** build `grp` into the Android CPython (all ABIs, 3.12 + 3.13+), so `import grp` works in serious_python apps.

**Context:** I maintain a Flet Android app that wraps [proot-distro](https://github.com/termux/proot-distro) (Linux containers on-device; related package request: flet-dev/flet#discussions/6979). `proot-distro` does `import grp` + `import pwd` unconditionally in `proot_distro/helpers/rootfs.py` and calls `pwd.getpwuid(uid).pw_name` / `grp.getgrgid(g).gr_name` when registering Android uid/gid entries into a container's `/etc/passwd`/`group`. On the Flet Android runtime (CPython 3.14) this fails: `ModuleNotFoundError: No module named 'grp'`.

**Why it's missing (verified):** CPython gates the module in `configure.ac`:

```
PY_STDLIB_MOD([grp], [], [test "$ac_cv_func_getgrent" = "yes" && { test "$ac_cv_func_getgrgid" = "yes" || test "$ac_cv_func_getgrgid_r" = "yes"; }])
```

Bionic only provides `getgrent`/`setgrent`/`endgrent` since **API 26** (`__INTRODUCED_IN(26)` in `grp.h`; `getgrgid_r` has been there since API 24), while `flet-dev/python-build` targets `api_level=24`. On the 3.12 legacy flow the repo additionally forces it off via `android/patches/grp.patch` (`Linux-android) py_cv_module_grp=n/a`, inherited from Chaquopy: "we can't build the grp module, because getgrent and setgrent aren't available until API level 26"). On 3.13+ the exclusion happens naturally at the configure gate. `Doc/library/grp.rst` documents "not Android"; note `pwd` is *not* Android-excluded and appears to build fine.

**Precedent — Termux ships `grp`:** they hit the identical regression on their 3.12→3.13 upgrade (termux/termux-packages#28684, `ModuleNotFoundError: No module named 'grp'`) and fixed it (PR termux/termux-packages#28768) by forcing `ac_cv_func_getgrent=yes` in `packages/python/build.sh` plus an NDK header patch (`ndk-patches/30/grp.h.patch`) that replaces the API-26 declarations with inline stubs:

```c
static struct group* _Nullable getgrent(void) { return 0; }
static void setgrent(void) {}
static void endgrent(void) {}
```

Result: real `getgrgid`/`getgrnam` through Bionic (working since API 24), while `getgrall()` returns `[]`. Chaquopy, Kivy's python-for-android, and Kodi instead treat `grp` as unsupported — Termux is the working counterexample.

**Ask:** adopt the Termux approach for the Android target: keep min-API 24, but ship `grp` with a `getgrent`-family fallback (build-time stub + `ac_cv_func_getgrent=yes`, or an equivalent in `Modules/grpmodule.c`) so `getgrgid`/`getgrnam` work and `getgrall()` degrades to `[]` on API 24–25. Ideally also drop/replace `android/patches/grp.patch` on the 3.12 flow accordingly.

I can test a pre-release build on-device immediately (`import grp; grp.getgrgid(os.getgid())` under Android 16, arm64-v8a). Meanwhile my app ships a 20-line `sys.modules` shim for the two calls proot-distro makes, so this is a durability request, not a blocker for me.

Posted: https://github.com/flet-dev/python-build/issues/45 (2026-10-16)
