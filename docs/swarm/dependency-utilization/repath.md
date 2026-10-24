# repath — audit

**Verdict:** PERFECT
**Confidence:** high
**Scope:** `src/main.py:1-41` · `src/app_controller.py:39-96,161-209` · `src/app_shell.py:1-78` · `src/screens/terminal_view.py:59-325` · `src/screens/views.py:20,26-51,73-130,165-260,386-420,565-606` · `src/core/state.py:8-54` · `src/services/session_manager.py:25-96` · `src/state/controller_ctx.py:1-61` · `pyproject.toml:9-15,62-63` · `tests/test_imports_vs_deps.py:46-59` · `tests/test_ui_reactive.py:49-53` · `docs/dependency-studies/repath.md` (study, prior knowledge) · `docs/dependency-studies/flet.md:329,408` · `docs/decisions.md:12-15,49` · `.venv/Lib/site-packages/repath.py:1-297` · `.venv/Lib/site-packages/repath-0.9.0.dist-info/METADATA:20` · `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:14-16` · `.venv/Lib/site-packages/flet/components/router.py:16,45-108,163-314,428-452,593-713` · `.venv/Lib/site-packages/flet/controls/template_route.py:1-52` · `.venv/Lib/site-packages/flet/controls/page.py:310-330,642,750-795` · `.venv/Lib/site-packages/flet/controls/core/view.py:149` · `.venv/Lib/site-packages/flet/__init__.py:1280,1538-1814,1821-1834` · **Date:** 2026-10-20

## What it does / how the app uses it

repath 0.9.0 is a **single-file, pure-Python ExpressJS-style route-template → regex
compiler** (296 lines, 8 205 bytes, `.venv/Lib/site-packages/repath.py`). It is **not** a
declared dependency of this project: `pyproject.toml:9-15` lists only `flet`, `flet-ads`,
`httpx`, `flet-terminal`, `proot-distro`. It arrives **transitively and unconditionally**
through flet:

```text
$ grep -n "Requires-Dist" .venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA
14:Requires-Dist: oauthlib>=3.2.2; platform_system != "Emscripten"
15:Requires-Dist: httpx>=0.28.1; platform_system != "Emscripten"
16:Requires-Dist: repath>=0.9.0
```

Line 16 carries **no environment marker** — unlike oauthlib/httpx on lines 14-15 — so repath is
a hard install-time requirement of flet on every platform, including Emscripten/web
(`flet-1.0.4.dist-info/METADATA:16`). Its own only dependency is `six (>=1.9.0)`
(`repath-0.9.0.dist-info/METADATA:20`), used at `repath.py:3-4`.

**The app uses repath not at all, and does not need to.** It is reachable only through flet's
two routing modules, both of which import it at module top level:

```text
$ grep -rn "repath" .venv/Lib/site-packages/flet/
flet/components/router.py:16:import repath
flet/components/router.py:191:        pattern = repath.pattern(full_path)
flet/components/router.py:228:        prefix_pattern = repath.pattern(full_path, end=False)
flet/components/router.py:265:            prefix_pattern = repath.pattern(full_path, end=False)
flet/components/router.py:287:            exact_pattern = repath.pattern(full_path)
flet/components/router.py:302:    leaf_pattern = repath.pattern(full_path)
flet/controls/template_route.py:3:import repath
flet/controls/template_route.py:44:        pattern = repath.pattern(route_template)
```

Neither module is loaded by `import flet`: flet re-exports them lazily
(`flet/__init__.py:1280` `_LAZY = {…}`, `:1645` `"Router": "flet.components.router"`,
`:1721` `"TemplateRoute": "flet.controls.template_route"`, resolved by
`__getattr__` at `flet/__init__.py:1821-1834`). Runtime proof:

```text
$ .venv/Scripts/python.exe -c "import flet, sys; print('repath' in sys.modules)"
False
$ .venv/Scripts/python.exe -c "import flet as ft, sys; _=ft.Router; print('repath' in sys.modules)"
True
```

