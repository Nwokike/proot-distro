# src/components/ui.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/components/ui.py` (79 lines) · `src/core/styles.py` · `src/core/theme.py` · `src/core/tokens.py` · `src/core/state.py` · `src/core/constants.py` · `src/screens/views.py` (usage) · `src/app_controller.py` (persistence pattern) · `tests/test_ui_reactive.py` · `docs/reference/house-ui-design.md` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/components/ui.py` is a thin facade over `core.styles` plus two bespoke components. `card()`/`section_header()`/`empty_state()` (`:10-22`) delegate argument-for-argument to `styles.glass_card`/`styles.section_header`/`styles.empty_state`. `probe_banner(summary)` (`:25-39`) renders a warning strip used in `screens/views.py:317` when `state.probe_passed` is False. `hints_card(dismissed, on_dismiss)` (`:42-79`) renders the dismissible "How this works" capability card used in `screens/views.py:313`, driven by `state.hints_dismissed`. All five are re-exported via `components/__init__.py:3` and consumed by `screens/views.py:10`.

---

## Findings

### F1 · P2 · `hints_card` dismissal is not persisted across app restarts
- **Where:** `src/components/ui.py:42-46` (signature `hints_card(dismissed: bool, on_dismiss)`) · `src/screens/views.py:313` (`hints_card(st.hints_dismissed, lambda _e: setattr(state, "hints_dismissed", True))`) · `src/core/state.py:34` (`hints_dismissed: bool = False`) · `src/app_controller.py:299-304` (`_restore_onboarding`/`finish_onboarding` with `STORAGE_ONBOARDING_DONE`) · `src/core/constants.py:22` (`STORAGE_ONBOARDING_DONE`) · `.venv/lib/python3.14/site-packages/flet/components/observable.py:165-176`
- **What:** The hints card is "dismissible" in-memory only. `on_dismiss` mutates `state.hints_dismissed`, which re-renders the view, but nothing writes the flag to `shared_preferences`. On the next launch `AppState.__init__` resets it to `False` (`src/core/state.py:49-52`), so the card reappears. This contrasts with the onboarding deck, which uses `STORAGE_ONBOARDING_DONE` + `_restore_onboarding`/`finish_onboarding` (`src/app_controller.py:299-304`).
- **Evidence:** `grep -rn "hints_dismissed" src` returns only `src/core/state.py:34`, `src/screens/views.py:313`, `src/screens/terminal_view.py`-adjacent none; no `prefs.set`/`prefs.get` for hints. `app_controller.py:299-304` shows the persisted pattern exists for onboarding only.
- **Fix / opportunity:** Add `STORAGE_HINTS_DISMISSED = "proot_hints_dismissed"` to `src/core/constants.py`, add `_restore_hints`/`dismiss_hints` controller methods mirroring `_restore_onboarding`/`finish_onboarding`, restore at boot, and have `on_dismiss` call `methods.dismiss_hints()` (or persist in the existing lambda). Keep `state.hints_dismissed` as the reactive mirror.
- **Risk if ignored:** Users who tap "Got it" see the card again on every restart, eroding trust in the dismiss control.

### F2 · P2 · `probe_banner` warning color fails contrast in light theme
- **Where:** `src/components/ui.py:30-31` (`color=theme.AppColors.WARN` on `ft.Icon` and `ft.Text`) · `src/components/ui.py:36` (`bgcolor=ft.Colors.with_opacity(0.10, theme.AppColors.WARN)`) · `src/core/theme.py:31` (`WARN = "#F38BA8"`) · `.venv/lib/python3.14/site-packages/flet/controls/colors.py:110` (`Colors.with_opacity`)
- **What:** `AppColors.WARN` is a single Catppuccin-pink (`#F38BA8`) used in both themes. Measured contrast of `#F38BA8` on the light glass/background (`#F4F4F8`/`#FFFFFF`) is ~2.1:1, below the 4.5:1 expected for 10px text (`tokens.FONT_SM`). On the dark background it is ~8.1:1, so the defect is light-theme only.
- **Evidence:** Computed locally: `WARN #F38BA8` on `#F4F4F8` = 2.11; on `#121218` = 8.06. `tokens.FONT_SM = 10` (`src/core/tokens.py:28`).
- **Fix / opportunity:** Make the warning color theme-aware, e.g. add `LIGHT_WARN`/`DARK_WARN` (or `warn()` resolver in `core/theme.py`) with a darker red for light mode (e.g. `#D20F39`), and have `probe_banner` read `theme.warn()` (or `theme.AppColors.WARN` resolved per theme). No new dependency required.
- **Risk if ignored:** The probe-failure strip is effectively unreadable in light mode, hiding the only user-facing explanation of why containers cannot install.

### F3 · P3 · Hardcoded copy in `hints_card` is not centralized
- **Where:** `src/components/ui.py:46-50` (three hint strings) · `src/components/ui.py:57-58` (`"How this works"`, `size=tokens.FONT_MD`) · `src/components/ui.py:64` (`"Got it"`) · `src/core/constants.py` (no UI-copy constants)
- **What:** All user-facing strings in `hints_card` are inline literals. The rest of the app also inlines copy, but `constants.py` is the designated home for identity/copy constants; there is no equivalent for UI copy. This makes the strings untestable and untranslatable and drifts from the "constants over literals" intent.
- **Evidence:** `src/core/constants.py` contains only identity/distribution/storage keys; `grep -rn "How this works" src` returns only `src/components/ui.py:57`.
- **Fix / opportunity:** Move the three hint lines and button labels into named constants (either in `core/constants.py` or a `core/copy.py`), imported by `ui.py`. Keep token-based sizing.
- **Risk if ignored:** Low; copy edits require touching component code and risk regressions in the render contract.

