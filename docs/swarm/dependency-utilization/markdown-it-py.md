# markdown-it-py 4.2.0 (transitive, dev-only via rich) — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/dependency-studies/markdown-it-py.md`; `docs/dependency-studies/INDEX.md:52`; `docs/reference/dep-cookiecutter-stack.md:16,19`; `docs/decisions.md:12` (D-003); `pyproject.toml:9-15,77-84`; `docs/swarm/dependency-tree/uv-tree.txt:45-47`; `docs/swarm/dependency-tree/uv-tree-inverted.txt:53-59`; `src/core/changelog.py`; `src/components/update_dialog.py`; `src/screens/onboarding_view.py`; `src/screens/views.py`; `src/services/update_service.py`; `src/core/constants.py`; `version.json`; `tests/test_imports_vs_deps.py`; `tests/test_version_sync.py`; `tests/check_flet_api.py`; `README.md`; `.venv/Lib/site-packages/markdown_it/`; `.venv/Lib/site-packages/markdown_it_py-4.2.0.dist-info/`; `.venv/Lib/site-packages/rich/markdown.py`; `.venv/Lib/site-packages/flet/controls/core/markdown.py`; `.venv/Lib/site-packages/flet/__init__.py`; `.venv/Lib/site-packages/{flet,flet_cli,flet_desktop,flet_ads,flet_terminal,httpx,rich,proot_distro}-*.dist-info/METADATA`; upstream Dart (network-fetched, not in `.venv`): `flet/packages/flet/lib/src/controls/markdown.dart`, `flet/packages/flet/lib/src/utils/images.dart`, `foresightmobile/flutter_markdown_plus/lib/src/builder.dart` · **Date:** 2026-10-20

## What it does / how the app uses it

**The app does not use markdown-it-py at all, and it must not.** The package is installed in the host venv and imported by exactly one thing in the tree — `rich`:

- `.venv/Lib/site-packages/markdown_it/__init__.py:5` — `__version__ = "4.2.0"`; `.venv/Lib/site-packages/markdown_it_py-4.2.0.dist-info/METADATA:3` — `Version: 4.2.0`; `:23` — `Requires-Dist: mdurl~=0.1` (the sole runtime dep, and `mdurl 0.1.2` is installed).
- `.venv/Lib/site-packages/rich/markdown.py:7` — `from markdown_it import MarkdownIt`; `:559` — `parser = MarkdownIt().enable("strikethrough").enable("table")`. This matches the study §7 exactly (spot-checked, not assumed).
- The app itself never touches it: `grep -rn "markdown_it\|markdown-it\|import rich\|from rich" src/ tests/ *.py` → **no output**. There is not a single mention of the package, of `rich`, or of markdown rendering anywhere in the app's own source.

**It is dev-only, and the chain is `rich`.** The full installed chain, from the swarm's own tree artifacts and the installed metadata:

```
proot-distro-flet [dev group]
└── flet-cli 1.0.4 / flet-desktop 1.0.4 / cookiecutter 2.7.1
    └── rich 15.0.0            (flet_cli METADATA:21 "Requires-Dist: rich>=13.0.0";
    │                           flet_desktop METADATA:13 same; cookiecutter METADATA:37 "Requires-Dist: rich")
        └── markdown-it-py 4.2.0   (rich-15.0.0.dist-info/METADATA:28 "Requires-Dist: markdown-it-py (>=2.2.0)")
            └── mdurl 0.1.2
```

`docs/swarm/dependency-tree/uv-tree-inverted.txt:53-59` shows the same: `mdurl → markdown-it-py → rich → cookiecutter / flet-cli / flet-desktop → proot-distro-flet (group: dev)`. `docs/swarm/dependency-tree/uv-tree.txt:45-47` shows `rich v15.0.0 → markdown-it-py v4.2.0 → mdurl v0.1.2` nested under the dev-only `flet-cli` branch. The house's own reference doc already files it under the dev CLI stack: `docs/reference/dep-cookiecutter-stack.md:16` — *"rich 15.0.0 + markdown-it-py 4.2.0 + mdurl 0.1.2 + pygments 2.21.0 (MIT/BSD) — CLI output"*.

**It cannot reach the APK.** The runtime dependency set is `pyproject.toml:9-15` (`flet`, `flet-ads`, `httpx`, `flet-terminal`, `proot-distro`) and none of them pulls `rich`:

