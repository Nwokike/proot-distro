# oauthlib — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `pyproject.toml:60-63` · `.github/workflows/app.yml:163-172,275-288` · `src/screens/views.py:26-51,565-606` · `src/app_controller.py:115-130,248-258` · `src/core/state.py:29` · `PRIVACY.md:19,32` · `docs/dependency-studies/oauthlib.md` · `docs/reference/dep-flet-runtime-utils.md:10-12` · `docs/compliance/licensing.md` (git HEAD) · `.venv/Lib/site-packages/oauthlib/**` · `.venv/Lib/site-packages/flet/controls/page.py:69-81,1193-1248` · `.venv/Lib/site-packages/flet/auth/authorization_service.py:93,120,208` · `.venv/Lib/site-packages/flet/auth/oauth_provider.py:38-69` · `.venv/Lib/site-packages/flet/auth/providers/github_oauth_provider.py:13-30` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:641-647,2770-2790,2925-2949` · `.venv/Lib/site-packages/flet_cli/utils/pyproject_toml.py:28-50` · `flet-dev/serious-python` `package_command.dart` · `flet-dev/serious-python_android/android/build.gradle.kts` · `dart-lang/tools` `pkgs/glob` · **Date:** 2026-10-20

## What it does / how the app uses it

oauthlib 4.0.0 is a **transitive** dependency: it is required by flet
(`flet-1.0.4.dist-info/METADATA:14` → `Requires-Dist: oauthlib>=3.2.2; platform_system != "Emscripten"`),
not by our `pyproject.toml` `[project].dependencies` (`pyproject.toml:9-15`).

**The app uses it not at all.** Every one of the 32 app modules under `src/` (32 `.py` files,
`main.py` included) imports cleanly and `oauthlib` never enters `sys.modules`:

```text
$ .venv/Scripts/python.exe -  (import every module under src/)
total .py files: 32
failures: []
oauthlib in sys.modules after importing ALL app modules (incl. main): False
```

The only `oauthlib` string in the whole app source is a **licence-list entry**, not an import:

```text
$ grep -rn "oauthlib" src/ tests/
src/screens/views.py:39:    "oauthlib",
```

Reachability inside flet is exactly three function-local imports, all of the same class, all in one
file (`grep -rn "oauthlib" .venv/Lib/site-packages/flet/`):

```text
flet/auth/authorization_service.py:93:        from oauthlib.oauth2 import WebApplicationClient
flet/auth/authorization_service.py:120:        from oauthlib.oauth2 import WebApplicationClient
flet/auth/authorization_service.py:208:        from oauthlib.oauth2 import WebApplicationClient
```

The chain that reaches them is `Page.login()` → `_default_authorization_impl()` →
`AuthorizationService`, and the last link is **deferred on purpose**:

```text
.venv/Lib/site-packages/flet/controls/page.py:69-81
    def _default_authorization_impl() -> "type[Authorization]":
        """Resolve the default `Authorization` implementation lazily.
        Deferring these imports keeps the auth subsystem out of the cold-start
        import graph for apps that never call `Page.login`."""
        ...
            from flet.auth.authorization_service import AuthorizationService
```

```text
.venv/Lib/site-packages/flet/controls/page.py:1213-1222
        if authorization is None:
            authorization = _default_authorization_impl()
        self.__authorization = authorization(...)
        if saved_token is None:
            authorization_url, state = self.__authorization.get_authorization_data()
```

`get_authorization_data` is the first of the three call sites
(`authorization_service.py:86` → `:93` `from oauthlib.oauth2 import WebApplicationClient`,
`:96-97` `WebApplicationClient(self.provider.client_id)` / `client.prepare_request_uri(...)`).

Runtime proof that the prune cannot break `import flet`:

```text
$ .venv/Scripts/python.exe -c "import flet; print('oauthlib' in sys.modules)"
import flet OK, flet version: 1.0.4
oauthlib in sys.modules after import flet: False
oauthlib in sys.modules after import flet.auth: False
```

