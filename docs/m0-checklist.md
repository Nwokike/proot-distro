# M0 checklist — device spike (go/no-go)

**Build:** `.github/workflows/m0-spike.yml` → prerelease `spike-<run#>` (APK attached) or the Actions artifact.
**Install:** sideload the `arm64-v8a` APK (throwaway CI keystore; allow install from unknown sources).
**Run:** open the app → tap **Run ALL (G1–G4)** → then **Start session** (G5) → **G6 export report**.
**Report back:** screenshots of the log + the G6 report text (or the file from the app documents dir).

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
