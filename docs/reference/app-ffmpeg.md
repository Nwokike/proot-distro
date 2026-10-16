# app-ffmpeg.md — FFmpeg Lite (native-shipment reference)

Verified 2026-10-16 against `C:\Users\nwoki\.zcode\workspace\default\ffmpeg`. **The closest sibling to this app** because it ships native code through the same Forge pipeline.

## Identity
"FFmpeg Lite" v1.0.0 build 1, bundle `ng.kiri.ffmpeg`. Wraps **PyAV `av==18.1.0` → FFmpeg 8** via the Forge-built `flet-libffmpeg` wheel; flet family pinned exactly (`flet==flet-ads==flet-audio==...==1.0.4`) with the reason in-comment: "audited against one exact Flet/PyAV wire contract — a minor framework release can change component constructors and event semantics".

## Native shipment (the shape we mirror for libproot)
- **Two-artifact split**: Python wheel (`av`) from PyPI + native-libs wheel (`flet-libffmpeg`) from pypi.flet.dev. Desktop/dev resolves PyPI (manylinux/macOS wheels); **Android native wheels resolve at `flet build` time from the Forge index — no `extra-index-url` needed in pyproject; flet-cli/serious_python inject it**.
- `extract_packages = ["av"]` — load-bearing **only because PyAV loads its bundled libs through `__file__` paths**; rule: add the package owning a `.so` load path only if it uses filesystem paths (zipimport breaks), not if it uses `importlib.resources`.
- `target_arch = [arm64-v8a, x86_64, armeabi-v7a]` + `split_per_abi = true`; in-comment lesson: **never copy a sibling's ABI note — derive from what the index actually publishes**.
- `flet-libffmpeg` is built WITHOUT `--enable-gpl` → probe-gating: `src/core/engine_probe.py` measures REQUIRED/OPTIONAL filters + encoders from the installed wheel; screens intersect probe results and never show what the engine can't do.
- `[tool.flet.flutter.pubspec.dependency_overrides] jni = "^1.1.0"` — workaround "until 1.0.4 ships (Flet PR #6920)"; **the 'until' has passed — verify removal on a CI branch; never copy blind**.

## CI (quality gate worth copying wholesale)
`uv sync --frozen` → ruff check+format → `pytest -m "not live"` → version-identity script → **AdMob production-ID guard (fails tags if test IDs present)**; then placeholder release; then apk-split (wheel pre-compile + keystore decode + size report + prune verification), aab, windows (Pillow ICO + Inno Setup), linux (fpm deb/rpm + desktop entry + AppStream metainfo). Keystore strictly via `FLET_ANDROID_SIGNING_*` secrets.

## Drifts found (fix in OUR app, don't inherit)
1. `pinned-deps.txt` referenced in pyproject but doesn't exist.
2. **`version.json` is gitignored yet CI's identity script opens it unconditionally → fresh checkout would fail** — track a template or tolerate absence.
3. README badge says Flet 1.0.1 while pins say 1.0.4.
4. **No release-notes finalize step** — the placeholder release body is never replaced (Sherlock has the same gap).
5. Runbook promises an AAB `minSdk`/versionCode inspection step that **doesn't exist in the workflow** — implement it for real in ours (assert `libproot.so` ABI floor).
6. Linux packaging symlinked `/usr/bin/ffmpeg` — never shadow a system binary name; use a unique name.

## Transferables for proot-distro
Mirror the two-artifact Forge shape; probe-gating analog (`proot_probe`: binary present/executable, arch, rootfs writability); exact-pin flet family; lockstep identity chain pyproject→constants→version.json→changelog; the CI skeleton (but add the missing finalize + floor-inspection steps); `split_per_abi` + per-ABI size reporting.