- `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:12-18` — the only runtime requires are `oauthlib`, `httpx`, `repath`, `msgpack`, `typing-extensions`. **No `rich`.**
- `.venv/Lib/site-packages/httpx-0.28.1.dist-info/METADATA:37` — `Requires-Dist: rich<14,>=10; extra == 'cli'` → an **extra**, not a hard dep.
- `.venv/Lib/site-packages/flet_ads-1.0.4.dist-info/METADATA:14` — `Requires-Dist: flet==1.0.4`; `.venv/Lib/site-packages/flet_terminal-0.4.0.dist-info/METADATA:23` — `Requires-Dist: flet`; `.venv/Lib/site-packages/proot_distro-5.10.0.dist-info/METADATA:13` — `pytest` under the `test` extra.

Since the Android Python payload is resolved by `serious_python`'s pip from the **project dependency strings** (the same chain the msgpack audit proved: `flet_cli/commands/build_base.py:2563-2619` → `requirements`), `rich` and `markdown-it-py` are **absent from the shipped APK**.

**Meanwhile the app *does* display markdown — through Flet, not through markdown-it-py.** Flet 1.0.4 ships a native Markdown control:

- `.venv/Lib/site-packages/flet/controls/core/markdown.py:928` — `@control("Markdown") class Markdown(LayoutControl)`; `:940` `value: str = ""`; `:945` `selectable: bool = False`; `:950` `extension_set: MarkdownExtensionSet = MarkdownExtensionSet.NONE`; `:955` `code_theme`; `:962` `auto_follow_links`; `:980` `soft_line_break: bool = False`; `:996` `code_style_sheet`; `:1001` `md_style_sheet`; `:1019` `on_tap_text`; `:1024` `on_selection_change`; `:1031` `on_tap_link`; `:28` `class MarkdownExtensionSet` with `:46 GITHUB_WEB = "gitHubWeb"`.
- Exported at the top level: `.venv/Lib/site-packages/flet/__init__.py:176-180` and `:1008-1012` (`"Markdown"`, `"MarkdownExtensionSet"`, …).
- Live check: `ft.Markdown('hello', selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB)` → `value='hello' selectable=True extension_set=MarkdownExtensionSet.GITHUB_WEB`, `soft_line_break=False`, `isinstance(m, ft.LayoutControl) is True`.

The app uses it in exactly two places, both in `src/components/update_dialog.py`:

| surface | call site | content source | is it markdown? |
|---|---|---|---|
| "update available" — release notes | `src/components/update_dialog.py:67-72` | `data["release_notes"]` (remote feed) | **yes** (whatever the feed author writes) |
| "you're up to date" — bundled changelog | `src/components/update_dialog.py:88-93` | `notes_for(APP_VERSION)` → `src/core/changelog.py:5-13` | **no** — plain `"• "` text |

Everything else is plain text by design: onboarding copy (`src/screens/onboarding_view.py:15-34` — three slides, `ft.Text` at `:84-98`), the license list and license bodies (`src/screens/views.py:613-634` — `ft.Text`), and the README, which is **never displayed in the app at all** (`grep -rn "README" src/` → only `tests/test_ui_reactive.py:83`, which reads the file to assert a doc claim).

**Answer to the assignment question, in one line:** markdown-it-py is dev-only (rich chain) and correctly so; the app's markdown rendering is already covered by `ft.Markdown` (flet 1.0.4, Flutter-side), so the *package* needs no action — but the app's *own* changelog/notes content is plain text fed to a markdown renderer, and the renderer collapses it. That is where the real defects are.

## Findings

### F1 · P2 · The bundled changelog is not markdown, and Flet's Markdown renderer collapses its five lines into one run-on paragraph

- **Where:** `src/core/changelog.py:5-13` (content) → `src/components/update_dialog.py:88-93` (the `ft.Markdown` that renders it); `.venv/Lib/site-packages/flet/controls/core/markdown.py:980` (`soft_line_break: bool = False`); upstream Dart `packages/flet/lib/src/controls/markdown.dart:70`; `flutter_markdown_plus/lib/src/builder.dart:118,330,341-344`.
- **What:** the changelog body is five plain lines joined by `\n`, each starting with a literal `•` character. It is handed to `ft.Markdown`, which parses it as **one paragraph** (a `•` is not a markdown list marker, and there is no blank line between the lines). Flet then renders it through `flutter_markdown_plus`, whose `trimText` replaces every soft line break with a **space** unless `soft_line_break` is set — and Flet's default is `false`:
  ```dart
  // packages/flet/lib/src/controls/markdown.dart:70
  softLineBreak: control.getBool("soft_line_break", false)!,
  // flutter_markdown_plus/lib/src/builder.dart:330,341-344
  final RegExp softLineBreakPattern = RegExp(r' ?\n *');
  if (softLineBreak) { return text; }
  return text.replaceAll(softLineBreakPattern, ' ');
  ```
  Neither `ft.Markdown` call site sets `soft_line_break`, so the "You're up to date" body renders as a single wall of text with the `•` characters still literal. The Markdown renderer is being given prose it cannot format.
