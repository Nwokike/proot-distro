# src/components/__init__.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/components/__init__.py` + every module it re-exports from (`src/components/ui.py`); package context from `src/components/{app_header,banner_ad,brand_hero,update_dialog}.py`; API verified against `.venv/lib/python3.14/site-packages/flet` (Flet 1.0.4). **Date:** 2026-10-24

## What it does / how the app uses it

`src/components/__init__.py` is the package facade for `src/components/`. It imports five thin wrapper/builders from `ui.py` and re-exports them in `__all__`:

- `card` → `styles.glass_card` (ui.py:10, styles.py:14)
- `section_header` → `styles.section_header` (ui.py:15, styles.py:25)
- `empty_state` → `styles.empty_state` (ui.py:20, styles.py:101)
- `probe_banner` → inline `ft.Container`/`ft.Row` warning strip (ui.py:25)
- `hints_card` → inline dismissible capability hints (ui.py:42)

Consumers import through this facade: `src/screens/views.py:10` does `from components import card, empty_state, hints_card, probe_banner, section_header`. The package's other four modules (`app_header`, `banner_ad`, `brand_hero`, `update_dialog`) are imported directly by consumers (e.g. `views.py:11-13`, `terminal_view.py:14-16`) and are NOT re-exported here — see F2.

## Findings

### F1 · P2 · `update_dialog.py` "Check for Updates" button never awaits its async handler — silent no-op
- **Where:** `src/components/update_dialog.py:102` (and handler def at `:149`); Flet dispatch rule at `.venv/lib/python3.14/site-packages/flet/controls/base_control.py:516-520`
- **What:** `_check_again` is declared `async def` (update_dialog.py:149) and is wired via `ft.TextButton("Check for Updates", on_click=lambda _e: _check_again(page))` (update_dialog.py:102). Flet only awaits a handler when the stored attribute itself `iscoroutinefunction` (base_control.py:516 checks the lambda, which is a plain sync function). The coroutine returned by `_check_again(page)` is created and immediately discarded, so `check_for_update()` never runs and the dialog never morphs.
- **Evidence:** update_dialog.py:102 `on_click=lambda _e: _check_again(page)`; update_dialog.py:149 `async def _check_again(page: ft.Page) -> None:`; base_control.py:516 `if inspect.iscoroutinefunction(event_handler):` — the lambda fails this test.
- **Fix / opportunity:** Make the lambda `async` and await: `on_click=lambda _e: page.run_task(_check_again, page)` or `on_click=lambda _e: asyncio.create_task(_check_again(page))`. Prefer `page.run_task` (page.py:929) which is the house pattern for fire-and-forget async work (used at update_dialog.py:26).
- **Risk if ignored:** User taps "Check for Updates"; nothing happens; no error surfaced. User-visible broken behavior.

### F2 · P3 · `__init__.py` re-exports only `ui.py`; not a complete export list for the `components` package
- **Where:** `src/components/__init__.py:3-5`
- **What:** `__all__ = ["card", "empty_state", "hints_card", "probe_banner", "section_header"]` covers exactly the five names from `ui.py`. The package also ships public symbols in four other modules that are never re-exported here: `AppHeader`, `theme_button`, `version_chip` (app_header.py:98/18/35); `pooled_banner_ad`, `build_banner_ad`, `clear_banner_pool`, `banner_unit_id` (banner_ad.py:31/43/39/27); `build_brand_hero`, `app_icon_svg` (brand_hero.py:32/17); `show_update_dialog` (update_dialog.py:40). Consumers reach these via direct module imports (`from components.app_header import AppHeader` — views.py:11), so nothing is broken, but the facade is incomplete and inconsistent with a "house package layout" that presents a unified surface.
- **Evidence:** __init__.py:3 import lists only `components.ui`; __all__:5 lists five names; sibling module public defs cited above.
- **Fix / opportunity:** Either (a) extend `__init__.py`/`__all__` to re-export the package's public component symbols, or (b) document that `__init__` is `ui`-only and consumers import other modules directly. Minimal, architecture-respecting: extend `__all__` + imports for the public builders consumers already use.
- **Risk if ignored:** New contributors assume `from components import *` (or `from components import AppHeader`) works; it silently fails with ImportError. Discoverability/UX defect.

### F3 · P3 · `core/__init__.py` is empty (0 bytes); `ui.py` relies on implicit submodule binding
- **Where:** `src/components/ui.py:7` `from core import styles, theme, tokens`; `src/core/__init__.py` (0 bytes, confirmed via `wc -c` = 0)
- **What:** `from core import styles` works in Python because importing a submodule binds it as an attribute on the parent package, even with an empty `__init__.py`. This is legal but implicit: a reader cannot tell from `core/__init__.py` what `core` exposes, and it is UNVERIFIED whether any code does `import core` then `core.styles` vs the `from core import styles` form used everywhere.
- **Evidence:** `src/core/__init__.py` is 0 bytes; ui.py:7 imports three submodules; all `core` consumers use `from core import X` form (grep of src/ confirms).
- **Fix / opportunity:** Leave as-is (it works) or add explicit re-exports to `core/__init__.py` for clarity. Low cost, low risk. Marked UNVERIFIED only in the sense that no explicit re-export contract exists.
- **Risk if ignored:** None functionally; clarity/maintainability only.