The app has **no login or OAuth path** — confirmed by source grep, by the controller, and by the
privacy policy:

- `grep -rn "oauthlib\|Page.login\|OAuthProvider\|\.login(" src/ tests/` → only `src/screens/views.py:39`.
- The only `login` hits in `src/` are upstream CLI calls, not auth: `src/services/proot_service.py:313,327,340`
  (`proot-distro login <c> --get-proot-cmd`).
- The only credential path is a **manually pasted** Docker Hub token: `src/app_controller.py:248-258`
  (`set_docker_token` → `os.environ["PD_DOCKER_AUTH"] = token`, persisted at `:257`,
  restored at `:123-127`), surfaced at `src/screens/views.py:390-393` and `src/core/state.py:29`.
- `PRIVACY.md:19`: "The application requires no account creation, registration, or login."
- `PRIVACY.md:32`: "Optional Docker Hub authentication tokens entered in Settings remain stored locally on your device."

## Findings

### F1 · P1 · The CI prune check is structurally blind to the site-packages, so the oauthlib prune has zero CI verification
- **Where:** `.github/workflows/app.yml:163-172` (apk job, "Size report & prune check") and
  `.github/workflows/app.yml:275-288` (aab job, "Verify no development files in the bundle");
  the check is anchored by the greps at `.github/workflows/app.yml:168` and `:282`.
  Packaging side: `serious_python_android/android/build.gradle.kts:359-386` (site-packages →
  `assets/sitepackages.zip`) and `:423-441` (app package → `assets/app.zip`).
- **What:** the two steps police the APK/AAB for `pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/`
  — `oauthlib` is not in the list, so the prune this repo relies on is never asserted anywhere in CI.
  Worse, the check cannot assert *anything* about the site-packages, because on Android the pure-Python
  payload is shipped as a **STORED zip asset**: `build.gradle.kts:368` creates
  `storedZip(File(assetsDir, "sitepackages.zip"))` and `:435` creates `storedZip(File(assetsDir, "app.zip"))`.
  `unzip -l "$artifact"` therefore lists those zips as single opaque entries. The AAB step does open one
  nested archive — but the wrong one: it extracts `base/assets/app/app.zip` (`app.yml:280`), which holds
  the **app package**, not `base/assets/sitepackages.zip`, which holds the site-packages where
  `oauthlib/`, `flet/`, `httpx/` … live. Net effect: the "prune check" is vacuous for every
  site-packages path, today and for any future leak.
- **Evidence:**
  ```text
  $ grep -n "oauthlib\|pytest/\|ruff/\|uvicorn/\|starlette/\|fastapi/\|docs/" .github/workflows/app.yml
  168:            if unzip -l "$artifact" | grep -qE 'pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/'; then
  282:              if unzip -l /tmp/aab_check/base/assets/app/app.zip | grep -qE 'pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/'; then
  ```
  ```text
  $ sed -n '359,386p' serious_python_android/android/build.gradle.kts
      // Site-packages tree: tagged .so -> mangled jniLibs (+ .soref markers), pure ->
      // sitepackages.zip (or extract.zip if allowlisted); opt/ is left to copyOpt.
      ...
              val siteZip = if (isPrimary) storedZip(File(assetsDir, "sitepackages.zip")) else null
  $ sed -n '423,441p' serious_python_android/android/build.gradle.kts
  // The app's Python sources ... ship as a STORED, ABI-common `app.zip` asset alongside stdlib.zip/sitepackages.zip
      val zip = storedZip(File(assetsDir, "app.zip"))
  ```
  (The site-packages are *not* extracted instead of zipped: `build_base.py:82`
  `ANDROID_DEFAULT_EXTRACT_PACKAGES: list[str] = []` and our pyproject sets no `extract_packages`.)
