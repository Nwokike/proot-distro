# M0 checklist — device spike (go/no-go)

**Build:** `.github/workflows/m0-spike.yml` → prerelease `spike-<run#>` (APK attached) — CI-only, signed with the **house kiri keystore** (alias `upload`; secrets wired 2026-10-16).
**Install:** sideload the `arm64-v8a` APK (allow install from unknown sources).
**Run:** open the app → tap **Run ALL (G1–G4)** → then **Start session** (G5) → **G6 export report**.
**Report back:** screenshots of the log (activity-terminal, timestamped) + the G6 report text (or the file from the app documents dir).

## Desktop pre-run (2026-10-16, Windows — informational, superseded by the device run)
Owner pressed all buttons in a local `flet run` session:
- G0 storage dirs + activity-terminal log render ✓ (timestamps visible), G6 report file written ✓
- G1b `sys.executable -c` → `spawn-ok` ✓ (desktop; Android must still be proven)
- G1/G3/G5 correctly refuse with "no nativeLibraryDir" (desktop has none) ✓
- G2/G4: `proot-distro` refuses to import on Windows (`os.O_DIRECTORY` — POSIX-only) → now reported with a friendly Linux-only message ✓

Record results below (one row per gate). Evidence: exact log excerpt + device model + Android version.

| Gate | What it proves | Result | Evidence |
|---|---|---|---|
| G0 bootstrap | Environment integrity: nativeLibraryDir found, runtime libs staged (libtalloc.so→libtalloc.so.2), LD_LIBRARY_PATH set, TracerPid=0 | | |
| G1 exec | `nativeLibraryDir/libproot.so --version` executes (W^X/execve path with legacy_packaging) | | |
| G1b spawn-probe | `sys.executable -c` works → CLI-subprocess route viable for login/structured exec | | |
| G2 install alpine | In-process `proot-distro` OCI install (Docker Hub pull, digest verify, tar extract) works on Android | | |
| G3 one-shot | Guest exec through proot loader (mmap-exec): `id; uname -a; /etc/os-release` in alpine | | |
| G4 install debian | OCI pull debian:bookworm (network path, bigger layers) | | |
| G4 apt cowsay | `apt-get update && apt-get install cowsay` + run → **loader mmap-exec of newly written guest binaries** (the load-bearing claim) | | |
| G5 session | Long-lived interactive shell in flet-terminal: typing, output streaming, Ctrl-C, `exit` → decides spawn port (Python vs Dart) for M1 | | |
| G6 export | Report file written to app documents | | |

## Device run #3 (2026-10-16 · Android 16 aarch64 · spike-6) — evidence
- **G0/G1/G2 ✓** — probe again ({'pwd': True, 'grp': False}), pty OK, alpine install 5.5s.
- **G3 ✓ FULL GREEN** — `rc=0`, `uid=0(root)`, `groups=3003(aid_3003),9997(aid_9997),20322(aid_20322),50322(aid_50322)` (shim `getgrgid` live), Alpine 3.21.8 `os-release`, real kernel line. **PATH env fix verified.**
- **G4-install ✓** 16.3s; **G5 ✓** session with controlling tty — owner screenshots show a working shell: coloured `ls`, `cd`, full `/bin` busybox listing, live prompt.
- **G4-apt ✗ rc=100 — LAST blocker, root-caused:** dpkg `unable to make backup link of './usr/bin/perl' … Permission denied` + `error creating new backup file '/var/lib/dpkg/status-old'` = **`link()` denied by Android SELinux for apps**. Fix (spike-8): adopt proot-distro's Termux-mode extensions one-to-one (`proot_cmd.py::_add_proot_extensions`): `--link2symlink` + `-L` (their comment: "Fix lstat for dpkg symlink warnings") + `--kill-on-exit` + `--sysvipc` + formatted `--kernel-release`, and pin `PROOT_L2S_DIR=<rootfs>/.l2s` (their l2s.py:70-71). All flags verified in proot 5.1.107.96 `src/cli/proot.h`.

## CI evidence — APK alignment (recorded 2026-10-16, at play-policy verification request)
Every CI build runs the "Inspect APK (payload presence + 16K alignment)" step (`tools/check_apk_alignment.py`; moved from `m0-spike/tools/` and made **enforcing for the flet-proot payload libs** in M2 — a missing payload lib or any PT_LOAD < 0x4000 now fails the build; stdlib libs stay report-only). First green run **38906734815** (repeated every build since, incl. spike-8/9) printed:

