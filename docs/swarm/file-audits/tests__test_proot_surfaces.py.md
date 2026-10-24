# tests/test_proot_surfaces.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_proot_surfaces.py · src/services/proot_service.py · tests/test_sessions.py · .venv/lib/python3.14/site-packages/proot_distro/ · Date: 2026-10-24

## What it does / how the app uses it

`tests/test_proot_surfaces.py` pins the proot-distro integration contract without a device:
1. Sole-importer rule: only `src/services/proot_service.py` may import `proot_distro` (AST scan over `src/`).
2. Argparse namespaces: the service's hand-built `_ns_*` namespaces must be field-for-field compatible with upstream's `parser.build_parser()`.
3. Env contract: `storage_paths.env_contract()` must set the import-time constants upstream reads, and `bootstrap()` must apply them idempotently before the first `proot_distro` import.
4. Desktop fallback: `available()` returns False when `proot_distro` can't be imported.
5. Dev-only guard: `src/` must not import dev-only packages (chardet, cookiecutter, pytest, ruff, flet_cli, flet_desktop, binaryornot, jinja2, requests).
6. Pull-limit policy: `is_pull_limit()` recognizes Docker Hub 429 markers.

`src/services/proot_service.py` is the sole facade: it bootstraps env/shims, wraps upstream `command_*` handlers via `_run_command` (capturing stdout/stderr, translating `SystemExit` into `Outcome`), builds argparse namespaces, and implements `get_proot_cmd` (runs `cli.main()` in-process with `sys.argv`/`sys.stdout`/`sys.stderr` swapped, returns the raw `--get-proot-cmd` line).

`tests/test_sessions.py` exercises the consumer side: it mocks `get_proot_cmd` to return a captured golden `--get-proot-cmd` line and asserts `session_argv` parses env + argv, merges host essentials, rejects garbage/empty commands, and folds upstream's backslash-newline wrapping.

## Findings