- **Fix / opportunity:** add a CI step that opens the site-packages archive itself and asserts on its
  listing — e.g. extract `assets/sitepackages.zip` (APK) / `base/assets/sitepackages.zip` (AAB) and
  `unzip -l` it, failing if it matches `oauthlib/` (or any other pruned glob). Extend the existing
  pattern list to cover the pruned set rather than only dev-tool names. Keep the AAB's `app.zip`
  extraction as-is for the app package.
- **Risk if ignored:** the prune is a "trust me" claim. A future glib mistake, a renamed upstream
  directory, or a dev dependency leaking into the site-packages ships silently and permanently —
  the gate that exists to catch exactly that reports green.

### F2 · P2 · The prune is half-done: the `oauthlib` dist-info (and its BSD LICENSE) still ships, and the in-app third-party list still advertises the package
- **Where:** `pyproject.toml:63` (`package_files = ["oauthlib/**"]`);
  `src/screens/views.py:39` (the `"oauthlib"` row in `_PY_DISTS`), `:565-572` (`_dist_license`),
  `:600-606` (`_py_entries`); `docs/compliance/licensing.md:105` and `:54` (git HEAD);
  `docs/compliance/licensing.md:693` (checklist A4).
- **What:** `oauthlib/**` removes the **code tree** but not the **distribution metadata**. The glob
  compiles to `^oauthlib/(?!^(?:\.\./|/))[^]*$`, which requires a literal `oauthlib/` — the sibling
  directory `oauthlib-4.0.0.dist-info/` does not match, so 18,352 bytes of metadata (including
  `oauthlib-4.0.0.dist-info/licenses/LICENSE`) still ship. `importlib.metadata` therefore still
  resolves the distribution inside the APK, and the Licenses screen still renders
  "oauthlib 4.0.0 (BSD-3-Clause)" for a package whose code is not in the binary. The compliance
  document already anticipated this: `licensing.md:105` says *"candidate for `[tool.flet.cleanup]`
  pruning — roadmap M5; **if pruned, drop the row and keep the audit note**"* — the row was never
  dropped, and `licensing.md:54` still lists `oauthlib` in the shipped "Python payload".
- **Evidence:**
  ```text
  $ .venv/Scripts/python.exe -  (simulate serious_python cleanupDirRecursive, glob "oauthlib/**")
  survivors after cleanup with glob 'oauthlib/**':
      flet/__init__.pyc
      httpx/__init__.pyc
      oauthlib-4.0.0.dist-info/METADATA
      oauthlib-4.0.0.dist-info/RECORD
      requests/__init__.pyc
  oauthlib/ dir still exists?       False
  oauthlib-4.0.0.dist-info exists?  True
  ```
  ```text
  $ .venv/Scripts/python.exe -  (importlib.metadata with ONLY the dist-info present)
  distributions found with ONLY the dist-info present: [('oauthlib', '4.0.0')]
  License: BSD-3-Clause | License-Expression: None
  ```
  ```text
  $ du -sb .venv/Lib/site-packages/oauthlib-4.0.0.dist-info
  18352
  $ ls .venv/Lib/site-packages/oauthlib-4.0.0.dist-info/licenses/
  LICENSE
  ```
  The screen code is *safe* (no crash) either way: `_dist_license` swallows the exception
  (`src/screens/views.py:568-569` `except Exception: return ("", "")`) and `_py_entries` skips
  empty versions (`:604` `if version:`) — so the row disappears cleanly if the dist-info is also pruned.
- **Fix / opportunity:** decide the end state explicitly and make all three artifacts agree:
  (a) widen the glob to `oauthlib*` — verified by the same algorithm simulation to remove **both**
  the code tree and `oauthlib-4.0.0.dist-info/` while leaving `flet/`, `httpx/`, `requests/` alone
  (no other package in the tree starts with `oauthlib`: `ls .venv/Lib/site-packages | grep oauthlib`
  → `oauthlib`, `oauthlib-4.0.0.dist-info` only) — and drop `"oauthlib"` from `_PY_DISTS`
  (`src/screens/views.py:39`) and from `licensing.md:54`/`:105`; **or**
  (b) keep the metadata and record the deliberate decision in `licensing.md` (the BSD notice ships
  without the code, and the screen row is then correct).
  Note the current state satisfies neither reading: the doc says "drop the row", the screen keeps it.