```
lib/arm64-v8a/libproot.so           align=0x4000 (16K-OK) soname=None
lib/arm64-v8a/libproot-loader.so    align=0x4000 (16K-OK) soname=None
lib/arm64-v8a/libtalloc.so          align=0x4000 (16K-OK) soname=libtalloc.so.2
lib/arm64-v8a/libandroid-shmem.so   align=0x4000 (16K-OK) soname=None
(+ every CPython stdlib lib_*.so in lib/arm64-v8a: all 0x4000 (16K-OK))
```

So: **the M0 APK's native libs ARE verified 16 KB-aligned** — `0x4000` satisfies Play's 16 KB page requirement for targetSdk ≥35. The step also fails the build if `libproot.so` is missing from jniLibs. M2 keeps the NDK r28+ rebuild requirement for the production `flet-proot` wheel; M5 keeps gating releases on this step's output.

## Device run #2 (2026-10-16 · Android 16 aarch64 · spike-5) — evidence
- **G0 ✓ (device truth)** — `posixdb probe: {'pwd': True, 'grp': False}` → only `grp` shimmed (settles the pwd question: pwd EXISTS on Android); `pty: posix-pty available (openpty OK)`; nativeLibraryDir + staged `libtalloc.so -> libtalloc.so.2` confirmed again.
- **G1 ✓** — proot exec again, `process_vm = yes, seccomp_filter = yes`.
- **G2 ✓ `OK in 7.4s`** — alpine:3.21 installed IN-PROCESS via proot-distro (OCI pull + extract) — including "Registering Android-specific UIDs and GIDs" = **the grp shim worked on-device**.
- **G4-install ✓ `OK in 40.1s`** — debian:bookworm installed (46.2 MiB layer).
- **G5 ✓ (first true interactive shell)** — PTY session; owner's screenshot shows a live `#` (fake-root) prompt and working keystrokes; `sh` loaded from the rootfs = **proot loader mmap-exec on Android proven end-to-end**. ("can't access tty; job control turned off" → fixed in spike-6 via setsid+TIOCSCTTY preexec.)
- **G3/G4-apt ✗ rc=127 (`id/ls/apt-get: not found`)** — root cause: the guest inherited the app's Android PATH (our minimal spawn bypasses proot-distro's env building). Fix in spike-6: `guest_env()` — one-to-one with `constants.py DEFAULT_PATH_ENV` + `_build_normal_env` HOME/USER/TERM, merged over the host essentials proot needs (LD_LIBRARY_PATH/PROOT_LOADER/PROOT_TMP_DIR).

## Device run #1 (2026-10-16 · Android 16 aarch64 · spike-3) — evidence
- **G0 ✓** — nativeLibraryDir found; `staged runtime libs: ['libtalloc.so -> libtalloc.so.2']`; `PD_PROOT_BIN` + `LD_LIBRARY_PATH` set; `TracerPid=0`; uid=10315.
- **G1 ✓✓ (the go/no-go) — `libproot.so --version` EXECUTES from nativeLibraryDir**: `rc=0`, prints `proot 5.1.107.96`, `built-in accelerators: process_vm = yes, seccomp_filter = yes`. **The W^X/jniLibs/legacy-packaging architecture is proven on real hardware.**
- **G1b ✗ (by design) — `sys.executable` is `/system/bin/app_process64`** (the Flutter host), spawn → `rc=-6`, "Error changing dalvik-cache ownership". The CLI-subprocess route via sys.executable is NOT viable → design: in-process library APIs + direct proot spawn (as planned).
- **G2/G4 ✗ → FIXED in spike-4** — `ModuleNotFoundError: No module named 'grp'`: CPython's Android port excludes `grp` (PEP 738 unsupported list) while proot-distro imports it unconditionally (`helpers/rootfs.py:42`). Fix: `src/posixdb.py` platform shim (installs only the missing module; probe logged). `pwd` is NOT in PEP 738's list — device probe will confirm.
- **G3/G4-apt/G5** — blocked downstream of G2 in this run (no rootfs yet); expected to proceed once G2 passes.
- **FletTerminal renderer error (owner-visible)** — `MobileTerminal()` raises `RuntimeError: No current renderer is set…` (flet/components/utils.py:31) outside a `@ft.component` tree; reproduced locally. spike-4 uses the plain `Terminal` control; M1 refactor item recorded in `reference/dep-flet-terminal.md`.