### F1 · P1 · get_proot_cmd redirects only sys.stdout, but upstream writes to sys.stdout.buffer — unhandled AttributeError on the real path
- **Where:** `src/services/proot_service.py:312-345` (specifically `sys.stdout = buffer` at :331, `buffer = io.StringIO()` at :328); `.venv/lib/python3.14/site-packages/proot_distro/commands/login/__init__.py:624` (`sys.stdout.buffer.write(data)` in `_print_command`); `.venv/lib/python3.14/site-packages/proot_distro/cli.py:334` (`cli.main()` → `command_login` → `_print_command`).
- **What:** `get_proot_cmd` installs `sys.stdout = io.StringIO()` and `sys.stderr = io.StringIO()`, then calls `cli.main()`. Upstream's `--get-proot-cmd` path writes its output via `sys.stdout.buffer.write(...)` (login/__init__.py:624, because the line may carry non-UTF-8 surrogates). A `io.StringIO` has no `.buffer` attribute, so any real invocation that reaches `_print_command` raises `AttributeError`. That is not a `SystemExit`, so `get_proot_cmd`'s `except SystemExit` (proot_service.py:335-340) does not catch it — the `AttributeError` propagates out of `get_proot_cmd` as an unhandled crash. (On this desktop host the run is stopped earlier by `ensure_proot_installed()` → `sys.exit(1)` because proot isn't on PATH, cli.py:137-145, which IS caught and re-raised as `RuntimeError`; the `.buffer` bug only surfaces once proot is available, i.e. on Android.)
- **Evidence:** Direct execution of the real `get_proot_cmd("debian")` path fails before reaching `_print_command` only because proot is absent (RuntimeError: "proot utility does not exist on your system"). The `.buffer` mismatch was reproduced by the test harness itself: wrapping `sys.stdout` with a `StringIO` and calling upstream-style `sys.stdout.buffer.write(...)` raises `AttributeError: '_io.StringIO' object has no attribute 'buffer'`. The upstream write site is confirmed at `.venv/.../login/__init__.py:624`.
- **Fix / opportunity:** Redirect `sys.stdout` to a wrapper exposing both `.write` (text) and `.buffer` (bytes capture), or capture `sys.stdout.buffer` directly, so upstream's `_print_command` output is captured and the `SystemExit(0)` path returns the line. Keep the `finally` restore of `sys.stdout`/`sys.stderr`/`sys.argv`.
- **Risk if ignored:** On Android, `session_argv` → `get_proot_cmd` crashes with `AttributeError` instead of returning the login command line, breaking session startup (user-visible: containers can't be opened). P1.

### F2 · P1 · Over-mocking: test_sessions.py mocks get_proot_cmd in every session_argv test, hiding the F1 bug and pinning a stale golden string
- **Where:** `tests/test_sessions.py:40-56` (mock at :41-43), `:59-68` (:61-63), `:71-76` (:72-74), `:79-83` (:80), `:148-160` (:150-152).
- **What:** All five `session_argv` tests replace `session_service.proot_service.get_proot_cmd` with a lambda returning a static golden string. Consequently no test ever calls the real `cli.main()` / `sys.stdout.buffer` path, so F1 is never exercised. The golden string is a captured snapshot; if upstream changes the printed format (field order, quoting, added assignments), `session_argv` could break while these tests keep passing. The wrapped-line test (`GOLDEN_CMD_WRAPPED`, :28-37) only validates the folding of backslash-newline, not the real subprocess boundary.
- **Fix / opportunity:** Add at least one integration test that drives the real `get_proot_cmd` (with proot shimmed/available) and asserts the returned line is parsed correctly, OR assert the golden string still matches a freshly captured upstream output in CI. Keep the mocked unit tests for deterministic parsing behavior.
- **Risk if ignored:** Silent divergence between `session_argv`'s parser and upstream's printed command line; sessions fail to start with an obscure `RuntimeError` rather than a caught regression. P1.

### F3 · P2 · Weak assertion direction in test_install_namespace_matches_parser
- **Where:** `tests/test_proot_surfaces.py:57-73`, especially the subset check at :73.
- **What:** `:73` asserts `set(vars(_ns_install("debian:bookworm", "debian"))) <= set(handled)` — i.e. the service's namespace is a *subset* of the full parser namespace. That passes even if `_ns_install` omits a field upstream's `command_install` actually reads, because it never requires the reverse inclusion. The four explicit field asserts (:66-70) are what actually carry coverage (`image_ref`, `custom_container_name`, `override_arch`, `allow_insecure`), all confirmed present in upstream (`parser.py:194-212`, `install.py:140-183`). The subset check adds no real enforcement.
- **Evidence:** `_ns_install` (proot_service.py:108-114) has exactly four fields; upstream `command_install` reads those four plus `quiet` (handled by cli before dispatch). The subset relation holds trivially and would continue to hold if `_ns_install` dropped `allow_insecure`.
- **Fix / opportunity:** Replace/augment the subset check with a positive requirement that every field `command_install`/`command_remove`/`command_reset` reads is present in the service's namespace (e.g. assert `allow_insecure` in `vars(_ns_install(...))`), or keep the four explicit asserts and drop the vacuous subset.
- **Risk if ignored:** A future namespace refactor that drops a field upstream reads would not be caught here; it would surface only as a runtime `AttributeError`/`TypeError` in the handler. P2.

### F4 · P2 · Sole-importer test has a dynamic-import blind spot
- **Where:** `tests/test_proot_surfaces.py:23-42` (`_imports_of` at :23-31, `test_only_proot_service_imports_proot_distro` at :34-42).
- **What:** `_imports_of` only recognizes static `import`/`import-from` AST nodes. A module could import `proot_distro` via `importlib.import_module("proot_distro")` (a string) and evade detection. `proot_service.py` itself does this legitimately (:47, :83), and grep of `src/` shows no other module imports `proot_distro` at all, so the rule holds today — but the test cannot prove it for dynamic imports.
- **Fix / opportunity:** Supplement with a grep/string-scan for `"proot_distro"` in `src/` (already done manually during this audit; clean) or document that dynamic imports must be added to the allowlist explicitly.
- **Risk if ignored:** Low today; a future contributor could bypass the sole-importer rule undetected. P2.

### F5 · P3 · Missing coverage across the service surface
- **Where:** `tests/test_proot_surfaces.py` (whole file, 11 tests).
- **What:** No tests exist for `remove_cached_image`, `rename_container`, `backup_container`, `restore_container`, `copy_path`, `kill_session`, `active_sessions`, `friendly_job_error`, `storage_bytes`, `busy_locks`, `cached_images`, `search_images`, `list_containers`, `_container_rows`, `_tree_bytes`; nor for `_run_command`'s non-zero `SystemExit` path (`:96-100`) or generic `Exception` path (`:101-102`); nor for `available() is True` (only the False off-device case at :123-130); nor for the real `get_proot_cmd` path (F1/F2). `test_bootstrap_is_idempotent_and_installs_shims` only asserts `_BOOTSTRAPPED is True`, not that env/shims were actually applied.
- **Fix / opportunity:** Add tests for each uncovered public function, prioritizing `get_proot_cmd` (F1/F2), `available()==True`, and `_run_command` failure branches.
- **Risk if ignored:** Regressions in storage/session/backup paths surface in the UI rather than in tests. P3.

### F6 · P3 · Dev-only list contains packages that are not dev-only in the venv
- **Where:** `tests/test_proot_surfaces.py:133-148` (`dev_only` set at :135-145).
- **What:** `requests` (and `binaryornot`, `cookiecutter`, `jinja2`, `flet_cli`, `flet_desktop`) are installed in `.venv` (`requests-2.34.2`, etc.) and are runtime dependencies of `proot_distro` itself (e.g. docker-helper search/download). The test only asserts `src/` doesn't import them, which currently holds, so the label "dev-only" is inaccurate for the venv as a whole — though correct for `src`. No code change needed; the test's actual assertion (src stays clean) is valid.
- **Risk if ignored:** None functional; naming is misleading if someone extends the list. P3.

## Verified-good list
- Sole-importer rule holds statically: only `src/services/proot_service.py` imports `proot_distro` (test passes; confirmed by grep of `src/`).
- `_ns_install`/`_ns_remove`/`_ns_reset` fields match upstream parser (`parser.py:194-212`, `install.py:140-183`, `remove.py:108-132`, `reset.py:44-65`); test passes.
- `env_contract()` sets all six asserted keys (`storage_paths.py:45-53`); `containers_dir()` is under `XDG_DATA_HOME` (`storage_paths.py:31-33`); package name is `ng.kiri.prootdistro`, not `com.termux` (`storage_paths.py:8`). Test passes.
- `bootstrap()` is idempotent and applies `TERMUX_APP__PACKAGE_NAME` (`proot_service.py:32-41`, `:40`). Test passes.
- `available() is False` when `proot_distro` is poisoned in `sys.modules` (`proot_service.py:44-50`). Test passes.
- `is_pull_limit()` recognizes 429/rate-limit markers (`proot_service.py:441-444`); test passes (markers vs live network UNVERIFIED).
- `src/` imports no dev-only packages (test passes).

## Unverified
- `get_proot_cmd` on Android where proot IS installed: the `sys.stdout.buffer` → `StringIO` `AttributeError` (F1) could not be triggered here because desktop `cli.main()` exits at `ensure_proot_installed()` before reaching `_print_command`; the `.buffer` mismatch itself was reproduced at the Python level. UNVERIFIED on-device.
- `is_pull_limit` markers against a real Docker Hub 429 response — no network in this environment. UNVERIFIED.
- Whether any `src/` module uses `importlib.import_module("proot_distro")` dynamically beyond `proot_service.py` — grep found none, but the AST test (F4) cannot prove the negative for string-based imports. UNVERIFIED by the test itself (proven clean by manual grep during this audit).
- `test_env_contract_is_import_safe` imports `from core import storage_paths`; relies on `src/core/__init__.py` existing and `pythonpath=["src"]` — confirmed by the passing test run, not re-checked independently.
