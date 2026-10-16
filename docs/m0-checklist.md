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