## Device retests #4+ — the apt-cowsay bug (G4) investigation arc
Recorded 2026-10-16 from the fix commits + CI releases (older spike release pages have since been pruned; commits are the durable record). Each retest re-ran **Run ALL** on the house device (Android 16 aarch64); only deltas listed.

- **Retest #4 — dpkg backup-link failure (fix shipped in spike-8, commit 95193d5).**
  Observed on the previous build: `apt` in guest Debian failed with dpkg `unable to make backup link of './usr/bin/perl'` + `error creating new backup file '/var/lib/dpkg/status-old'` = Android SELinux denies app-side `link()`. Fix (one-to-one with `proot_cmd.py::_add_proot_extensions`): `--link2symlink` + `-L` + `--kill-on-exit` + `--sysvipc` + formatted `--kernel-release`, and `PROOT_L2S_DIR=<rootfs>/.l2s` (l2s.py:70-71). Result: **backup-link error gone — NEW failure surfaced at the next chown step.**
- **Retest #5 — the open bug: chown ENOENT on `.dpkg-new` (fix attempted in spike-9, commit af29b0d).**
  Failure: `error setting ownership of '/usr/bin/perl5.36.0.dpkg-new': No such file or directory` (dpkg hardlink entry does `link()` → link2symlink substitutes a symlink → the follow-up `chown()` resolves through the l2s-parked path and gets ENOENT). **Upgrade-over-existing packages only** — fresh installs work. spike-9 attempt: full proot-distro binds (`/dev`, `/proc`, `/sys`, stdio fds), rootfs `tmp/` bind for `/dev/shm` (chmod 1777), `PROOT_F2FS_WORKAROUND=0` toggle. Result: **did NOT fix the chown ENOENT.**
- **Termux ground truth (owner control run, in Termux's own Debian).** `apt-get install`/upgrade path works in Termux; `--get-proot-cmd` output captured and compared: the real session argv uses `--change-id=0:0`, `<rootfs>/tmp:/dev/shm`, and explicit stdio binds. (Termux also ships a `proot` build with more Termux patches — noted, not usable as a drop-in.)
- **Retest #6 — spike-10 (commit 4630063): Termux argv adopted one-to-one + workaround + probe. CI ✅; device retest FAILED; LOOP DEFERRED (D-011).**
  Changes: session argv now matches the Termux capture exactly (`--change-id=0:0`, `<rootfs>/tmp:/dev/shm`, `/dev/urandom:/dev/random`, `/proc/self/fd` stdio binds, `--cwd=/root`); G4's apt step runs with `--no-upgrade` (avoids the broken upgrade path); **new G4b probe** (`--only-upgrade perl-base`) isolates and re-confirms the upgrade bug on-device; new D0 diagnostics gate (host `.l2s` listing, perl leftovers, guest `readlink`s). CI run **38939581051** green (all 11 steps, incl. APK payload + 16K alignment inspection); APK published: release **`spike-10`** → `m0-spike-arm64-v8a.apk` (2026-10-16 17:32 UTC).
  Device result (owner report 2026-10-16): **still failing** — exact gate outputs not captured in the message (G4 and/or G4b). Per owner ruling (D-011 in `docs/decisions.md`): the retest loop is **closed until after M1–M6**; resume with the recorded recipe (install spike-10 → Run ALL → capture the G4 + G4b log text + owner Termux control #2). M0 remains non-blocking: G1/G2/G3/G5 are green on-device; only apt-**upgrade-over-existing** is open, workaround `--no-upgrade`.

## Failure triage (if a gate is red)
1. Re-run the gate once (transient network for G2/G4).
2. In-app log already contains `rc=`, stderr tails, and tracebacks — screenshot it.
3. If G1/G3/G5 fail with exec/SELinux symptoms: on a PC run
   `adb logcat | grep -iE "avc|denied|proot|libproot|linker"` while tapping the gate; attach the output.
4. Fallback experiments if exec is denied: (a) `/system/bin/linker64 <libproot.so> …`; (b) check `gnu-variant`/page-size of the device (`getconf PAGE_SIZE`).

## After results
- Update this file with pass/fail + evidence.
- `docs/decisions.md`: close O-3 (spawn port), annotate O-7 (zstd) and O-8 (Termux-masquerade) with device evidence.
- If G1–G4 green: proceed to M1 (flet-terminal refactor) plan mode.