### F4 · P3 · `empty_state` wrapper reverses the underlying argument order
- **Where:** `src/components/ui.py:20-22` (`def empty_state(title, message="", icon=ft.Icons.INBOX)` → `styles.empty_state(icon, title, message)`) · `src/core/styles.py:101` (`def empty_state(icon, title, message="")`)
- **What:** The wrapper's parameter order (`title, message, icon`) is the reverse of `styles.empty_state` (`icon, title, message`). Callers in `src/screens/views.py:368-372` rely on keyword `icon=`, so it works today, but positional callers (or future ones) will silently swap icon and title. The house empty state's first positional is the icon (`house-ui-design.md` §5).
- **Evidence:** `src/screens/views.py:368-372` calls `empty_state("No containers yet", "Install any Docker image to begin.", icon=ft.Icons.INVENTORY_2_OUTLINED)`.
- **Fix / opportunity:** Either align `ui.empty_state`'s signature to `(icon, title, message="")` to match `styles.empty_state`, updating the single call site, or keep the current order but document it. Aligning is the lower-risk, less surprising choice.
- **Risk if ignored:** A future positional call produces a wrong-icon/wrong-title render with no type error.

### F5 · P3 · `hints_card` "Got it" button has no explicit color/size
- **Where:** `src/components/ui.py:64` (`ft.TextButton("Got it", on_click=on_dismiss)`) · `src/core/tokens.py:28-29` (`FONT_SM`, `FONT_MD`)
- **What:** Unlike the surrounding text, the dismiss button inherits Flet's default `TextButton` label styling (no `color`, no `size`). In both themes this is acceptable, but it is inconsistent with the card's `FONT_SM` body text and relies on theme defaults rather than house tokens.
- **Evidence:** `ui.py:61-69` sets `size=tokens.FONT_SM` on item text but `ui.py:64` sets neither on the button.
- **Fix / opportunity:** Pass `style=ft.ButtonStyle(color=theme.primary())` (or `color=theme.primary()`) and keep the default size, or explicitly set the button text size to `tokens.FONT_SM`.
- **Risk if ignored:** Minor visual inconsistency; low user impact.

### F6 · UNVERIFIED · Dismissed empty `Container()` may retain layout height
- **Where:** `src/components/ui.py:44-45` (`if dismissed: return ft.Container()`)
- **What:** It is not verified from the installed source whether a `Container` with no `content`/`height` collapses to zero height inside a `Column`, or whether default padding/margins leave a gap. If it does not collapse, the dismissed card leaves blank space.
- **Evidence:** `src/components/ui.py:44-45`; `.venv/lib/python3.14/site-packages/flet/controls/material/container.py:39-...` (default `padding`/`height` not confirmed). Labeled `UNVERIFIED`.
- **Fix / opportunity:** If a gap is observed, return `None` is not allowed in `controls` lists; instead gate the call site in `views.py` (`if not st.hints_dismissed: controls.append(hints_card(...))`) or set `visible=False`/`height=0`.
- **Risk if ignored:** Possible blank strip after dismissal (visual only).

---

## Missed capabilities (dependency audits only)

N/A — this is an app-component audit, not a dependency audit. No new packages proposed (D-003).

---

## Verified-good list

1. **All Flet 1.0.4 APIs used exist with matching signatures:** `ft.Container` (`controls/material/container.py:39`), `ft.Row` (`controls/core/row.py:14`), `ft.Column` (`controls/core/column.py:14`), `ft.Icon` (`controls/core/icon.py:13`), `ft.Text` (`controls/core/text.py:222`), `ft.TextButton` (`controls/material/text_button.py:21`), `ft.Border.all` (`controls/border.py:204`), `ft.Padding.symmetric` (`controls/padding.py:46`), `ft.Colors.with_opacity` (`controls/colors.py:110`), `ft.CrossAxisAlignment.CENTER` (`controls/types.py:388`), `ft.FontWeight.BOLD` (`controls/types.py:165`), `ft.Icons.*` (`controls/material/icons.py` via `flet/__init__.py:423`).
2. **Wrapper delegation is correct:** `card`→`styles.glass_card(content, padding)`, `section_header`→`styles.section_header(title, action)`, `empty_state`→`styles.empty_state(icon, title, message)` with the reordering done explicitly (`src/components/ui.py:10-22` vs `src/core/styles.py:14,25,101`).
3. **No imperative control mutation in `ui.py`:** No `.value =`, `page.update()`, or `.controls.append/clear` (D-015 compliant).
4. **Theme-aware colors in `hints_card`:** uses `theme.glass_bg()`, `theme.glass_border()`, `theme.text()`, `theme.text_dim()`, `theme.primary()` (`src/components/ui.py:56,61,62,68,74,75`), so it follows light/dark switches.
5. **State-driven re-render path exists:** `DistroView` subscribes via `ft.use_state(state)` (`src/screens/views.py:75`), so `hints_dismissed` toggles re-render `hints_card` correctly.
6. **`probe_banner` uses tokens for spacing/radius/padding** (`tokens.SPACE_XS/MD/SM`, `RADIUS_SM`) and `expand=True` text, so it behaves correctly in narrow widths.

---

## Unverified

1. Whether a content-less `ft.Container()` collapses to zero height in a `Column` (F6) — labeled `UNVERIFIED`.
2. Whether `TextButton` default label color meets contrast in both themes (no explicit color set) — labeled `UNVERIFIED`.
3. Whether persisting `hints_dismissed` is intended by product (no decision doc entry) — labeled `UNVERIFIED`; inferred from the onboarding precedent.