The app's own import graph never touches it — all 32 app modules import cleanly and neither
`repath` nor `six` enters `sys.modules`:

```text
total .py files: 32
failures: []
repath in sys.modules after importing ALL app modules (incl. main): False
six    in sys.modules after importing ALL app modules (incl. main): False
```

The only `repath` string anywhere in `src/` is a **licence-list entry**, not an import
(`src/screens/views.py:40`, inside `_PY_DISTS` at `:26-42`, consumed by `_py_entries()` at
`:600-606` to render "repath 0.9.0 (MIT)" in the app's Licenses screen).

**How the app navigates instead.** `src/main.py:19-32` builds one `AppController`
(`src/app_controller.py:39-43`) and renders exactly one root component tree:

- `src/app_controller.py:85` — `self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))`.
  `Page.render()` replaces `page.views[0].controls` only (`flet/controls/page.py:750-771`) —
  there is **one** view, no view stack.
- `src/app_shell.py:20-28` — three peer tabs (`TAB_DISTRO`/`TAB_TERMINAL`/`TAB_SETTINGS`) in a
  `ft.NavigationBar` (`:66-73`) whose `selected_index=active_tab` (`:70`) is driven by
  `ft.use_state` (`:44`) and `on_change` (`:47-48`).
- `src/app_shell.py:53-61` — the body is a plain if/elif swap over that tab index
  (`DistroView` / `SessionSelectorView` / `SettingsView`).
- `src/app_shell.py:31-38` + `src/core/state.py:46` — the one drill-down: a live session
  (`state.active_session` → `SessionManager.entries`, `src/services/session_manager.py:50`)
  **takes over the whole body** (`src/app_shell.py:54-55` → `TerminalView(entry)`), and the only
  way back is an in-app `ARROW_BACK` button (`src/screens/terminal_view.py:136-142`) that calls
  `methods.leave_session`.
- Everything else — install consent, rename, backup, restore, copy, remove, reset, Docker
  token, privacy options — is a **modal dialog** (`page.show_dialog` / `page.pop_dialog`,
  e.g. `src/screens/views.py:92-130`, `:165-260`, `:392-417`; `src/screens/terminal_view.py:42-56`).

Zero routing API is referenced anywhere in `src/` or `tests/`:

```text
$ grep -rn "Router\|TemplateRoute\|use_route\|page\.go\|page\.route\|on_route_change\|repath\|\.go(" src/ tests/
src/screens/views.py:40:    "repath",
```

## Findings

### F1 · P3 · repath is an unconditional flet dependency and correctly excluded from every cleanup path
- **Where:** `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:16` (`Requires-Dist: repath>=0.9.0`, **no** environment marker) · `pyproject.toml:62-63` (`[tool.flet.cleanup] package_files = ["oauthlib/**"]`) · `pyproject.toml:9-15` (project deps) · `.venv/Lib/site-packages/flet/components/router.py:16` · `.venv/Lib/site-packages/flet/controls/template_route.py:3`
- **What:** repath is a **hard runtime dependency of flet**, not an optional one — but only for code paths that use flet's router. It cannot be pruned the way oauthlib was: `package_files` removes files from the packaged app, and flet's `flet.components.router` / `flet.controls.template_route` do a **top-level** `import repath`, so a pruned repath turns any future routing import into a hard `ModuleNotFoundError`. The current cleanup glob (`["oauthlib/**"]`, `pyproject.toml:63`) correctly excludes repath, and repath is correctly *not* declared in `[project].dependencies`.
- **Evidence:** with repath blocked by a `sys.meta_path` finder:
  ```text
  Router import without repath -> ModuleNotFoundError No module named 'repath'
  TemplateRoute import without repath -> ModuleNotFoundError No module named 'repath'
  plain import flet without repath -> OK, flet 1.0.4
  ft.Router attribute access without repath -> ModuleNotFoundError No module named 'repath'
  ```
- **Fix / opportunity:** none — keep repath exactly as it is. Concretely: **never** add `repath/**` (or `six/**`) to `[tool.flet.cleanup].package_files`; keep repath out of `pyproject.toml:9-15` (adding it would make `tests/test_imports_vs_deps.py:46-59` treat it as a direct dep and is not needed since the app never imports it).
- **Risk if ignored:** a future "trim the APK" pass that prunes repath would leave the app shipping fine until the first `ft.Router`/`ft.TemplateRoute` import, which would then crash the app at import time on device. It is also the cheapest dependency in the tree to keep (8 KB), so there is no upside to pruning it.

### F2 · P3 · Zero app usage of repath is the correct outcome for this app's single-shell/tab design
- **Where:** `src/app_controller.py:85` · `src/app_shell.py:20-28,44,47-48,53-61,66-73` · `src/screens/terminal_view.py:136-142` · `src/screens/views.py:92-130,165-260` · `.venv/Lib/site-packages/flet/components/router.py:45-108,593-598`
- **What:** the app never declares a route, so repath's only consumer (`repath.pattern()`) is never invoked. The app's navigation vocabulary — three **peer** tabs, one **live-session takeover** with an in-app back arrow, and a pile of **modal dialogs** — maps onto flet Router as follows: peer tabs are already fully expressed by `NavigationBar.selected_index` (`src/app_shell.py:70`) and need no route identity; the session takeover is a *live PTY handle*, not a restorable resource, so `/terminal/:container` would be a URL that cannot be honoured on a cold start (`src/services/session_manager.py:50` holds the only live handle, and `src/app_shell.py:31-38` reads it from the in-process manager); the destructive flows are modals, which Router's `modal=True` (`flet/components/router.py:107`) would replace with something strictly weaker for a destructive confirm-then-act flow.
- **Evidence:** `grep` across `src/` and `tests/` returns only the licence-list string (`src/screens/views.py:40`); the import-graph probe above shows `repath` absent from `sys.modules` after importing all 32 app modules.
- **Fix / opportunity:** none. Adopting `ft.Router` now would add a **second source of navigation truth** (the URL) alongside `state.active_session` (`src/core/state.py:46`) and `active_tab` (`src/app_shell.py:44`) — the exact divergence that D-015 (`docs/decisions.md:49`) exists to prevent — and would require moving the app from `Page.render()` to `Page.render_views()` (`flet/controls/page.py:750-795`), a structural change to the single-root `AppShell` + `ControllerMethodsCtx` composition at `src/app_controller.py:85`.
- **Risk if ignored:** none user-visible. The cost of *not* routing is that the app has no shareable/deep-linkable URLs and no declarative route guard; at the current feature set (3 tabs, 1 drill-down, modals) that is a feature gap with no consumer.

### F3 · P3 · The one genuinely missing flet-routing capability: a system-back / view-stack affordance for the terminal takeover
- **Where:** `src/app_shell.py:54-55` (terminal takes over the body) · `src/screens/terminal_view.py:136-142` (in-app `ARROW_BACK` → `methods.leave_session`) · `src/app_controller.py:85` (`page.render`, not `page.render_views`) · `flet/controls/page.py:310-330,642,750-795` · `flet/controls/core/view.py:149` · `flet/components/router.py:609-614,661-713`
- **What:** the app has a drill-down (session takeover) with an in-app back button but **no view stack and no `page.on_view_pop` handler** (`grep -rn "on_view_pop" src/` → no hits). `Page.render()` yields exactly one view (`flet/controls/page.py:750-771`), and `View.can_pop` defaults to `True` (`flet/controls/core/view.py:149`), so there is no Python-side hook where a system back gesture could be turned into "leave the session". By contrast, `ft.Router(..., manage_views=True)` installs a default pop handler that navigates back to the parent route (`flet/components/router.py:669-713`) and, per its own docstring, enables "swipe-back gestures, system back button, and `ft.AppBar` implicit back button on mobile" (`flet/components/router.py:609-614`).
- **Evidence:** `grep -rn "on_view_pop\|render_views" src/` returns no hits; `src/app_controller.py:85` uses `page.render`; `flet/controls/page.py:642` declares `on_view_pop: Optional[EventHandler[ViewPopEvent]] = None` and `flet/controls/page.py:310-322` documents it as "Delivered to `flet.Page.on_view_pop` when the top view is being popped by system or app-bar back behavior."
- **Fix / opportunity:** if the owner wants the Android system back gesture to leave the session, the **minimal, non-routing** fix is to install `page.on_view_pop` in `AppController.init` and call `state.active_session = None` when a session is open — no Router, no repath, no view-stack refactor. Whether that event is actually delivered to Python in single-view `page.render` mode is **UNVERIFIED** (see below), so the fix is speculative until it is measured on-device.
- **Risk if ignored:** if the host does deliver the event and the app ignores it, the user must find the small in-app arrow instead of using the platform gesture — a minor UX friction on the one drill-down the app has. If the host does not deliver it (single view, nothing to pop), the platform back exits the app and the current behaviour is already correct. **This is a P3 because the user-visible impact is unproven and the in-app arrow already covers the flow.**

### F4 · P3 · `repath`'s unused API surface is larger than flet's — and flet only uses the safe subset
- **Where:** `.venv/Lib/site-packages/repath.py:239-249` (`compile`), `:252-263` (`match`), `:288-296` (`template`), `:76-131` (`parse`), `:197-236` (`tokens_to_pattern`) · `.venv/Lib/site-packages/flet/components/router.py:191,228,265,287,302` · `.venv/Lib/site-packages/flet/controls/template_route.py:44`
- **What:** flet calls **only** `repath.pattern()` (six call sites across the two files above). The remaining eight public functions are unused by flet — including `repath.match()`, which has an upstream defect: it accepts a `flags` argument and then **hardcodes `flags=0`**, silently discarding the caller's flags (`repath.py:263`: `return compile(path, flags=0, **options).match(string)`). Because flet never calls `repath.match`, that quirk cannot reach us; and because the app calls no repath API at all, no repath quirk can reach the app.
- **Evidence:** live introspection of the installed module:
  ```text
  repath.pattern sig: (path, **options)
  repath has __version__: False
  repath.__all__: MISSING
  Match class? False   MatchResult? False
  pattern /distro/:name/terminal -> ^/distro/(?P<name>[^/]+?)/terminal(?:/(?=$))?$
  pattern end=False             -> ^/distro/(?P<name>[^/]+?)(?:/(?=$))?(?=/|$)
  match groupdict -> {'name': 'alpine'}
  prefix match    -> /distro/alpine
  list alternation-> (?:^/a(?:/(?=$))?$|^/b(?:/(?=$))?$)
  ```
  (named-group emission at `repath.py:217-218`, `end`/`strict` handling at `:227-236`.)
- **Fix / opportunity:** none. This is a note for the record: if the app ever adopts routing directly (it should not — see F2), it must call `repath.pattern()`/`repath.template()`, **never** `repath.match()` with `flags`.
- **Risk if ignored:** none today. It is recorded so the synthesis does not re-derive that "repath has a broken `match()`" is a live defect in this app — it is not, because flet does not call it.

## Missed capabilities (dependency audits only)

**The capability:** flet's declarative router — `ft.Router` / `ft.Route` / `ft.TemplateRoute` and
the hooks `use_route_params`, `use_route_location`, `use_route_outlet`, `use_route_loader_data`,
`is_route_active` (`flet/__init__.py:1538-1814`; implementation `flet/components/router.py:1-902`,
`flet/controls/template_route.py:1-52`).

| Capability | API location | Proposed integration point | Value vs cost |
|---|---|---|---|
| Parameterized routes (`/distro/:name`) with `use_route_params()` | `flet/components/router.py:45-108` (`Route`), `:163-314` (matching), `:340-354` (`use_route_params`) | none — the app has no restorable per-container screen; container actions are dialogs (`src/screens/views.py:165-260`), and the session takeover is a live in-process handle (`src/services/session_manager.py:50`) | **Value: low. Cost: high.** A `/distro/alpine` URL would have no view to render — the app shows a list of installed containers (`src/screens/views.py:165`), not a per-container page — so the route would have to be invented first, then routed. |
| View stack + system back button + swipe-back | `flet/components/router.py:609-614`, `:661-713`; `flet/controls/page.py:775-795` (`render_views`) | would replace `page.render` at `src/app_controller.py:85` and the tab switch at `src/app_shell.py:53-61` | **Value: low-medium. Cost: high.** It is the only capability with a concrete user-facing payoff (F3), but the payoff is one drill-down that already has an in-app back arrow (`src/screens/terminal_view.py:136-142`), and the cost is a page-model change plus a second navigation state source next to `state.active_session` (`src/core/state.py:46`) and `active_tab` (`src/app_shell.py:44`) — the divergence D-015 (`docs/decisions.md:49`) exists to prevent. The cheaper route to the same payoff is `page.on_view_pop`, not Router. |
| `use_route_loader_data` / `Route.loader` (async data per route) | `flet/components/router.py:66-68`, `:802-805`, `:413-425` | would replace `AppController.refresh_containers()` (`src/app_controller.py:141-159`) as the loader for the distro list | **Value: negative. Cost: high.** Loading is already event-driven and state-driven (`src/app_controller.py:96`, `src/core/state.py:18-23`); a route loader would add a second fetch trigger next to the observable state. |
| `Route.modal=True` (modal overlay routes) | `flet/components/router.py:107`, `:744-794`, `:820-900` | would replace the destructive-confirm dialogs (`src/screens/views.py:241-258`) | **Value: negative.** A modal *route* is weaker than `ft.AlertDialog` for a confirm-then-act destructive flow, and it would lose the `page.pop_dialog()` idiom used consistently today (`src/screens/views.py:99`, `:196`, `:204`, `:215`, `:227`, `:235`, `:246`, `:254`, `:397`, `:409`, `:417`). |
| `repath.template()` — build a URL from params (`/distro/alpine`) | `repath.py:288-296`, `:134-194` | n/a — the app builds no URLs | **Value: zero. Cost: zero.** Recorded for completeness; flet never calls it either. |

**Bottom line on routing:** at the current feature set, adopting flet Router would **add
complexity without materially improving the app**. The app's navigation is 3 peer tabs + 1
live-session takeover + modals; a route tree expresses none of that better than the
`if/elif` at `src/app_shell.py:53-61` and the `NavigationBar` at `:66-73`, while adding a URL
axis that must be kept in sync with `state.active_session` and `active_tab`. The one real
capability worth chasing — a platform back affordance — is reachable through
`page.on_view_pop` (`flet/controls/page.py:642`) **without** repath, Router, or a view-stack
refactor.

## Verified-good list

- **The app never imports repath** — 32/32 app modules import cleanly with `repath` and `six`
  absent from `sys.modules`. `tests/test_imports_vs_deps.py:46-59` (the house guard) would
  fail the build if the app ever imported repath without declaring it, so the zero-usage
  state is enforced, not accidental.
- **repath is not declared in `pyproject.toml:9-15`** — correct: it is a transitive flet
  dependency, and `flet build` resolves flet's own requirements.
- **`[tool.flet.cleanup].package_files = ["oauthlib/**"]` (`pyproject.toml:63`) correctly
  excludes repath** — pruning it would break `flet/components/router.py:16` and
  `flet/controls/template_route.py:3` at import (proved by the `ModuleNotFoundError` probe in
  F1). It also correctly excludes `six/**`, which repath imports at `repath.py:3-4`.
- **The in-app Licenses screen lists repath** (`src/screens/views.py:40`, rendered by
  `_py_entries()` at `:600-606` through `_dist_license()` at `:565-572`) — MIT attribution for
  a dist that really does ship inside the APK (it is pulled in by flet). `six` is listed
  alongside it at `src/screens/views.py:41`, correctly, since repath requires it
  (`repath-0.9.0.dist-info/METADATA:20`).
- **The app's rendering is a single root component** (`src/app_controller.py:85`), which is
  the correct shape for the current three-tab shell and keeps `AppShell` the only navigation
  surface (`src/app_shell.py:42-77`). `tests/test_ui_reactive.py:49-53` renders `AppShell` in a
  renderer context, so the shell stays under the D-015 reactivity guard.
- **The app's own dependency guard would catch a repath import** (`tests/test_imports_vs_deps.py:52-59`),
  so the "app uses zero routing" property cannot regress silently.
- **The repath API claims in `docs/dependency-studies/repath.md` all re-verified against the
  installed source**: `pattern` dispatcher at `repath.py:266-285`; `end`/`strict` handling at
  `:227-236`; named-group emission only for names matching `[a-zA-Z]` at `:217-218`; the
  `match()` flags quirk at `:263`; `compile` at `:239-249`; `template` at `:288-296`; absence of
  `Match`/`MatchResult`/`__all__`/`__version__` (live-checked). The study's claim that "the
  module itself carries NO `__version__`" is confirmed: `repath has __version__: False`.
- **The study's line references to flet are all still accurate** — `flet/components/router.py:16`
  and the five `repath.pattern` sites at `:191/:228/:265/:287/:302`;
  `flet/controls/template_route.py:3` and `:44`; flet's unconditional floor at
  `flet-1.0.4.dist-info/METADATA:16`.
- **flet uses only `repath.pattern()`**, never `repath.match()`/`compile()`/`template()`
  (F4) — so no upstream repath defect is reachable from the app's dependency chain.

## Unverified

- **Whether the Flutter/Android host delivers a system back gesture to Python as
  `Page.on_view_pop` while the app is in single-view `page.render` mode.** The Dart client is
  not in `.venv`; `flet/controls/page.py:310-322` documents the event but the host side is out
  of scope for this audit. Consequently the F3 claim "the system back button exits the app
  instead of leaving the session" is **UNVERIFIED** — only the structural half (no view stack,
  no `on_view_pop` handler, one `View` with `can_pop=True`) is proven.
