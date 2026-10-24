# tests/test_ui_reactive.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_ui_reactive.py · src/screens/views.py · src/screens/terminal_view.py · src/screens/onboarding_view.py · src/screens/__init__.py · .venv/lib/python3.14/site-packages/flet/components/component.py · .venv/lib/python3.14/site-packages/flet/core/theme.py equivalent (src/core/theme.py) · src/components/app_header.py · src/components/brand_hero.py · src/app_shell.py · Date: 2026-10-24

## What it does / how the app uses it

Offline render contract for the state-driven shell. Guards that (a) the `@ft.component` views (AppShell, DistroView, SettingsView, TerminalView, OnboardingView) construct inside a Flet renderer context without RuntimeError, (b) brand hero / theme toggle icons resolve per theme mode, (c) licenses view ships compliance content and real license text, (d) theme mode resolution works with no page bound (terminal-native dark default), and (e) a source-level regex guard forbids imperative control mutation in `src/screens/*.py`. Runs under `pythonpath = ["src"]` (pyproject.toml:87).

Empirical result: `pytest tests/test_ui_reactive.py` → **8 passed, 2 failed**. Both failures are the license tests, because `src/LICENSES` is deleted (verified by `ls` and by the test's own assertion at test_ui_reactive.py:182).

## Findings

### F1 · P0 · Renderer.render_component does NOT execute component bodies — the D-015 render gate is void (false confidence)
- **Where:** `tests/test_ui_reactive.py:43-45` (`_render` helper) calls `Renderer().render_component(fn, (), {})` only; `.venv/.../flet/components/component.py:476-522` (`Renderer.render_component`) builds a frozen `Component` wrapper and returns it — `fn` is never invoked there. The component body is executed only later in `Component.update()` (component.py:146: `Renderer(self).render(self.fn, ...)`) and `Component.before_update()` (component.py:194), neither of which `_render` calls.
- **What:** `test_views_construct_in_renderer_context` (test_ui_reactive.py:48-56) and `test_state_changes_rerender_without_frozen_errors` (test_ui_reactive.py:99-118) pass trivially: they construct `Component` wrappers for `AppShell`, `DistroView`, `SettingsView` but never run a component body or trigger a re-render. Mutating `state` before `_render` (test_ui_reactive.py:103-118) has no effect on the outcome because nothing calls `update()`. The D-015 ruling (decisions.md:52) that "the components are constructed + re-rendered inside a renderer context in tests, so the bug class cannot silently return" is only half-true — construction is tested, body execution/re-render is NOT.
- **Evidence:** `pytest` run: `test_views_construct_in_renderer_context PASSED` and `test_state_changes_rerender_without_frozen_errors PASSED` while `_render` never invokes `fn` (component.py:476-522). A body that raised at render time would not be caught.
- **Fix / opportunity:** Replace `_render` to actually mount/render, e.g. call `c.update()` (component.py:116) on the returned `Component` inside a bound page session, or invoke `fn(*args, **kwargs)` directly within `Renderer().with_context()`. Minimal: in `_render`, after `render_component`, call the returned component's `update()` within a renderer/page context so bodies execute and frozen-control mutations surface as RuntimeError.
- **Risk if ignored:** A frozen-control / imperative-mutation regression in a view body would ship undetected; the gate gives false confidence.

### F2 · P1 · Both license tests fail because `src/LICENSES` is deleted
- **Where:** `tests/test_ui_reactive.py:175-197` (`test_license_texts_are_present_and_shipped`, fails at :182) and `:200-207` (`test_licenses_view_carries_real_text`, fails at :206); `src/screens/views.py:20` (`_LICENSES_DIR`) and `:627-628` (reads `_LICENSES_DIR / fname`, falls back to `"(text missing)"`).
- **What:** `src/LICENSES` does not exist on disk (verified `ls: cannot access .../src/LICENSES: No such file or directory`). `licenses_view()` therefore emits `"(text missing)"` for every expansion tile (views.py:628), so `test_licenses_view_carries_real_text` fails (`"(text missing)" not in ...` is False) and `test_license_texts_are_present_and_shipped` fails (`app_dir.is_dir()` is False). The compliance texts are not shipped.
- **Evidence:** `pytest` FAILED both license tests with the exact assertion messages above; `src/LICENSES` absent while `src/assets/icon.svg` exists (99177 bytes icon.png, 42905 bytes icon.svg).
- **Fix / opportunity:** Restore `src/LICENSES/*.txt` (GPL-2.0, GPL-3.0, Apache-2.0, MIT, BSD-3-Clause, MPL-2.0, PSF-2.0, each >500 bytes, byte-identical to repo `LICENSES/` per views.py:193-197) so the license screen carries real text and the tests pass. Do not weaken the tests.
- **Risk if ignored:** GPL §3(b)/§6(b) source-offer compliance content is absent; the app ships placeholder text; CI fails on these two tests.

### F3 · P2 · `test_brand_hero_builds_and_tints_per_theme` reads `icon.color` after `build_brand_hero` outside a renderer — assertion strength is weak but passes
- **Where:** `tests/test_ui_reactive.py:58-76`; `src/components/brand_hero.py:32-62` (`ft.Image(color=...)` at :42).
- **What:** `build_brand_hero` is a plain function (not `@ft.component`), so calling it directly is fine. It sets `color=ft.Colors.WHITE` when dark and `None` when light (brand_hero.py:42). Test asserts `icon.color == ft.Colors.WHITE` for dark and `icon.color is None` for light. These pass (ft.Colors.WHITE verified present in installed flet 1.0.4). Assertion is valid but only checks the `ft.Image`, not that the hero Container actually renders.
- **Fix / opportunity:** None required — correct and passing. Keep.

### F4 · P3 · `test_theme_toggle_button_matches_mode` / `test_theme_modes_resolve` are verified-good
- **Where:** `tests/test_ui_reactive.py:87-96` and `:135-149`; `src/components/app_header.py:18-32` (`theme_button`); `src/core/theme.py:43-72` (`is_light_theme`, `bg`).
- **What:** `ft.Icons.BRIGHTNESS_AUTO_ROUNDED`, `LIGHT_MODE_ROUNDED`, `DARK_MODE_ROUNDED` all exist in installed flet 1.0.4 (verified via venv python). `theme_button` returns the right icon per `state.theme_mode` (app_header.py:20-22). `is_light_theme()` with no page returns False (dark terminal-native default, theme.py:60-61); `bg()` == `AppColors.DARK_BG` (theme.py:71-72). `build_theme()` returns an `ft.Theme` pair (theme.py:95-124).
- **Evidence:** venv `python3 -c "import flet as ft"` confirmed all `ft.Icons.*` and `ft.Colors.WHITE` present; both tests PASSED.
- **Fix / opportunity:** None. Verified-good.

### F5 · P2 · Imperative-mutation guard covers all screen files, but only screen files
- **Where:** `tests/test_ui_reactive.py:152-162` (walks `(ROOT / "src" / "screens").rglob("*.py")`); `src/screens/` contains exactly `__init__.py`, `onboarding_view.py`, `terminal_view.py`, `views.py` (verified `ls`); all `@ft.component` usages are under `src/screens/` plus `src/app_shell.py` (verified `grep -rln "@ft.component" src/`).
- **What:** The guard's four regexes (`\.value\s*=`, `page\.update\(`, `\.controls\.(append|clear|extend)\(`, `\.controls\s*=\s*\[`) are checked against every `src/screens/*.py`. All four screen files are covered; no imperative control mutation is currently present (verified by the passing test). `app_shell.py` (the navigation shell, not a screen) is NOT covered by the guard — but it is outside the guard's declared scope (`src/screens`), so this is a scope question, not a gap in coverage of screen files.
- **Fix / opportunity:** If `app_shell.py` should be held to the same rule, extend the walk to include it; otherwise no change needed.
- **Risk if ignored:** Low — the guard does cover every screen file.

## Verified-good list
- `ft.component`, `ft.use_state`, `ft.use_effect`, `ft.use_context`, `ft.memo` all exist in installed flet 1.0.4 (venv check).
- `ft.Colors.WHITE`, `ft.Icons.BRIGHTNESS_AUTO_ROUNDED/LIGHT_MODE_ROUNDED/DARK_MODE_ROUNDED` exist (venv check; brand_hero.py:42, app_header.py:20-22).
- `theme.is_light_theme()` no-page → False; `theme.bg()` == `AppColors.DARK_BG` (theme.py:43-72); `theme.build_theme()` → `ft.Theme` pair (theme.py:95-124).
- `Renderer.render_component` creates a frozen `Component` wrapper without executing `fn` (component.py:476-522) — matches the test's comment "Component wrappers come back".
- `test_licenses_view_has_compliance_content` (test_ui_reactive.py:121-132) PASSED — static compliance strings ("Source code offer", "GPL-2.0"/"GPL-3.0", "Software in the Public Interest", "Canonical", "termux/proot") are present in views.py:646-683.
- No imperative control mutation in `src/screens/*.py` (guard test passes).

## Unverified
- Whether a real body-execution render (calling `Component.update()` / `fn`) would raise for any view — the test never exercises it (F1). Marked UNVERIFIED; the D-015 claim that re-rendering is covered is UNVERIFIED for body execution.
- Whether `app_shell.py` should be included in the imperative-mutation guard scope (F5). UNVERIFIED — it's a navigation shell, not a `src/screens` screen file.
- Whether restoring `src/LICENSES` byte-identical to repo `LICENSES/` makes both license tests pass — strongly implied by the test logic but not re-run after a restore (I am read-only on code).

## Notes on labels
- Every defect/opportunity above cites `file:line` from the app and from `.venv` (or a pasted venv-python command output), per BRIEF rule 2.
- Claims not proven by direct observation are labeled UNVERIFIED (F1 body-execution, F5 app_shell scope, license-restore re-run).
- No HALLUCINATION: all `ft.*`, `@ft.component`, observable, and theme claims were spot-checked against the installed flet 1.0.4 source.
