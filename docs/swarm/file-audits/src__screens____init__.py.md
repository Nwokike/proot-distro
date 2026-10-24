# src/screens/__init__.py — audit

**Verdict:** PERFECT
**Confidence:** high
**Scope:** `src/screens/__init__.py` · `src/screens/onboarding_view.py` · `src/screens/terminal_view.py` · `src/screens/views.py` · `.venv/lib/python3.14/site-packages/flet/__init__.py` · `.venv/lib/python3.14/site-packages/flet/controls/base_page.py` · `.venv/lib/python3.14/site-packages/flet/controls/context.py` · `.venv/lib/python3.14/site-packages/flet/controls/padding.py` · `.venv/lib/python3.14/site-packages/flet/controls/alignment.py` · `.venv/lib/python3.14/site-packages/flet/controls/events.py` · `.venv/lib/python3.14/site-packages/flet/controls/material/form_field_control.py` · `.venv/lib/python3.14/site-packages/flet/components/hooks/use_effect.py` · `.venv/lib/python3.14/site-packages/flet/components/hooks/use_state.py` · `.venv/lib/python3.14/site-packages/flet_terminal/__init__.py` · `.venv/lib/python3.14/site-packages/flet_terminal/mobile_terminal.py` · `.venv/lib/python3.14/site-packages/flet_terminal/themes.py` · `tests/test_ui_reactive.py` · `src/app_shell.py` · **Date:** 2026-10-24

## What it does / how the app uses it

`src/screens/__init__.py` is a 14-line re-export facade. It pulls six names from
three sibling modules and lists them in `__all__`, giving the rest of the
codebase a single import surface (`from screens import X`). The three modules
implement the app's four screens: `OnboardingView` (first-run deck),
`TerminalView` + `SessionSelectorView` (terminal tab), `DistroView` +
`SettingsView` (distro manager and settings), and the standalone helper
`licenses_view` (compliance dialog content). `app_shell.py` imports five of the
six names; tests import all six directly from `screens`.

## Findings

No bugs, hallucinations, or structural defects were found. The file is free of
unused imports, missing exports, and incorrect API references. Details follow in
the verified-good list below.

## Missed capabilities (dependency audits only)

N/A — this is an app-code file, not a dependency wrapper.

## Verified-good list

**Export completeness — exact match.**
Every name re-exported by `__init__.py` (`src/screens/__init__.py:7-14`) exists
in its source module and is verified callable:

| Export | Source | Source line |
|---|---|---|
| `DistroView` | `screens/views.py` | 74 (`@ft.component`) |
| `OnboardingView` | `screens/onboarding_view.py` | 38 (`@ft.component`) |
| `SessionSelectorView` | `screens/terminal_view.py` | 232 (`@ft.component`) |
| `SettingsView` | `screens/views.py` | 386 (`@ft.component`) |
| `TerminalView` | `screens/terminal_view.py` | 60 (`@ft.component`) |
| `licenses_view` | `screens/views.py` | 609 (plain `def`) |

No name in any sibling module's public surface is absent from `__all__`; all
private helpers (`_fmt_size`, `_write`, `_confirm_close`, etc.) are correctly
prefixed and rightly omitted.

**No unused import.**
`app_shell.py:12-18` imports `DistroView`, `OnboardingView`,
`SessionSelectorView`, `SettingsView`, `TerminalView` — all five. `licenses_view`
is imported from `screens` by `tests/test_ui_reactive.py:122-124` and
`:202-204`, so the sixth export is consumed by the test suite. Every import in
`__init__.py` is used.

**Flet 1.0.4 API — all verified.**
Checked programmatically against the installed package
(`.venv/lib/python3.14/site-packages/flet`, `flet_version = "1.0.4"`,
`flet/version.py:21`). All 34 `ft.*` names used across the three sibling
modules resolve correctly:

- `ft.component` — `.venv/…/flet/components/component_decorator.py` (re-exported
  at `flet/__init__.py:16`).
- `ft.use_state(initial)` — `.venv/…/flet/components/hooks/use_state.py:48`.
- `ft.use_effect(setup, dependencies, cleanup)` — `.venv/…/flet/components/hooks/use_effect.py:42`.
  Call at `terminal_view.py:122` passes `[state.theme_revision]` as the
  second positional, matching the `dependencies` parameter — correct.