- **Whether `page.pop_dialog()` interacts with the platform back button** (i.e. whether a
  dialog can be dismissed with the system gesture rather than a tap on Cancel). Same Dart-side
  reason; the app's dialogs all offer an explicit Cancel (`src/screens/views.py:126`,
  `:204`, `:227`, `:235`, `:246`, `:254`, `:409`, `:417`; `src/screens/terminal_view.py:52`),
  so the flow is complete either way.
- **Whether `flet build` would physically retain `repath.py`/`six.py` in the APK** if they were
  ever removed from the resolved environment. flet-cli packaging behaviour is host-side
  (`flet_cli/commands/build_base.py`) and is out of this audit's scope; the sibling
  `flet-cli.md` report covers it.
- **Whether `src/LICENSES/` exists in this working tree.** It does not (`ls src/LICENSES/`
  → missing), but the same working tree has a wholesale set of deletions relative to `HEAD`
  (including `src/LICENSES/*`, `LICENSES/*`, `docs/roadmap.md`, `docs/compliance/*`) that
  sibling reports (`certifi.md`, `flet-cli.md`, `binaryornot.md`) already recorded as a
  workspace-state artifact rather than a per-package defect. Consequently
  `src/screens/views.py:628` currently renders the literal `"(text missing)"` for every
  licence text, including the MIT text that covers repath. **UNVERIFIED** whether that
  deletion is intentional. I did not restore anything — this audit is read-only apart from
  this report.