- **Evidence:** the exact Dart rule applied to the shipped changelog string:
  ```
  CHANGELOG['1.0.0'] collapsed by softLineBreak=false ->
     • Real Linux containers on Android — no root, no Termux • Install any Docker image: type a reference or search Docker Hub • Interactive shells in every container, with the extra-keys bar • Manage containers: rename, back up, restore, copy, reset, remove • Light and dark themes, following the system by default
  ```
  (one line, 380 chars, five `•` and zero line breaks — produced by applying `re.sub(r' ?\n *', ' ', body)` to the literal at `src/core/changelog.py:7-11`).
- **Fix / opportunity (minimal, two independent options — the first needs no code change):**
  1. **Author the changelog as real markdown** in `src/core/changelog.py:5-13` — `- Real Linux containers on Android — no root, no Termux\n- Install any Docker image…` — and use a blank line between the title and the list. Each item then becomes its own `<li>`, renders as a proper bullet list, and the same string can carry `**bold**`, links and `##` headings. This is a content change only; `ft.Markdown` at `src/components/update_dialog.py:88` already does the rest. (The `• ` prefix should be dropped — the renderer adds the bullet.)
  2. Or, if the content must stay prose, set `soft_line_break=True` on the `ft.Markdown` at `src/components/update_dialog.py:88` (the Python kwarg exists — `.venv/Lib/site-packages/flet/controls/core/markdown.py:980`). This is one argument and fixes the collapse for *any* line-oriented content, including the remote feed's notes.
  Doing (1) **and** (2) is the right combination: (1) makes the bundled text idiomatic markdown, (2) makes the dialog robust against a feed whose notes are written as plain lines.
- **Risk if ignored:** the entire "What's New" panel is one unreadable run-on line on a phone. The five selling points — the whole point of the changelog — are unreadable in the "You're up to date" dialog, which is the dialog the user opens from the header on every fresh install.

### F2 · P2 · `notes_for()` falls back to the **oldest** changelog entry, contradicting its own docstring

- **Where:** `src/core/changelog.py:16-18`.
- **What:**
  ```python
  def notes_for(version: str) -> str:
      """The changelog entry for a version, falling back to the newest one."""
      return CHANGELOG.get(version) or next(iter(CHANGELOG.values()), "")
  ```
  `next(iter(CHANGELOG.values()))` returns the **first-inserted** entry, not the newest. Python dicts preserve insertion order, and the literal at `src/core/changelog.py:5-13` is written oldest-first, so the fallback is the *oldest* note — the opposite of the docstring. Today the two coincide (there is only `"1.0.0"`, and `APP_VERSION == "1.0.0"` at `src/core/constants.py:11`, so the `.get()` hit path is taken and the fallback never runs). The moment a `"1.0.1"` entry is appended, the fallback starts serving 1.0.0's news.
- **Evidence:** simulation of the exact expression with a two-entry changelog:
  ```
  simulated notes_for("9.9.9") with 1.0.0+1.0.1 present -> 'old notes'
  (docstring says: falling back to the NEWEST one)
  ```
  The current test cannot catch it: `tests/test_version_sync.py:29-31` asserts `APP_VERSION in CHANGELOG` and `notes_for(APP_VERSION)` — always the `.get()` hit path.