- **Risk if ignored:** the in-app screen says "This app includes third-party software" and then lists a
  package whose code is absent, while `licensing.md` simultaneously claims oauthlib ships and says the
  row should have been dropped. A compliance reviewer comparing the doc to the binary finds three
  different answers.

### F3 · P3 · `pyproject.toml`'s "~1 MB saved" overstates the real saving by roughly 2x
- **Where:** `pyproject.toml:61` — `# (licensing A4). ~1 MB saved; breaks only Page.login().`
- **What:** the ~1 MB figure is the *dev-tree* size of `oauthlib/` including `__pycache__`. The
  pure `.py` source is 503,928 B, and the **shipped** footprint — what the APK actually carries after
  flet compiles packages (`compileall -b`, then the `.py` files are deleted) — is 538,219 B across
  75 `.pyc` files, i.e. ~526 KB, because `__pycache__` is never copied into the build tree.
  The number is also a floor, not a ceiling: the `oauthlib-4.0.0.dist-info` (18,352 B) is not pruned
  at all (F2).
- **Evidence:**
  ```text
  $ du -sb .venv/Lib/site-packages/oauthlib
  1043015                       # includes __pycache__  (the "~1 MB" figure)
  $ find .venv/Lib/site-packages/oauthlib -name "*.py" -not -path "*__pycache__*" -exec du -cb {} + | tail -1
  503928                        # .py source only
  $ (copy oauthlib to tmp, python -m compileall -b, delete *.py)
  === shipped .pyc total (bytes) ===
  538219
  === file count ===
  75
  ```
- **Fix / opportunity:** change the comment to "~0.5 MB saved" (and, if F2(a) is taken, note that the
  dist-info stays or goes with it). Purely a comment — no behaviour change.
- **Risk if ignored:** a 2x-inflated size claim in the file future maintainers read first; harmless
  today, misleading when a packaging budget is argued from it.

### F4 · P3 · A future `Page.login()` would fail on-device with a bare `ModuleNotFoundError`, and nothing in the repo would catch it
- **Where:** `.venv/Lib/site-packages/flet/controls/page.py:1193-1248` (entry) →
  `:69-81` (`_default_authorization_impl`) → `.venv/Lib/site-packages/flet/auth/authorization_service.py:93`
  (first `from oauthlib.oauth2 import WebApplicationClient`); also `:120` (`request_token`) and
  `:208` (`__refresh_token`, reached from `dehydrate_token` when `Page.login(saved_token=...)` is used —
  `page.py:1242`).
- **What:** with `oauthlib/**` pruned, the first use of the OAuth path raises
  `ModuleNotFoundError: No module named 'oauthlib'` **inside** `get_authorization_data`, i.e. at the
  moment the user taps "sign in" — not at import time, not at build time, and not on the desktop
  dev machine (where oauthlib is installed). There is currently no guard that would fail a build
  that introduced a login call: `tests/test_imports_vs_deps.py` only checks that every import in
  `src/` is a *declared* dependency (`:46-59`) — it never checks the reverse, and oauthlib is a
  transitive flet dep, so it is not in `[project].dependencies` at all.
- **Evidence:** `grep -rn "on_login\|on_logout" src/` → no hits; the only `oauthlib` string in `src/`
  is the licence row (`src/screens/views.py:39`); `flet/controls/page.py:69-74` documents the
  deferred import explicitly.
