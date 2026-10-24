# src/core/changelog.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/core/changelog.py` (18 lines) · `src/components/update_dialog.py` (162 lines, consumer) · `src/core/constants.py:11` (`APP_VERSION = "1.0.0"`) · `tests/test_version_sync.py:29-31` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/changelog.py` defines `CHANGELOG: dict[str, str]` mapping a version string to a block of release notes (currently only `"1.0.0"`, lines 5-13) and `notes_for(version)` (lines 16-18), which returns the exact entry or a fallback. The sole caller is `src/components/update_dialog.py:89` (`notes_for(APP_VERSION)`), rendered inside the "You're up to date" dialog (lines 83-100) through `ft.Markdown(..., extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)` (lines 88-93). `tests/test_version_sync.py:29-31` asserts the current version has an entry and that `notes_for(APP_VERSION)` is truthy.

---

## Findings

### F1 · P2 · `notes_for()` falls back to the oldest entry, contradicting its docstring
- **Where:** `src/core/changelog.py:16-18` (`"""...falling back to the newest one."""` / `return CHANGELOG.get(version) or next(iter(CHANGELOG.values()), "")`) · consumer `src/components/update_dialog.py:89` · guard `tests/test_version_sync.py:29-31`
- **What:** `next(iter(CHANGELOG.values()))` returns the first-inserted value. Dicts preserve insertion order and the literal (lines 5-13) is written oldest-first, so the fallback returns the *oldest* release's notes, not the newest. Today it is masked because `CHANGELOG` has one key and `APP_VERSION == "1.0.0"` (`src/core/constants.py:11`), so the `.get()` hit path is taken; the fallback is never exercised. `tests/test_version_sync.py:29-31` only checks the hit path.
- **Evidence:** installed Python 3.14 semantics: `next(iter({"1.0.0": "old", "1.0.1": "new"}.values())) == "old"`. Confirmed by prior swarm audits (`docs/swarm/dependency-utilization/packaging.md`, `markdown-it-py.md`, `python-dateutil.md`).
- **Fix / opportunity:** make the fallback numeric/newest, e.g. `max(CHANGELOG, key=lambda v: tuple(int(p) for p in v.split(".")))` then `CHANGELOG[newest]`, or reverse insertion order. Add a test pinning `notes_for("99.0.0")` to the newest entry.
- **Risk if ignored:** after the next release, a version with no exact entry shows stale "What's New" notes labelled as the current build's.