- **Fix / opportunity (minimal):** make the fallback actually mean "newest" instead of "first inserted". The version keys are dotted numeric strings, so order them numerically, not lexically (`"1.0.10" < "1.0.9"` lexicographically):
  ```python
  def notes_for(version: str) -> str:
      """The changelog entry for a version, falling back to the newest one."""
      if version in CHANGELOG:
          return CHANGELOG[version]
      if not CHANGELOG:
          return ""
      newest = max(CHANGELOG, key=lambda v: tuple(int(p) for p in v.split(".")))
      return CHANGELOG[newest]
  ```
  Alternatively, keep the literal newest-first and say "first entry" in the docstring — but newest-first is the wrong order for a human reading a changelog, so the numeric max is the better rule. Worth adding one test that pins the fallback (`notes_for("99.0.0")` must equal the newest entry's notes) so the two cannot drift again.
- **Risk if ignored:** after the next release, any lookup miss — including the `notes_for(APP_VERSION)` call at `src/components/update_dialog.py:89` if the version constant and the changelog ever disagree — shows *stale* release notes labelled as the current build's news. `tests/test_version_sync.py:29` currently guarantees the two agree, which is why this is a latent (P2) rather than a live defect.

### F3 · P2 · The licenses dialog truncates five of the seven license texts at 6000 characters while promising "Full texts below"

- **Where:** `src/screens/views.py:626-634` (the slice) and `src/screens/views.py:636-643` (the promise); `_TEXT_FILES` at `src/screens/views.py:43-51`.
- **What:** each license body is read and cut:
  ```python
  body = path.read_text(encoding="utf-8")[:6000] if path.is_file() else "(text missing)"
  ```
  The dialog's own header says *"This app includes third-party software. **Full texts below**; the same texts ship in the repository's LICENSES/ directory."* — but 6000 characters is far short of the actual texts. Measured against the tracked files (`git show HEAD:src/LICENSES/<file>`):
  | file | bytes | shown in the app |
  |---|---|---|
  | `GPL-3.0.txt` | 35 147 | ~17 % |
  | `GPL-2.0.txt` | 19 106 | ~31 % |
  | `MPL-2.0.txt` | 16 726 | ~36 % |
  | `PSF-2.0.txt` | 13 936 | ~43 % |
  | `Apache-2.0.txt` | 11 357 | ~53 % |
  | `BSD-3-Clause.txt` | 1 529 | 100 % |
  | `MIT.txt` | 1 071 | 100 % |
  The cut is invisible to the user: the body is a `ft.Text(body, size=9, selectable=True)` with no ellipsis and no "truncated" marker (`src/screens/views.py:632`). GPL-3.0's §4 "Corresponding Source" and §5 "License notices" obligations are exactly the parts that live past the cut.
- **Evidence:** the byte counts above, from `git show HEAD:src/LICENSES/<file> | wc -c`; the slice at `src/screens/views.py:628`; the promise at `src/screens/views.py:639-640`.
- **Fix / opportunity (minimal):** drop the slice and let the control hold the whole text — `ft.Text(body, size=9, selectable=True)` renders 35 KB of text without trouble, and the surrounding `ft.Column` already has `scroll=ft.ScrollMode.AUTO` (`src/screens/views.py:693`), so the `ExpansionTile` body scrolls with the dialog. If a bound is kept for a reason not visible in the code, it must be visible to the user: append a "… (text truncated)" marker and stop claiming "Full texts below" at `src/screens/views.py:639`.
- **Risk if ignored:** incomplete license attribution for GPL-2.0/GPL-3.0/MPL-2.0/Apache-2.0 components — a compliance exposure, and a mismatch between what the app claims and what it shows. (Note: the same screen is the app's §3.3 compliance surface, so this is squarely a compliance defect, not cosmetic.)
- **Worktree caveat (not a code defect):** in the current worktree `src/LICENSES/` is **absent** — `git status --short` shows 24 uncommitted deletions including all seven `src/LICENSES/*.txt` files — so the `else` branch fires and every tile shows the literal string `"(text missing)"` (`src/screens/views.py:628`). The files exist in HEAD. I did not touch the worktree; flagging it because any other agent (or a test run) in this workspace will see the same missing directory.

### F4 · P3 · The update feed's `release_notes` are the same `• ` plain text, so the "update available" dialog collapses the same way

- **Where:** `version.json:6` (the feed payload) → `src/services/update_service.py:95` → `src/components/update_dialog.py:66-74`.
- **What:** the shipped feed's release notes are `"• Real Linux containers on Android — no root, no Termux\n• Install any Docker image, or search Docker Hub\n…"` — identical shape to the bundled changelog (F1). The remote path *is* rendered by a markdown renderer (`ft.Markdown`, `src/components/update_dialog.py:67`), and the remote content is the one place where real markdown is expected to arrive. Today the renderer is fed prose, so it collapses exactly as in F1. Note the two notes sources have already drifted from each other (`src/core/changelog.py:8` says "type a reference **or** search Docker Hub"; `version.json:6` says "**or** search Docker Hub"), which is a second symptom of the same split source of truth.
- **Evidence:** `version.json:6` (verbatim above); `src/services/update_service.py:95` — `"release_notes": _safe_text(data.get("release_notes"), 10000)` (a 10 000-char cap, no format contract); `src/components/update_dialog.py:66-74` renders it with `ft.Markdown`.
- **Fix / opportunity (minimal):** author the feed's `release_notes` as markdown (a `- ` list, optionally with a `##` heading and a `**bold**` lead) — the renderer already supports it, and `MarkdownExtensionSet.GITHUB_WEB` (`src/components/update_dialog.py:70`) already gives GitHub-flavoured tables/strikethrough/autolinks. Add `soft_line_break=True` to this `ft.Markdown` as well, so a feed written as plain lines still reads as lines. Then consider generating `version.json`'s notes from `src/core/changelog.py` (one source of truth) instead of maintaining two copies.
- **Risk if ignored:** the update dialog — the one screen the user sees when a new version is offered — is a wall of text. Low severity because it is one line of copy away from being fixed.

### F5 · P3 · markdown-it-py must stay dev-only — three independent reasons, so the study's "Track B" stays declined

- **Where:** `docs/dependency-studies/markdown-it-py.md:190-209` (Track A at `:190`, Track B at `:197`, "an M4 plan-mode proposal" at `:209`); `docs/dependency-studies/INDEX.md:52` ("candidate for in-app markdown rendering (M4 decision)"); `docs/decisions.md:12` (D-003, frozen dependency set); `pyproject.toml:9-15`; `tests/test_imports_vs_deps.py:46-59`; `tests/check_flet_api.py:52-58`.
- **What:** the study leaves in-app rendering open ("Track B — in-app markdown rendering (option, NOT a decision)"). The evidence gathered in this audit closes it against the current architecture:
  1. **D-003 freezes the runtime set** (`docs/decisions.md:12`: *"Runtime: `flet`, `flet-ads`, `proot-distro`, `flet-terminal` … Dev: `flet-cli`, `flet-desktop`, `pytest`, `pytest-timeout`, `ruff`. Any addition needs owner sign-off."*). Adding `markdown-it-py` to `pyproject.toml` is an owner decision, not an audit decision.
  2. **The house import guard already forbids it.** `tests/test_imports_vs_deps.py:46-59` fails any `src/` import whose distribution is not in `[project].dependencies` (+ the `tool.flet.<platform>.dependencies` tables). `markdown_it`'s provider distribution is `markdown-it-py`, which is in neither → an app-side `import markdown_it` fails CI today, by design. The docstring at `tests/test_imports_vs_deps.py:2-6` states the reason: *"`flet build` resolves ONLY the project dependencies; a desktop-only import that isn't declared crashes the packaged app on Android."*
  3. **It would duplicate a capability the app already ships natively.** Flet 1.0.4 renders markdown in Dart (`ft.Markdown`, `.venv/Lib/site-packages/flet/controls/core/markdown.py:928`, backed by `flutter_markdown_plus`). Shipping a pure-Python markdown parser into the APK to re-derive HTML that a native control already renders is a net loss: extra APK size, an extra pure-Python dependency to maintain on the Android resolve, and a `Token → ft.Control` mapper to write and test. The study's own §8 says exactly this ("writing and owning a `Token → ft.Markdown`/`ft.TextSpan` mapper … carrying it in the APK forever against the owner's minimal-deps rule").
- **Evidence:** the import-guard rule above; `pyproject.toml:9-15` (no rich, no markdown-it-py); `flet-1.0.4.dist-info/METADATA:12-18` (no rich anywhere in flet's runtime requires) → neither package is in the Android resolve. Live: `grep -rn "markdown_it\|import rich\|from rich" src/ tests/ *.py` → no output.
- **Fix / opportunity:** none in the app. Record the ruling where a future reader will look: the study's §8 already says Track B needs an explicit M4 plan-mode proposal with a mapper line-count estimate; this audit's contribution is that **Flet already provides the mapper** (`ft.Markdown`), so the correct answer to "can we render markdown in-app?" is *"yes, and we already do"* — not *"ship a parser"*.
- **Risk if ignored:** the failure mode is not a bug but a regression in scope: an agent (or a well-meaning owner) reading `docs/dependency-studies/INDEX.md:52` could add `markdown-it-py` to `pyproject.toml` to "enable in-app markdown", shipping a ~1 MB pure-Python parser into the APK to replace a native control that is already wired up at `src/components/update_dialog.py:67` and `:88`.

### F6 · P3 · Remote images embedded in release notes are fetched without a host allowlist (link taps are gated; image loads are not)

- **Where:** `src/components/update_dialog.py:71` and `:92` (the `on_tap_link` handler, which *is* gated); upstream Dart `packages/flet/lib/src/controls/markdown.dart:60-66` (the `imageBuilder`) and `packages/flet/lib/src/utils/images.dart:91-95`.
- **What:** link taps go through `_launch` → `is_allowed_launch_url` (`src/components/update_dialog.py:23-26`, `src/services/update_service.py:26-37`), so only `github.com` / `raw.githubusercontent.com` / `play.google.com` may open. **Images in the same markdown are not gated**: Flet's `imageBuilder` resolves the URL through `getAssetSource` and, for anything that is not a local file, builds a `NetworkImage`:
  ```dart
  // packages/flet/lib/src/utils/images.dart:91-95
  if (resolvedSrc.hasUri) {
    var assetSrc = FletBackend.of(context).getAssetSource(resolvedSrc.uri!);
    return assetSrc.isFile ? getFileImageProvider(assetSrc.path) : NetworkImage(assetSrc.path);
  }
  ```
  So a `![](https://…/pixel.png)` in the release notes causes a network fetch to an arbitrary host. The feed is first-party (`src/core/constants.py:17` — `UPDATE_CONFIG_URL = https://raw.githubusercontent.com/Nwokike/proot-distro/main/version.json`) and pinned to the repo, so this is a low-probability, low-impact exposure today — but it is a shape that matters if the feed ever becomes editable by a third party, and it is a network request the privacy policy does not mention (`PRIVACY.md:27-43` lists only container registries and AdMob; the update-feed fetch at `src/services/update_service.py:75` is not listed either).
- **Evidence:** the Dart snippets above; `src/components/update_dialog.py:23-26` and `src/services/update_service.py:26-37` (the link gate); `PRIVACY.md:43` — *"Network interactions are limited to the container registries you connect to and Google AdMob as described above."*
- **Fix / opportunity (minimal):** the cheapest control is to render remote notes with images suppressed — pass `image_error_content=` is not a suppress switch; the effective options are (a) strip `![…](…)` from the feed text before rendering (a two-line regex in `src/services/update_service.py:95`, where the text is already sanitised and capped), or (b) publish the feed's notes without images and treat "the feed may contain images" as out of contract. Since the feed is our own file, (b) plus a line in the release runbook is enough. Separately, `PRIVACY.md:29-43` should mention the update-feed request to `raw.githubusercontent.com` so the disclosure matches the code.
- **Risk if ignored:** low. A tracking pixel in a release note would leak the device's IP and the fact that the app updated, to a host the app never allowlists.

## Missed capabilities (dependency audits only)

markdown-it-py's API is large and completely unused by the app (by design, F5). The capabilities that are genuinely on the table, with API location, integration point and value-vs-cost:

- **`MarkdownIt.parse(src) -> list[Token]`** · `.venv/Lib/site-packages/markdown_it/main.py:252`; `Token` at `.venv/Lib/site-packages/markdown_it/token.py` · Integration point: a **host-side** markdown linter for `docs/` (new `tools/` script, run in the `quality` job of `.github/workflows/app.yml`) · Value: catch broken relative links by walking `link_open` tokens' `href` attrs, and flag fenced blocks with an empty `fence.info` · Cost: ~40 lines, **zero new dependencies** (the package is already in the dev venv; D-003 is untouched because it only constrains the *runtime* set) · The repo's `docs/` now holds 47 dependency studies + 20 swarm reports with dozens of cross-links, so the link check has real yield.
- **`MarkdownIt.render(src) -> str`** (HTML) and **`renderInline`** · `.venv/Lib/site-packages/markdown_it/main.py:275,309` · Integration point: the same host-side script, to render a release-notes draft to HTML for the GitHub Release body · Cost: trivial · Value: the same renderer the docs were validated against, per the study's Track A. Note this is *host/CI only* — it must never run on device.
- **`MarkdownIt.validateLink(url) -> bool`** · `.venv/Lib/site-packages/markdown_it/main.py:323` (delegates to `mdurl`) · Integration point: a host-side check for the release-feed URLs · Value: one call to reject `javascript:` / `vbscript:` / `file:` destinations in authored markdown before it is published to `version.json`. **Note:** this does **not** replace `is_allowed_launch_url` (`src/services/update_service.py:26-37`) — that allowlist is host-based and is the app's real control; `validateLink` is scheme-based and complementary.
- **`MarkdownIt.enable/disable/configure/set`** · `.venv/Lib/site-packages/markdown_it/main.py:160,192,104,104`; presets at `.venv/Lib/site-packages/markdown_it/presets/{commonmark,default,zero}.py` · Integration point: the host-side linter's config (e.g. `MarkdownIt("commonmark").enable("table")`) · Caveat worth recording: the commonmark preset ships `"html": True` (`.venv/Lib/site-packages/markdown_it/presets/commonmark.py:17`) while the default preset ships `"html": False` (`.venv/Lib/site-packages/markdown_it/presets/default.py:10`) — a linter that wants CommonMark-strict behaviour should use `MarkdownIt("default")` or explicitly `md.set({"html": False})`, otherwise raw HTML in a doc passes through unflagged.
- **`rich.markdown.Markdown`** · `.venv/Lib/site-packages/rich/markdown.py:513` with its own parser at `:559` (tables + strikethrough enabled, linkify/smartquotes **not**) · Integration point: a *console* markdown preview in the same host-side script, printing the rendered doc to a terminal during review · Cost: ~5 lines, and it needs **no** new import of `markdown_it` at all — rich is already installed in the dev venv.
- **In-app markdown rendering — ALREADY SHIPPED, do not re-add.** `ft.Markdown` (`.venv/Lib/site-packages/flet/controls/core/markdown.py:928`) is the in-app capability, with `extension_set` (`:950`), `selectable` (`:945`), `on_tap_link` (`:1031`), `code_theme` (`:955`), `md_style_sheet` (`:1001`), `code_style_sheet` (`:996`), `on_tap_text` (`:1019`), `on_selection_change` (`:1024`), `image_error_content` (`:991`), `auto_follow_links` (`:962`) and `soft_line_break` (`:980`) still unused by the app. The unused knobs that matter for *this* app's content: `soft_line_break` (F1/F4), `md_style_sheet` (to align the dialog's markdown with the house type scale in `src/core/tokens.py`), and `code_theme` (the release notes are the only place a fenced block could appear).
- **Track B (ship markdown-it-py into the APK) — declined**, see F5. No integration point is proposed because the capability already exists natively.

## Verified-good list

- `ft.Markdown` **exists** in the installed Flet 1.0.4 and is exported at the top level: `.venv/Lib/site-packages/flet/controls/core/markdown.py:928`, `.venv/Lib/site-packages/flet/__init__.py:176-180,1008-1012`. Live-instantiated successfully. `ft.MarkdownExtensionSet.GITHUB_WEB` exists (`markdown.py:46`, value `"gitHubWeb"`). No HALLUCINATION in `src/components/update_dialog.py`.
- The two `ft.Markdown` call sites use the API correctly: `value` is passed positionally and is the first dataclass field (`.venv/Lib/site-packages/flet/controls/core/markdown.py:940`); `selectable=True`, `extension_set=…GITHUB_WEB`, `on_tap_link=…` are all real fields (`:945`, `:950`, `:1031`).
- `on_tap_link` really does deliver the URL in `Event.data`: the Python docstring says so (`.venv/Lib/site-packages/flet/controls/core/markdown.py:1031-1040`) and the Dart side fires it with the href (`packages/flet/lib/src/controls/markdown.dart:91-95` → `control.triggerEvent("tap_link", href)`). The app's `lambda e: _launch(page, e.data)` (`src/components/update_dialog.py:71,92`) is correct.
- Link taps are **allowlisted** before anything opens: `_launch` → `is_allowed_launch_url` (`src/components/update_dialog.py:23-26`; `src/services/update_service.py:26-37`) — https only, and only `github.com` / `raw.githubusercontent.com` / `play.google.com` (plus their subdomains). `auto_follow_links` is left at its `False` default (`.venv/Lib/site-packages/flet/controls/core/markdown.py:962`), so Flet does not open URLs behind the app's back — the app's own handler is the only path.
- The remote release notes are length-capped before rendering: `src/services/update_service.py:95` truncates to 10 000 chars, and every URL in the feed payload passes `_safe_url` (`src/services/update_service.py:44-47`), so a hostile feed cannot smuggle an arbitrary link into the dialog.
- The Flet API guard passes and the `ft.*` chains the app uses exist in the installed flet. CI runs it over **every** file in `src/` (`.github/workflows/app.yml:55-58` — `for f in $(find src -name "*.py"); do … tests/check_flet_api.py "$f"`), and a local run on the markdown surface passes with the markdown chains explicitly listed:
  ```
  $ .venv/Scripts/python.exe tests/check_flet_api.py src/components/update_dialog.py
  flet 1.0.4 — 25 chain(s) referenced in src\components\update_dialog.py
    ok     ft.Markdown
    ok     ft.MarkdownExtensionSet
    ok     ft.MarkdownExtensionSet.GITHUB_WEB
  OK: every referenced flet API chain exists in the installed version.
  exit=0
  ```
  (Invoked with the default `src/main.py` it walks a single chain, `ft.run`; the per-file loop above is the CI form.)
- The app's markdown-it-py usage is **absent**, not accidental: `grep -rn "markdown_it\|markdown-it\|import rich\|from rich" src/ tests/ *.py` → no output; the runtime dependency list (`pyproject.toml:9-15`) contains no `rich`; and flet's own metadata has no `rich` require (`.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:12-18`).
- The study's API claims about the installed package all spot-check correct: `MarkdownIt` at `.venv/Lib/site-packages/markdown_it/main.py:33` with `config="commonmark"` default (`:36`); `parse` (`:252`), `render` (`:275`), `parseInline` (`:289`), `renderInline` (`:309`), `validateLink` (`:323`), `normalizeLink` (`:333`), `normalizeLinkText` (`:343`), `set` (`:94`), `configure` (`:104`), `get_all_rules` (`:142`), `get_active_rules` (`:151`), `enable` (`:160`), `disable` (`:192`), `use` (`:235`), `add_render_rule` (`:225`), `reset_rules` (`:216`). Live options dict: `{'maxNesting': 20, 'html': True, 'linkify': False, 'typographer': False, 'quotes': '“”‘’', 'xhtmlOut': True, 'breaks': False, 'langPrefix': 'language-', 'highlight': None}` — identical to the study §1. Live active rules: no `table`, no `strikethrough` under the commonmark preset (the study §5) — which is exactly why rich re-enables them at `rich/markdown.py:559`.
- `markdown-it-py`'s optional extras are all absent, as the study states: `linkify-it-py` and `mdit-py-plugins` are not installed (`.venv/Lib/site-packages/markdown_it_py-4.2.0.dist-info/METADATA:33-34` declare them as extras only). Consequently `linkify` is a no-op even if the rule is enabled.
- The onboarding copy is plain prose in `ft.Text` and needs no markdown renderer: `src/screens/onboarding_view.py:15-34` (three slide dicts) rendered at `:84-98`. Titles use an explicit `\n` in a `ft.Text` (`src/screens/onboarding_view.py:18,24,30`) — correct for Flet, which does not process `\n` in markdown anyway.
- The license **list** rows (`src/screens/views.py:613-623`) are plain `ft.Text` with a literal `• ` prefix — the right control for a one-line row; converting them to `ft.Markdown` would only cost a Dart-side markdown parse per row.
- The README is **not** displayed in the app, so there is no markdown-rendering gap there: `grep -rn "README" src/` → only `tests/test_ui_reactive.py:83` (a test reading the file to assert a doc claim).
- The app never imports `markdown_it`; were it to, `tests/test_imports_vs_deps.py:46-59` would fail the build with *"imports without a declared dependency"* — the house guard and D-003 agree.
- `src/components/update_dialog.py:33` uses `except TypeError, ValueError:` — valid **only** under PEP 758 (unparenthesized except tuples), which the project targets: `pyproject.toml:8` `requires-python = ">=3.14"`, `.python-version` = `3.14`, and the installed interpreter is 3.14.7. Live check confirms it parses and runs. **Not** a bug — and an AST sweep of all 32 files under `src/` found **zero** syntax errors.

## Unverified

- **The rendered result on a device/emulator.** The soft-line-break collapse (F1, F4) is proved from the exact upstream Dart sources (`packages/flet/lib/src/controls/markdown.dart:70` and `flutter_markdown_plus/lib/src/builder.dart:118,330,341-344`) and reproduced in Python by applying the same regular expression, but no Android build was run and no screenshot was taken. `flutter_markdown_plus` is the *current* pub release (1.0.12, `https://pub.dev/api/packages/flutter_markdown_plus`) — the version Flet 1.0.4 pins in its own pubspec was not independently confirmed, and the `trimText` rule quoted above is from the current `main` of that repository.
- **The exact Flet Dart control file in the 1.0.4 tag.** The Dart sources cited are from `flet-dev/flet@main` (fetched over the network; the Dart code is not present in `.venv`). The Python side of 1.0.4 is authoritative for the API surface, and the property names line up (`soft_line_break` in Python, `soft_line_break` read in Dart), but the 1.0.4 tag's Dart file was not diffed against `main`.
- **The `src/LICENSES/` worktree deletion (F3 caveat).** 24 files are deleted in the worktree but present in HEAD. I did not restore them (read-only audit) and could not determine whether the deletion is intentional (a pruning pass) or an artifact of a concurrent branch operation. The byte counts used in F3 are from `git show HEAD:src/LICENSES/…`.
- **The exact rendered `ft.Markdown` output for the remote feed's notes.** The feed is first-party (`src/core/constants.py:17`), so only the shipped `version.json` content was analysed; notes published in a future release were not available.
- **Whether `ft.Markdown`'s `md_style_sheet` can be driven from the house tokens** (`src/core/tokens.py`) to match the app's type scale was not prototyped; it is listed as an available knob, not as a validated integration.
- **The size cost of shipping markdown-it-py into the APK** (a rough "~hundreds of KB" from the study) was not measured here; F5's argument rests on D-003, the import guard, and the existence of a native renderer, none of which depend on the number.