- **Fix / opportunity:** keep the decision and the failure mode recorded where the next person will
  look — `docs/reference/dep-flet-runtime-utils.md:10-12` already does this ("breaks only
  `Page.login()` — documented, verified safe"). Add the flip side to the roadmap: a login feature
  must un-glob `oauthlib/**` in `pyproject.toml` **and** update `PRIVACY.md:19` (which currently
  promises no login) and `licensing.md:54`/`:105`. A cheap CI guard — fail if `oauthlib` appears as
  an import in `src/` while the glob is active — turns a silent on-device crash into a build failure.
- **Risk if ignored:** a future login feature ships broken and only fails on a real device, in a
  flow that is otherwise untested by CI.

### F5 · P3 · The prior study's two load-bearing claims are now stale
- **Where:** `docs/dependency-studies/oauthlib.md:396-397` and `:420-422`.
- **What:** the study was correct on 2026-10-16, but the repo has moved on:
  - study:396-397 claims *"the repo contains zero oauthlib references — verified `grep -rn
    "oauthlib\|Page.login\|OAuthProvider" src/ tests/` returns nothing"*. Today that grep returns
    `src/screens/views.py:39:    "oauthlib",` (a licence-list entry, harmless, but the claim as
    written is false).
  - study:421-422 claims *"Our pyproject currently has NO `[tool.flet]` table at all (verified read),
    so this is a packaging-milestone addition, not a change to anything existing."* Today
    `pyproject.toml:20` is `[tool.flet]` and `pyproject.toml:62-63` is
    `[tool.flet.cleanup]` / `package_files = ["oauthlib/**"]` — the prune is **live**, not pending.
- **Evidence:** `grep -rn "oauthlib" src/ tests/` → `src/screens/views.py:39`;
  `pyproject.toml:20` `[tool.flet]`, `:62-63` `[tool.flet.cleanup]` / `package_files = ["oauthlib/**"]`.
- **Fix / opportunity:** do not edit the study (it is a dated snapshot); this report supersedes its
  §4 pruning conclusion. The synthesis should treat "oauthlib is pruned" as **shipped state**, not
  roadmap M5, and should not re-derive the "zero references" claim.
- **Risk if ignored:** the synthesis re-opens a settled decision, or re-asserts a false premise.

## Missed capabilities (dependency audits only)

- **Private container-registry sign-in is the one capability that is actually reachable, and it is
  the reason the manual-token field exists.** The app already has the credential *slot*
  (`src/app_controller.py:248-258` → `PD_DOCKER_AUTH`, surfaced at `src/screens/views.py:390-393`)
  and currently requires the user to paste a Docker Hub personal access token by hand
  (`PRIVACY.md:32`). A "sign in with GitHub" flow for `ghcr.io` private images would be exactly
  `flet.auth.GitHubOAuthProvider` (`.venv/Lib/site-packages/flet/auth/providers/github_oauth_provider.py:13-30`,
  endpoints hard-coded at `:25-26`) + `Page.login()` (`page.py:1193`) + the
  `authorization_service.py:93-97` authorization-URL path — **no new dependency** (the frozen
  dependency set D-003 is not touched) and no native code.
  Cost: the oauthlib glob must be removed, `PRIVACY.md:19` must change (it currently promises no
  login), `licensing.md:54`/`:105` must change, and the token must be persisted (flet already
  supports `saved_token=` → `page.py:1242` → `authorization_service.py:70`).
  Value: removes a copy-paste friction step for the exact users who need private images.
  **Verdict: not now** — no registry-auth work is scoped, the manual-token path works, and the
  prune is already live and correct. Recorded so the decision is revisited deliberately, not by
  accident.
- **What oauthlib can never do for this app:** act as an OAuth *provider*. The server half
  (`oauthlib.oauth2` endpoints, grant types, `RequestValidator`) serves tokens to other clients —
  meaningless inside an Android client, and flet never touches it (`flet` imports exactly one class,
  `WebApplicationClient`, at three sites). Device flow (`oauthlib.oauth2.rfc8628`) is philosophically
  suited to a phone but is not needed — a phone browser completes a standard flow fine.
- **PKCE is available but unused.** `flet.auth.OAuthProvider.__init__` accepts
  `code_challenge` / `code_challenge_method` (`.venv/Lib/site-packages/flet/auth/oauth_provider.py:50-51`,
  stored at `:68-69`) and `authorization_service.py:102-103` forwards them into
  `client.prepare_request_uri(...)`. If a login flow is ever built, PKCE should be on by default —
  it is a security property that is free to enable and free to omit, and omitting it is the
  irreversible kind of mistake. Not an audit finding today (there is no login flow); a constraint
  on the future one.

## Verified-good list

- **`import flet` never loads oauthlib** — `page.py:69-81` defers the auth import; runtime check
  returns `False` for `'oauthlib' in sys.modules` after `import flet` and after `import flet.auth`.
  The prune therefore cannot break `import flet`.
- **Reachability is exactly one chain**: `Page.login()` (`page.py:1193`) → `_default_authorization_impl()`
  (`page.py:69-81`) → `AuthorizationService` → `from oauthlib.oauth2 import WebApplicationClient`
  (`authorization_service.py:93`, `:120`, `:208`). No other module in all of flet imports oauthlib
  (`grep -rn "oauthlib" .venv/Lib/site-packages/flet/` → 3 code imports + 2 docstring mentions, all in
  `authorization_service.py`).
- **The app has no login/oauth path.** `grep -rn "oauthlib\|Page.login\|OAuthProvider\|\.login(" src/ tests/`
  → only `src/screens/views.py:39`; `grep -rn "on_login\|on_logout" src/` → no hits; `PRIVACY.md:19`
  states there is no login; the only credential is a manually pasted Docker token
  (`src/app_controller.py:248-258`).
- **The `pyproject.toml` key path and resolution are correct for every platform.** The real
  `flet_cli` resolver was exercised against the real `pyproject.toml`:
  ```text
  $ .venv/Scripts/python.exe -  (BaseBuildCommand.get_platform_setting)
  REAL get_platform_setting(cleanup.package_files) = ['oauthlib/**']   # config_platform='android'
  REAL get_platform_setting(cleanup.package_files) = ['oauthlib/**']   # config_platform='ios'
  ```
  Precedence is `tool.flet.<platform>.` → `tool.flet.` → default
  (`build_base.py:2943-2949`); `tool.flet.android.cleanup` is absent, so the global
  `[tool.flet.cleanup]` (pyproject.toml:62-63) governs Android, iOS, Windows, macOS, Linux and web.
- **The glob reaches serious_python correctly.** `build_base.py:2778-2784` turns each entry into one
  `--cleanup-package-files <glob>` argument and `:2789-2790` adds `--cleanup-packages` (default on,
  `:2750-2751`); the args are handed to the `serious_python package` step at `:2820-2825`.
  serious_python's own flag is `package_command.dart:190-192` and is applied at `:517-525` with
  `Glob(g.replaceAll("\\", "/"), context: path.Context(current: directory.path))` (`:642-643`), i.e.
  the glob is resolved **relative to the site-packages root** — the correct base for `oauthlib/**`.
- **The glob removes exactly the oauthlib code tree and nothing else.** The Dart glob package
  (`dart-lang/tools` `pkgs/glob`) compiles `oauthlib/**` to `^oauthlib/(?!^(?:\.\./|/))[^]*$`
  (`ast.dart:46-48` anchoring, `:207-226` sequence, `:276-309` `DoubleStarNode`); the serious_python
  deleter (`package_command.dart:646-666`) then removes every matching child and, because the
  `oauthlib` directory itself is emptied, removes it too. A faithful port of that algorithm on a
  synthetic site-packages leaves `flet/`, `httpx/`, `requests/` untouched and deletes `oauthlib/`
  entirely. The `oauthlib` directory entity itself is *not* matched by the regex — it is removed by
  the empty-directory rule, which is why the "dir doesn't match" case still ends clean.
- **The prune is a packaging glob, not a source edit** — no vendoring, no fork, no monkeypatch
  (BRIEF rule 4 respected); re-enabling is one line in `pyproject.toml:63`.
- **flet upstream already ships without oauthlib**: `flet-1.0.4.dist-info/METADATA:14` marks it
  `platform_system != "Emscripten"`, so on Emscripten flet runs with no oauthlib at all.
- **The licences screen cannot crash on a missing distribution**: `src/screens/views.py:568-569`
  catches everything and `:604` skips entries with an empty version.
- **The dependency guard is green**: `tests/test_imports_vs_deps.py` passes — the app imports only
  `flet` + stdlib + local modules, and never oauthlib.
- **The prune happens before the payload is archived**: serious_python cleans each per-ABI
  site-packages tree inside the arch loop (`package_command.dart:507-525`) and only afterwards copies
  /zips it into the app (`:552-571`).
- **The installed version matches the study**: `oauthlib-4.0.0.dist-info/METADATA:3` → `Version: 4.0.0`;
  `oauthlib/__init__.py:15` → `__version__ = '4.0.0'`; 75 `.py` files; no `cryptography`/`jwt`/
  `blinker` in the venv, so the RSA/JWT/blinker extras are absent (as the study recorded).

## Unverified

- **No APK/AAB was built.** The prune's effect is proven at the glob/algorithm level (exact Dart
  semantics + a faithful port of the deleter), not on a real artifact. The APK/AAB byte-level
  outcome — in particular the exact in-archive path of `sitepackages.zip` — is **UNVERIFIED**.
- **The `serious_python` version actually used by the build template was not determined.** The
  `package_command.dart` and `build.gradle.kts` read here are `flet-dev/serious-python` `main`
  (pubspec `version: 6.0.0`, `glob: ^2.1.3`); the build pins its own serious_python through the
  flet build template, and that pin was not inspected. The glob semantics were read from
  `dart-lang/tools` `pkgs/glob` **main (2.2.0)**, not from the 2.1.3 lower bound — the `**` rules
  are exercised by serious_python's own `src/serious_python/test/glob_test.dart` (which asserts
  `Glob("**/__pycache__").matches("__pycache__")` and `Glob("**/numpy/**/tests")` behaviour), but
  the exact 2.1.3 source is **UNVERIFIED**.
- **Whether `assets/sitepackages.zip` appears at that exact path in the built APK/AAB** (as opposed
  to a Flutter-asset-relative prefix) is inferred from `build.gradle.kts:151,368,435` and the AAB
  layout convention, not observed — **UNVERIFIED**; the F1 fix should confirm the path on the first
  real artifact.
- **The full list of packages that a real `pip install` places beside `oauthlib`** (and therefore
  whether any *other* `oauthlib*`-prefixed name could exist) was checked only in this venv
  (`ls .venv/Lib/site-packages | grep oauthlib` → `oauthlib`, `oauthlib-4.0.0.dist-info`); the
  build-time site-packages tree is **UNVERIFIED**.
- **The two pre-existing test failures** in `tests/test_ui_reactive.py::test_license_texts_are_present_and_shipped`
  and `::test_licenses_view_carries_real_text` are caused by `src/LICENSES/*.txt` being **deleted
  in the working tree** (`git status --short` → ` D src/LICENSES/BSD-3-Clause.txt` etc.; the files
  are tracked at HEAD). They are unrelated to oauthlib and to this audit — this agent modified
  nothing. Their pre-existence is **UNVERIFIED** in the sense that no clean checkout was available
  to re-run the suite.
- Per the BRIEF's inventory-level rule, the ~40 oauthlib modules flet never imports (OAuth 1
  `rfc5849`, the server endpoints, the grant types, the `RequestValidator` hierarchy, the OpenID
  Connect half) were **not** re-audited here; this report covers the utilisation question, using
  `docs/dependency-studies/oauthlib.md` as prior knowledge and spot-checking only the APIs it
  relies on.