- `ft.use_context(ctx)` — `.venv/…/flet/components/hooks/use_context.py:84`.
- `ft.context.page` — `.venv/…/flet/controls/context.py:46` (`@property page`
  on the singleton `Context` object).
- `page.show_dialog` / `page.pop_dialog` — both defined on `BasePage`
  (`.venv/…/flet/controls/base_page.py:402,427`); `Page` inherits `BasePage`
  (`.venv/…/flet/controls/page.py:484`).
- `page.run_task` — `.venv/…/flet/controls/page.py:929`.
- `ft.Padding.symmetric(horizontal=…)` / `ft.Padding.only(bottom=…)` —
  `.venv/…/flet/controls/padding.py:46,54`. Both are `@classmethod`s; calls
  at `terminal_view.py:174,227` use keyword arguments matching the signatures.
- `ft.Alignment.TOP_LEFT` — `.venv/…/flet/controls/alignment.py:129` (class
  property).
- `ft.OutlineInputBorder(side=ft.BorderSide(…))` — `OutlineInputBorder` at
  `.venv/…/flet/controls/material/form_field_control.py:120` has `side:
  Optional[BorderSide] = None` at line 125. Usage in `views.py:88,337,501`
  is correct.
- `ft.GestureDetector(on_horizontal_drag_end=…)` —
  `.venv/…/flet/controls/core/gesture_detector.py:401`.
- `DragEndEvent.primary_velocity` — `.venv/…/flet/controls/events.py:314`
  (`Optional[float]`). `onboarding_view.py:56` correctly guards with
  `getattr(e, "primary_velocity", 0) or 0` to handle the `None` case.
- `ft.Button` — `.venv/…/flet/controls/material/button.py:26`; distinct from
  `ElevatedButton`/`FilledButton`, exists in `flet.__init__` at line 363.
- `ft.FilledButton`, `ft.TextButton`, `ft.IconButton`, `ft.TextField`,
  `ft.Container`, `ft.Column`, `ft.Row`, `ft.Text`, `ft.Icon`, `ft.Image`,
  `ft.AlertDialog`, `ft.Divider`, `ft.ListTile`, `ft.ExpansionTile`,
  `ft.PopupMenuButton`, `ft.PopupMenuItem` — all present in
  `.venv/…/flet/__init__.py` (grep confirmed; programmatic check returned OK
  for all 34 names).
- `ft.Icons.*` (12 members: `DOWNLOAD_ROUNDED`, `TERMINAL_ROUNDED`,
  `ARROW_BACK`, `TERMINAL`, `CLOSE`, `FULLSCREEN`, `FULLSCREEN_EXIT`, `INFO`,
  `INVENTORY_2_OUTLINED`, `APPS`, `MORE_VERT`, `SETTINGS`) — all resolve
  correctly on the installed `ft.Icons` enum class (programmatic check, all
  OK).
- `ft.Colors.WHITE` — present on `ft.Colors`.
- `ft.BoxFit.CONTAIN`, `ft.FontWeight.BOLD`, `ft.TextAlign.CENTER`,
  `ft.MainAxisAlignment.CENTER`, `ft.CrossAxisAlignment.CENTER`,
  `ft.ScrollMode.AUTO` — all verified present.

**flet-terminal API — all verified.**
`BUILTIN_THEMES` is exported from `flet_terminal` at
`.venv/…/flet_terminal/__init__.py:7,12`. `MobileTerminal.set_on_bytes`,
`.on_data`, `.on_resize`, `.on_title_change`, `.on_mount`, `.clear_pending`,
`.send_bytes`, `.set_theme` are all defined at
`.venv/…/flet_terminal/mobile_terminal.py:337,343,352,361,394,415,245,156`
respectively.

**Architecture conformance.**
All four views are `@ft.component` functions returning `ft.Control`, consistent
with the declared state-driven architecture (D-015). No imperative widget
mutation (`.update()`, `.controls.append()`) is present in any view body.
Controller mutations are routed through `ControllerMethodsCtx` and
`page.run_task`. `licenses_view` is correctly a plain `def` (not
`@ft.component`) because it is called inside dialog handlers where component
hooks are not valid — the docstring at `views.py:610-611` documents this
intentional choice.

**No stale or phantom exports.**
`screens/__init__.py` has no imports from modules that do not exist; no names
are imported under aliases that would mismatch `__all__`. The `__all__` list
matches the set of imported names exactly (6 = 6).

## Unverified

Nothing. Every claim above is backed by a file:line citation or a reproducible
programmatic check.
