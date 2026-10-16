# app-ddgs.md — DDGS

Verified 2026-10-16 against `C:\Users\nwoki\.zcode\workspace\default\DDGS`.

## Identity
`DDGS` (no Kiri prefix), Python 3.12. Wraps `ddgs>=9.16.0` (locked 9.16.0) + `kani[openai]` (fetched live router; never vendored).

## Dependencies — the "honest import" discipline (copy verbatim)
11 runtime deps, each carrying a justification comment: `httpx`/`certifi`/`idna`/`openai`/`tiktoken` are declared because the app imports them directly even though they're already transitive (`already a base flet dependency`, `already kani[openai]'s own requirements`). Two hard-won Android rules in comments:
- **`lxml>=6.1.1` ceiling rule**: pypi.flet.dev tops out at lxml 6.1.1 — never raise the floor past the Android ceiling or only the APK job dies.
- **`primp` floor = ddgs' own requirement** so the two can't diverge (anti-bot browser profiles).
- Dev group keeps `flet[cli,desktop]==1.0.3` OUT of `[project]` so `flet build` never resolves desktop packages for Android.

## Guard tests (copy both)
- `tests/test_imports_vs_deps.py` — every third-party import in `src/` must resolve to a declared `[project]` dependency (imports crash on Android when undeclared).
- `tests/test_version_discipline.py` — version consistency across pyproject/constants/workflow/version.json; feed may lag (`held back`) but never lead.

## Wrapping pattern
Thin `SearchService` around `ddgs` (direct import, graceful ImportError fallback, upstream exceptions mapped), one shared proxy/SSL helper (`net_clients.py`). **Cautionary tale**: `src/services/youtube/*` (608 lines of hand-rolled InnerTube + JS-cipher solver with an embedded key) exists because upstream rate-limits — exactly the "second engine" the owner does NOT want to maintain. The single true upstream patch: `_DDGSClass.threads = state.threads` (process-global class mutation).

## CI/release
Single workflow: quality (playstore-branch divergence gate — exactly two files may differ; version-consistency script; ruff; pytest) → `prepare-release` (tag or `build-<sha>`; **every release stays prerelease + make_latest=false; promotion is an explicit `gh release edit`**) → apk-split (wheel pre-compile for primp/ddgs), windows (Inno), linux (fpm deb/rpm). AAB lives only on the `playstore` branch.

## Transferable
Floor-pin style; honest-import comments + test; minimal `[tool.flet]` set (org/product/company/build_number, app.path, android bundle_id/perms/meta_data/signing, splash, gradle jvmargs cap) is sufficient for signed split-APK + desktop + linux; prerelease-always release model.
