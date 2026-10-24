# qrcode — audit

**Verdict:** PERFECT
**Confidence:** high
**Scope:** `.venv/Lib/site-packages/qrcode/__init__.py:1-30` · `.venv/Lib/site-packages/qrcode/constants.py:1-5` · `.venv/Lib/site-packages/qrcode/main.py:22-26,28-48,74-99,132-146,286-327,339-387,515` · `.venv/Lib/site-packages/qrcode/console_scripts.py:25,35,43` · `.venv/Lib/site-packages/qrcode-8.2.dist-info/METADATA:1-15` · `.venv/Lib/site-packages/qrcode-8.2.dist-info/entry_points.txt:2` · `.venv/Lib/site-packages/flet_cli/commands/run.py:16,584-591,638-677` · `.venv/Lib/site-packages/flet_cli/cli.py:16` · `.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA:16` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2564,2566-2576,2605-2606,2608-2619,2770-2786` · `.venv/Lib/site-packages/flet_cli/utils/project_dependencies.py:110-133` · `.venv/Lib/site-packages/flet/controls/services/share.py:162-204,206-233,235-283,331-372` · `.venv/Lib/site-packages/flet/controls/core/text.py:251` · `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:33` · `pyproject.toml:9-15,30-31,52,62-63,78-84` · `uv.lock:230,709-717` · `src/` (all 32 files; 27 importable modules — 5 are `__init__.py`) · `src/core/constants.py:16-20` · `src/core/shared_services.py:12-18,21-50,53-66` · `src/components/update_dialog.py:23-26,129-143` · `src/screens/views.py:26-42,527,600-606` · `src/services/update_service.py:23,26-37` · `tests/test_imports_vs_deps.py:18-59` · `.github/workflows/app.yml:159,213` · `docs/decisions.md:12-13,18-19` · `docs/dependency-studies/qrcode.md` (study, prior knowledge) · **Date:** 2026-10-22

## What it does / how the app uses it

qrcode 8.2 is a **pure-Python QR encoder** (`qrcode/main.py`) plus image factories
(`qrcode/image/`) and a `qr` console script (`.venv/Scripts/qr.exe`, entry point
`qr=qrcode.console_scripts:main` at `.venv/Lib/site-packages/qrcode-8.2.dist-info/entry_points.txt:2`).

**The app does not use qrcode at all — and there is no product surface that would
want it.** It is a **dev-only transitive dependency of `flet-cli`**:

- `.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA:16` — `Requires-Dist: qrcode>=7.4.2` (no environment marker).
- `uv.lock:230` — the **only** edge in the whole lock file that names qrcode is flet-cli's; `uv.lock:709-717` pins qrcode 8.2 with a single dependency, `colorama` (win32 marker only, `uv.lock:712-714`).
- `docs/swarm/dependency-tree/uv-tree-inverted.txt:35-37` — the inverted tree agrees: `qrcode v8.2 → flet-cli v1.0.4 → proot-distro-flet (group: dev)`.
- `flet-cli` is a **dev-group** member only (`pyproject.toml:78-84`); the frozen runtime set is `flet`, `flet-ads`, `httpx`, `flet-terminal`, `proot-distro` (`pyproject.toml:9-15`), matching D-003 (`docs/decisions.md:12-13`).

**qrcode is provably NOT in the APK.** `flet build` resolves dependencies *only* from
`project.dependencies` and `tool.flet.<platform>.dependencies`
(`.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576`, normalized by
`.venv/Lib/site-packages/flet_cli/utils/project_dependencies.py:110-133`, then handed to the
packager at `build_base.py:2605-2606`). Live evaluation of that exact function against this repo's
`pyproject.toml`:

```text
project.dependencies -> ['flet >=1.0.4', 'flet-ads >=1.0.4', 'flet-terminal >=0.4.0', 'httpx >=0.28.1', 'proot-distro >=5.10.0']
tool.flet.android.dependencies -> ['flet-proot==5.1.107.98']
qrcode in build deps: False
flet-cli in build deps: False
pillow in build deps: False
```

The `src/requirements.txt` fallback branch (`build_base.py:2608-2617`) is not taken —
`src/requirements.txt` does not exist — and the final fallback (`build_base.py:2619`) would
install only `flet==<version>`. `[tool.flet.cleanup].package_files = ["oauthlib/**"]`
(`pyproject.toml:62-63`, consumed at `build_base.py:2770-2786`) prunes oauthlib only; qrcode
never needs pruning because it is never installed into the packaged site-packages.

**The single consumer is flet-cli's device-connect QR, and this repo never triggers it.**
`import qrcode` is top-level at `.venv/Lib/site-packages/flet_cli/commands/run.py:16`, and
`flet_cli/cli.py:16` imports `flet_cli.commands.run` at top level. The QR is printed only on the
mobile branches:

```text
.venv/Lib/site-packages/flet_cli/commands/run.py:584-591
        if (
            self.page_url.startswith("http")
            and not self.ios
            and not self.android
        ):
            print(self.page_url)
        if self.ios or self.android:
            self.print_qr_code(self.page_url, self.android)