### F2 · P2 · Bundled changelog is plain text rendered as Markdown (line breaks collapse; bullets are not list syntax)
- **Where:** `src/core/changelog.py:7-11` (plain `"• ..."` lines joined by `"\n"`) · `src/components/update_dialog.py:88-93` (`ft.Markdown(notes_for(APP_VERSION), ..., extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)`) · installed `flet/controls/core/markdown.py:980` (`soft_line_break: bool = False`) and `:940` (`value: str`)
- **What:** The bundled notes use single `"\n"` between bullet lines and a literal `"•"` instead of Markdown list syntax. With `soft_line_break=False` (default, verified `.venv/.../markdown.py:980`), a single newline is a soft break and collapses to a space, so the bullets render as one paragraph rather than a list. Remote release notes (update mode, `update_dialog.py:67-74`) are expected to be real Markdown; the bundled path is not.
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/controls/core/markdown.py:940` (`value: str = ""`) and `:980` (`soft_line_break: bool = False`); `extension_set` default `NONE` (line 950) but app passes `GITHUB_WEB` (line 91).
- **Fix / opportunity:** either convert the bundled text to Markdown lists (`- ` lines) and/or set `soft_line_break=True` on the bundled `ft.Markdown` (update_dialog.py:88), or render the bundled notes with `ft.Text` instead of `ft.Markdown`. Keep remote notes as Markdown.
- **Risk if ignored:** "You're up to date" dialog shows a run-on paragraph instead of a bulleted list (user-visible formatting defect). Runtime rendering outcome is UNVERIFIED (no widget test).

### F3 · P3 · Changelog data shape is unvalidated and version-parsing is stringly
- **Where:** `src/core/changelog.py:5` (`CHANGELOG: dict[str, str]`) · `src/core/changelog.py:16` (`notes_for(version: str)`) · `tests/test_version_sync.py:29-31` (only membership + truthiness)
- **What:** Keys are arbitrary strings; there is no PEP 440 / tuple version parsing, no ordering invariant, and no check that the highest key equals `APP_VERSION`. `update_service._release_tuple` (`src/services/update_service.py:33-39`) does parse versions for the feed, but the bundled changelog path does not reuse it. A typo'd or non-numeric key would silently become the "newest" under any numeric-max fix.
- **Evidence:** `src/services/update_service.py:33-39` (`_release_tuple`); `src/core/changelog.py:5,16`.
- **Fix / opportunity:** add a CI/test guard asserting keys are strictly increasing dotted-numeric versions and the max equals `APP_VERSION` (consistent with `tests/test_version_sync.py`); optionally reuse `_release_tuple` for the fallback. No runtime dependency needed.
- **Risk if ignored:** future release could ship mismatched changelog/version with no failure.

### F4 · P3 · Bundled notes are not Markdown, but are passed to `ft.Markdown` (API mismatch)
- **Where:** `src/core/changelog.py:7-11` (plain text) · `src/components/update_dialog.py:88-93` (`ft.Markdown(..., selectable=True, extension_set=..., on_tap_link=...)`)
- **What:** `ft.Markdown` (`.venv/.../markdown.py:927-928`, `@control("Markdown")`, `LayoutControl`) expects Markdown in `value` (line 940). The bundled value contains no Markdown constructs; `on_tap_link` (line 1031) is wired but the bundled text has no links, so it is dead for this path. Not a crash (guard passes), but a semantic mismatch.
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/controls/core/markdown.py:927-928,940,1031`; guard run `.venv/bin/python tests/check_flet_api.py src/components/update_dialog.py` → `OK` (25 chains).
- **Fix / opportunity:** either make the bundled text real Markdown or render it with `ft.Text`/`ft.Column` of `ft.Text` bullets. Keep `ft.Markdown` for remote `release_notes`.
- **Risk if ignored:** formatting/link affordances behave inconsistently between the two dialog modes.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-file audit, not a dependency audit. No new packages proposed (D-003). Note: version comparison could reuse the already-shipped `packaging` only in CI/build, not in `src/` (runtime), per `docs/swarm/dependency-utilization/packaging.md`.

---

## Verified-good list

1. `ft.Markdown` and all chains used in `update_dialog.py` exist in installed flet 1.0.4 with matching names: `ft.Markdown` (`.venv/.../controls/core/markdown.py:927`), `ft.MarkdownExtensionSet.GITHUB_WEB` (line 46), `selectable` (line 945), `extension_set` (line 950), `on_tap_link` (line 1031) — guard run above returned `OK`.
2. `ft.Markdown.value` is `str` (line 940); `notes_for` returns `str` (changelog.py:16-18) — type-compatible.
3. `CHANGELOG` is a module-level `dict[str, str]` and `notes_for` returns `""` default when empty (`next(iter(...), "")`) — no `None` leak into `ft.Markdown.value`.
4. `is_allowed_launch_url` gating (`services/update_service.py:12-24`) and `_launch` (update_dialog.py:23-27) protect `on_tap_link` launches; bundled path has no links so it is inert but safe.
5. `tests/test_version_sync.py:29-31` guarantees the shipped version has an entry, so the F1 fallback is latent, not live, today.
6. No imperative widget mutation / no `page.update()` in changelog.py or update_dialog.py (D-015 respected); dialog uses `page.show_dialog`/`page.pop_dialog`.

---

## Unverified

1. Whether `soft_line_break=False` (default, markdown.py:980) actually collapses the bundled `"\n"` bullets at render time in the Flutter client — inferred from the property semantics; no widget test exercises it. Labeled UNVERIFIED.
2. Whether remote `release_notes` are genuinely Markdown in the feed — not checked here (feed absent in clean clone per test skip).
3. Whether a second changelog entry will be appended oldest-first or newest-first at the next release — convention unenforced; F3 covers it.