## Verified-good list (every `ft.*` / enum / member checked against installed Flet 1.0.4 source)

- `flet.__version__` / `flet_version = "1.0.4"` — `.venv/.../flet/version.py:19`, `__init__.py:4`
- `ft.Icons.INBOX, WARNING_AMBER_ROUNDED, INFO_OUTLINE, LIGHT_MODE_ROUNDED, DARK_MODE_ROUNDED, BRIGHTNESS_AUTO_ROUNDED, CAMPAIGN_ROUNDED, ROCKET_LAUNCH_ROUNDED, VERIFIED_ROUNDED, SHOP_ROUNDED, DOWNLOAD_ROUNDED, TERMINAL` — all present in `controls/material/icons.json`; resolved via `_IconsProxy.__getattr__` at `controls/material/icons.py:68`
- `ft.Colors.with_opacity` — `controls/colors.py:110` (classmethod); `ft.Colors.WHITE` — `colors.py:469`
- `ft.Control, ft.Container, ft.Row, ft.Column, ft.Text, ft.Icon, ft.IconButton, ft.TextButton, ft.FilledButton, ft.OutlinedButton, ft.Image, ft.Markdown, ft.AlertDialog, ft.SnackBar, ft.ProgressRing` — all in `flet/__init__.py` `__all__` and defined in their modules (e.g. `alert_dialog.py:24`, `snack_bar.py:155`, `progress_ring.py:13`)
- `ft.Padding.symmetric / .all / .only` — `controls/padding.py:13,39,46,54`; `ft.Border.all` — `controls/border.py:173,204`; `ft.Margin` — `controls/margin.py:10`; `ft.Alignment.CENTER` — `controls/alignment.py:33,125`
- `ft.ScrollMode.AUTO` — `controls/types.py:684,692`; `ft.CrossAxisAlignment.CENTER` — `:388,404`; `ft.MainAxisAlignment.SPACE_BETWEEN / .CENTER` — `:350,365,370`; `ft.FontWeight.BOLD` — `:165,175`; `ft.TextAlign.CENTER` — `:647,662`; `ft.BoxFit.CONTAIN` — `controls/box.py:216,231`
- `ft.MarkdownExtensionSet.GITHUB_WEB` — `controls/core/markdown.py:28,46`
- `ft.context.page` (raises RuntimeError outside a session) — `controls/context.py:46,62-69`; `ft.Page.platform` `:595`, `Page.web` `:516`, `Page.run_task` `:929`
- `Page.show_dialog` / `Page.pop_dialog` — `controls/base_page.py:402,427`
- `core/styles.glass_card / section_header / empty_state` — `styles.py:14/25/101` (signatures match ui.py call sites exactly)
- `core.theme.AppColors.WARN / primary() / text() / text_dim() / glass_bg() / glass_border() / is_light_theme()` — `theme.py:8/31/91/84/88/127/131/43`
- `core.tokens.SPACE_MD / SPACE_XS / SPACE_SM / RADIUS_SM / RADIUS_LG / FONT_SM / FONT_MD / FONT_LG` — `tokens.py:11/9/10/19/21/28/29/30`
- Flet awaits coroutine handlers (base_control.py:516-520) — relevant to F1; confirms the lambda bug.

## Unverified

- Whether any consumer relies on `from components import *` pulling in only `ui.py` names vs expecting the other modules (behavioral impact of F2; code grep shows direct module imports everywhere).
- Whether `core/__init__.py` being empty is intentional house style vs an oversight (no doc found; F3 flagged as clarity only).
- Runtime behavior of `probe_banner`/`hints_card` (no test harness exercised; UI rendering not executed).
- `banner_ad.py` imports `from flet import Control` (banner_ad.py:14) — `Control` is exported (`__init__.py:839`) and used only for typing; verified present but not exercised at runtime.

## Notes / labeling

- `update_dialog.py:33` `except TypeError, ValueError:` is valid Python 3 (exception tuple) — compiles cleanly (compile-check returned exit 0). NOT a bug; not flagged.
- `app_header.py:37` re-imports `from core.state import state as core_state` inside `version_chip` while `state` is already imported at module scope (line 15). Works, mildly redundant; not flagged as a defect.
- No code was modified, per the BRIEF non-negotiable rule 1.