```

`print_qr_code` (`run.py:638-677`) renders the LAN URL as `https://android.flet.dev/<ip:port/path>`
for Android or `flet://flet-host/<lan_url>` otherwise (`run.py:655-670`), then:

```text
.venv/Lib/site-packages/flet_cli/commands/run.py:672-674
        qr = qrcode.QRCode()
        qr.add_data(qr_url)
        qr.print_ascii(invert=True)
```

That branch needs `flet run --android` / `--ios` (flags confirmed at `run.py:169,176`; help text
`--ios  Launch the app on an iOS device` / `--android  Launch the app on an Android device`).
The house dev loop is plain `uv run flet run` (`docs/decisions.md:18-19`), and CI only runs
`uv run flet build apk` / `uv run flet build aab` (`.github/workflows/app.yml:159,213`) — **never
`flet run`, never a mobile target**. So the QR path is dead code in this repo's own workflows.

## Findings

### F1 · P3 · qrcode is correctly dev-only and provably absent from the shipped APK
- **Where:** `pyproject.toml:9-15` (runtime deps) · `pyproject.toml:78-84` (dev group) · `uv.lock:230` · `.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA:16` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576,2605-2606` · `.venv/Lib/site-packages/flet_cli/utils/project_dependencies.py:110-133`
- **What:** qrcode is neither a declared dependency nor a transitive dependency of any *runtime* dependency — its only path to this project is `flet-cli` → qrcode, and `flet-cli` is dev-group-only. Because `flet build` installs only `project.dependencies` + `tool.flet.<platform>.dependencies`, qrcode never enters the packaged site-packages and therefore never enters the APK. This is the correct end state and requires no action.
- **Evidence:** the live `get_project_dependencies` evaluation quoted in "What it does" returns `qrcode in build deps: False`. Cross-checked against `docs/swarm/dependency-tree/uv-tree-inverted.txt:35-37`, whose only qrcode edge is flet-cli's.
- **Fix / opportunity:** none. Do **not** add `qrcode` to `pyproject.toml:9-15`, and do **not** add `qrcode/**` to `[tool.flet.cleanup].package_files` (`pyproject.toml:62-63`) — the glob would be a no-op against a package that was never installed, and adding the dependency would be the actual regression (see F4).
- **Risk if ignored:** none user-visible. The only real risk is the inverse mistake — declaring qrcode to "use" it (see F4) — which would add ~46 KB of pure-Python encoder plus its `colorama` dependency to every APK install for a feature that does not exist.

### F2 · P3 · The app has no QR surface and no URL-sharing path; every URL is an outbound "open in browser" link
- **Where:** `src/core/constants.py:16-20` · `src/components/update_dialog.py:129-143` · `src/screens/views.py:527` · `src/core/shared_services.py:53-66` · `src/services/update_service.py:23,26-37` · `src/screens/views.py:26-42,600-606`
- **What:** the app's entire URL surface is **five constants** and **three launch points**, all of which open a URL in the system browser through `ft.UrlLauncher`:
  - `GITHUB_RELEASES_URL`, `UPDATE_CONFIG_URL`, `PLAY_STORE_URL`, `PRIVACY_POLICY_URL`, `TERMS_OF_SERVICE_URL` (`src/core/constants.py:16-20`),
  - "Google Play" + "Release page" buttons in the update dialog (`src/components/update_dialog.py:129-143`),
  - "Privacy policy" in Settings (`src/screens/views.py:527`),
  - all funnelled through `launch_url` → `ft.UrlLauncher.launch_url` (`src/core/shared_services.py:58-66`) and constrained by the https + host allowlist `("github.com", "raw.githubusercontent.com", "play.google.com")` (`src/services/update_service.py:23,26-37`).
  There is **no** invite code, no account, no remote-container connection, no docs-site link, and no donate/sponsor surface. `grep -rniE "\bssh\b|port.?forward|\bremote\b|tunnel|listen|localhost|127\.0\.0\.1"` over `src/` returns only the word "remote" in the update-service prose (`src/services/update_service.py:65-67`, `src/components/update_dialog.py:4-5`) — the app runs containers locally on the device and never listens or connects out to one.
- **Evidence:**
  ```text
  $ grep -rni "qrcode|qr_code|\bqr\b|qr-" src/ tests/ .github/ build_flet_proot_wheel.py
  (no matches — exit 1)
  $ grep -rn "https\?://" src/ --include=*.py
  src/core/constants.py:16,17,18,19,20   (the five URL constants)
  src/screens/views.py:650                (GPL source-offer text, selectable, not a link control)
  src/services/proot_service.py:216       (docstring example of a container image ref)
  ```
  `qrcode` is also correctly absent from the app's own open-source-licenses list, which enumerates shipped runtime packages by hand (`_PY_DISTS`, `src/screens/views.py:26-42`, rendered by `_py_entries()` at `src/screens/views.py:600-606`) — consistent with qrcode not being in the APK. `PLAY_STORE_URL` (`src/core/constants.py:18`) is defined but never referenced by any view.
- **Fix / opportunity:** none. There is no QR surface to add and no product flow that would justify one.
- **Risk if ignored:** none. The absence of a QR/share surface is a **feature gap with no consumer**, not a defect: the app has no account system, no invite mechanic, and no remote-container endpoint — a QR code would have nothing to encode except an outbound link the user can already tap.

### F3 · P3 · The one candidate surface — "share app link" — is already covered natively by the mounted-but-unused `ft.Share` service
- **Where:** `src/core/shared_services.py:26` (`("share", ft.Share)`) · `src/core/shared_services.py:12-18` · `src/core/shared_services.py:21-50` (mount) · `src/app_controller.py:99` (call site) · `.venv/Lib/site-packages/flet/controls/services/share.py:162-204` (`share_text`), `:206-233` (`share_uri`), `:235-283` (`share_files`), `:331-372` (`ShareText` ClientAction)
- **What:** the app **already mounts** a native platform share sheet (`ft.Share`) and a clipboard service (`ft.Clipboard`, `src/core/shared_services.py:25`) — but **never calls either**. The only occurrences of "share" in `src/` are the mount itself and unrelated prose (`src/core/shared_services.py:15,26`; "Shared UI pieces" docstrings at `src/components/ui.py:1`, `src/components/__init__.py:1`, `src/components/app_header.py:1`, `src/components/brand_hero.py:1`; and a filesystem path `src/core/storage_paths.py:23`). There is no `share_text` / `share_uri` / `share_files` call anywhere in the app.
  This matters for the qrcode question specifically: if a "share app link" / "share this container's image ref" feature is ever requested, the correct implementation is `page.share.share_text(...)` / `share_uri(...)` — the **native** Android/iOS share sheet — which needs **zero** new dependencies and zero APK payload. A hand-rolled QR would be strictly worse: it would require adding `qrcode` to `project.dependencies` (shipping it in every APK) plus a rasterization step (`make_image` → PNG → `ft.Image(src_base64=...)`, or `get_matrix()` → ASCII in `ft.Text`).
- **Evidence:**
  ```text
  $ grep -rn "share_text\|share_uri\|share_files\|ShareText" src/
  (no matches)
  $ grep -rn "share\|Share" src/ --include=*.py
  src/core/shared_services.py:15,26,40,46,53,59   (mount + url_launcher only)
  ... (remaining hits are docstrings and a storage path)
  ```
  The two zero-new-dependency QR renderings are both unattractive: `make_image` defaults to PIL when importable (`qrcode/main.py:363-367`) but **Pillow is host-only** — it is not a flet runtime dependency (`flet-1.0.4.dist-info/METADATA:33` lists `pillow>=10.3.0` only under the `test` extra) and `pillow in build deps: False`; and the ASCII fallback via `get_matrix()` (`qrcode/main.py:515`) renders into `ft.Text`, whose `font_family` is `None` by default (`flet/controls/core/text.py:251`) and which the app never overrides (no `font_family` anywhere in `src/core/theme.py`, `src/core/tokens.py`, `src/core/styles.py`) — i.e. the platform's proportional default, which is not reliably scannable.
- **Fix / opportunity:** none for qrcode. If the swarm wants a product improvement here, the actionable one is **using `ft.Share`**, which is already mounted at zero cost — but that is a `flet` utilization item, not a qrcode item, and it needs a user story first (there is no share flow to hang it on today).
- **Risk if ignored:** none user-visible. The cost of the status quo is that the app has no "share" affordance at all — acceptable for a container runner whose distribution channel is the Play Store listing (`src/core/constants.py:18`).

### F4 · P3 · A qrcode import in `src/` would be blocked by the house import guard — and unblocking it would ship qrcode in every APK
- **Where:** `tests/test_imports_vs_deps.py:46-59` (guard) · `tests/test_imports_vs_deps.py:18-32` (`_declared()` reads `project.dependencies` + `tool.flet.<platform>.dependencies`) · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576`
- **What:** the guard asserts that every third-party import in `src/` maps to a **declared** dependency. Adding `import qrcode` to any app module would fail `test_imports_all_declared` unless `qrcode` were added to `pyproject.toml:9-15` — and adding it there is exactly what puts it in the APK (F1). The dependency set is frozen by D-003 (`docs/decisions.md:12-13`: "Any addition needs owner sign-off"), so there is no legal path from "I want a QR" to "qrcode is in the app" without an owner decision.
- **Evidence:**
  ```text
  $ .venv/Scripts/python.exe -m pytest tests/test_imports_vs_deps.py -q
  .                                                                        [100%]
  ```
  The guard's `_declared()` (`tests/test_imports_vs_deps.py:18-32`) reads exactly the two tables that `build_base.py:2566-2576` feeds to the packager — so the guard and the packaging rule are the same rule, which is why the guard is trustworthy here.
- **Fix / opportunity:** none — this is the mechanism working as designed. Document the coupling for the synthesis: **qrcode-in-APK requires a pyproject change, and a pyproject change requires owner sign-off.**
- **Risk if ignored:** none. The guard currently passes, so there is no latent breakage. The value is that it forecloses the "just add the import" shortcut that would otherwise silently grow the APK.

### F5 · P3 · The study's "no-ship verdict" holds; one wording correction on "zero build relevance"
- **Where:** `docs/dependency-studies/qrcode.md:9-10` ("Dev flows only — zero build relevance (roadmap §3 row D1)") · `.venv/Lib/site-packages/flet_cli/commands/run.py:16` · `.venv/Lib/site-packages/flet_cli/cli.py:16` · `.venv/Lib/site-packages/flet_cli/commands/run.py:584-591` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2568-2606` · `docs/dependency-studies/qrcode.md:180-184` (§7 "Fullest utilization") · `docs/dependency-studies/qrcode.md:34` (ctor default wording)
- **What:** the study's conclusion — "dev flows only, do NOT ship to Android" (§5), "No `dependencies` entry, no in-app screen, no service" (§7) — is **correct and unchanged** by the current product. Two refinements:
  1. **"Zero build relevance" is imprecise.** `import qrcode` is top-level (`run.py:16`) and `flet_cli/cli.py:16` imports `flet_cli.commands.run` at top level, so **every** flet-cli invocation imports qrcode — including the `flet build apk` / `flet build aab` steps in CI. Runtime proof: `import flet_cli.cli` → `qrcode in sys.modules: True`. The QR is still never *rendered* in CI (the `self.ios or self.android` guard at `run.py:590` is false during a build), and qrcode is still **not packaged** (F1). So the correct statement is: *loaded in every flet-cli process, never used except in `flet run --android/--ios`, never shipped.*
  2. **Ctor default wording.** The study writes the default as `error_correction=0`; the installed source writes `error_correction=constants.ERROR_CORRECT_M` (`qrcode/main.py:81`), and `ERROR_CORRECT_M = 0` (`qrcode/constants.py:3`) — semantically identical, but the constant is the literal form. The study's non-alphabetical level values (L=1, M=0, Q=3, H=2) are confirmed verbatim at `qrcode/constants.py:1-5`.
- **Evidence:**
  ```text
  $ .venv/Scripts/python.exe -c "import flet_cli.cli; print('qrcode' in sys.modules)"
  True
  $ .venv/Scripts/python.exe -c "import sys, pathlib; sys.path.insert(0,'src'); [__import__(m) for m in <all 27 app modules>]; print('qrcode' in sys.modules)"
  total modules: 27
  failures: []
  qrcode in sys.modules: False
  ```
- **Fix / opportunity:** none to the code. If the study's §5/§7 wording is ever re-quoted, prefer "never packaged, loaded only by flet-cli" over "zero build relevance" (F5.1), and cite `main.py:81` rather than a bare `0` for the error-correction default (F5.2).
- **Risk if ignored:** a synthesis line saying "qrcode has zero build relevance" could be misread as "qrcode is absent from the build toolchain" and invite a `pip uninstall`/cleanup change. It is in fact a hard import of `flet_cli.commands.run`; removing it would break `flet run`/`flet build` outright.

## Missed capabilities (dependency audits only)

**None worth shipping. The honest inventory:**

| Capability | API location | Could the app use it? | Verdict |
|---|---|---|---|
| `qr` console script (host-side PNG/ASCII generation) | `.venv/Scripts/qr.exe`; `qrcode-8.2.dist-info/entry_points.txt:2`; `qrcode/console_scripts.py:43` (`main`), `:25` (`default_factories`: pil/png/svg/svg-fragment/svg-path), `:35` (`error_correction` map) | Yes, host-side only — but there is no URL worth encoding for the product, and the CI publishes release pages (`docs/decisions.md:21-22`, GitHub Releases only) rather than artifact pages needing a scannable link | **No.** The study's §5.3 idea of a `tools/print_qr.py` would *hand-roll over an already-installed console script* — against the brief's stated goal of using capabilities we already ship. `qr --output invite.png '<url>'` already exists; no new file is needed. |
| `make_image()` rasterization (`PilImage` / `PyPNGImage` / `SvgImage`) | `qrcode/main.py:339-387`; default factory at `:363-367`; `qrcode/image/pil.py:5`, `qrcode/image/pure.py`, `qrcode/image/svg.py` | Would need `qrcode` in `project.dependencies` → into the APK; PIL default would additionally need Pillow in the APK (`pillow in build deps: False`) | **No.** For a surface that does not exist. |
| `get_matrix()` → ASCII in `ft.Text` | `qrcode/main.py:515` | Zero new dependency (qrcode is pure-Python; `PyPNGImage` needs no Pillow) | **No.** Renders in the platform proportional font (`ft.Text.font_family` is `None` by default, `flet/controls/core/text.py:251`; the app sets no family) → not reliably scannable. Would need a bundled monospace font asset, i.e. new asset work for a nonexistent feature. |
| `print_tty()` (ANSI-colour terminal QR) | `qrcode/main.py:256-284` | Host-side only | **No.** The only realistic use is a dev terminal, and flet-cli already prints the ASCII form (`run.py:674`); `print_tty` is commented out there (`run.py:675`). |
| `QRCode(version=…, error_correction=…, box_size=…, border=…, mask_pattern=…)` tuning | `qrcode/main.py:78-99`; version property `:101-112`; mask setter `:118-121`; `_check_mask_pattern` `:40-48` | No consumer | **No.** Tuning knobs for a renderer the app never invokes. |

The one genuine *product* lever — "share a link with another device" — is served natively by
`ft.Share` (F3) and requires no dependency at all. qrcode is not the tool for it.

## Verified-good list

Things checked and confirmed correct, so the synthesis does not re-open them:

1. **Study API accuracy** — spot-checked against the installed source, every claim holds: package exports (`qrcode/__init__.py:1-10`, `run_example` at `:13-24`); `make()` shortcut (`qrcode/main.py:22-26`); `QRCode` class + ctor signature and guards (`qrcode/main.py:74-99`, `_check_box_size:28-30`, `_check_border:33-37`, `_check_mask_pattern:40-48`); `add_data(data, optimize=20)` (`qrcode/main.py:132-146`); `print_ascii(out, tty, invert)` (`qrcode/main.py:286-327`); `make_image` with the PIL-default branch (`qrcode/main.py:339-387`, `:363-367`); `get_matrix()` (`qrcode/main.py:515`); error-correction constants L=1/M=0/Q=3/H=2 verbatim (`qrcode/constants.py:1-5`).
2. **Version and licence** — qrcode **8.2** installed (`.venv/Lib/site-packages/qrcode-8.2.dist-info/METADATA:3`), BSD (`METADATA:6`), matching the study's identity line.
3. **Transitive-only status** — `qrcode` is not in `pyproject.toml:9-15`, not in the dev group (`pyproject.toml:78-84`), and not reachable from any runtime dependency; the sole lock-file edge is `uv.lock:230` (flet-cli). Inverted tree agrees (`docs/swarm/dependency-tree/uv-tree-inverted.txt:35-37`).
4. **Not in the APK** — proven by live evaluation of flet-cli's own dependency resolver (F1); the `src/requirements.txt` fallback does not apply (that file does not exist).
5. **qrcode absent from the app import graph** — all 27 app modules import cleanly with `qrcode` **not** in `sys.modules`; and qrcode is correctly absent from the hand-written shipped-licenses list `_PY_DISTS` (`src/screens/views.py:26-42`).
6. **The house import guard passes** — `tests/test_imports_vs_deps.py:46-59` green; it is also the mechanism that would block an unauthorized qrcode import (F4).
7. **CI never exercises the QR path** — `.github/workflows/app.yml:159` (`flet build apk`) and `:213` (`flet build aab`) only; no `flet run` anywhere in the repo's own scripts; the QR renders only under `flet run --android/--ios` (`flet_cli/commands/run.py:590-591`).
8. **No QR/URL-sharing path in `src/`** — zero matches for `qrcode|qr_code|\bqr\b|qr-` across `src/`, `tests/`, `.github/`, `build_flet_proot_wheel.py`; zero calls to `share_text`/`share_uri`/`share_files`.
9. **No container-connection surface** — no SSH, port-forward, tunnel, local server, or listen/bind anywhere in `src/`.
10. **No donate/sponsor surface** — the only "sponsored" hits are the trademark disclaimers at `src/screens/views.py:663,670,677,683`.
11. **D-003 frozen set respected** — `docs/decisions.md:12-13` lists exactly the deps in `pyproject.toml:9-15` + `:78-84`; qrcode is not among them and needs no entry.
12. **`qrcode`'s only dependency is win32-only `colorama`** (`uv.lock:712-714`) — so even a hypothetical qrcode adoption would not drag a cross-platform transitive dependency into the APK.

## Unverified

- **Whether any *future* roadmap item will need a QR.** `docs/roadmap.md` and `docs/testing-findings.md` are **deleted in the working tree** (`git status` shows ` D docs/roadmap.md`, ` D docs/testing-findings.md`) while still present in `git HEAD`; `docs/reference/README.md:5` links to both. I read the roadmap from `git show HEAD:docs/roadmap.md` and confirmed line 136 lists `qrcode` in the dev-only stack — matching the study's "roadmap §3 row D1" claim. Whether the working-tree deletion is intentional (a doc restructure) or accidental is **UNVERIFIED** and outside this audit's scope; the swarm synthesis should confirm it before re-quoting roadmap section numbers. (Note: this deletion is **not** caused by qrcode and is not filed as a qrcode finding.)
- **Whether `flet run --android` has ever been executed by a maintainer.** The QR path is verified dead in the repo's scripts and CI; whether a developer used the flag manually outside version control is **UNVERIFIED**.
- **The exact APK size delta** qrcode would add if it were ever declared. `qrcode-8.2` is a pure-Python wheel of 45 986 bytes compressed (`uv.lock:717`); the installed size is ~60 KB of `.py` plus `__pycache__`. The exact on-device delta after serious-python's packaging is **UNVERIFIED** — no build was run (per D-005, "No local `flet build`", `docs/decisions.md:19`).
- **Behaviour of `print_ascii` on a non-UTF-8 console** (`qrcode/main.py:303` decodes cp437 code points) — not exercised by any repo workflow; **UNVERIFIED** and not on any critical path.
- **Reed–Solomon internals, `qrcode/image/` factory class bodies beyond names, `styledpil` drawers, `qrcode/release.py`, `qrcode/tests/`** — carried over as **unverified** from the study; this audit re-verified only the API surface it relied on.
