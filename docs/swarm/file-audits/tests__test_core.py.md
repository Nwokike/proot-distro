# tests/test_core.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `tests/test_core.py` (110 lines) · supporting reads `src/core/posixdb.py`, `src/core/storage_paths.py`, `src/core/changelog.py`, `tests/conftest.py`, `src/core/proot_probe.py`, `src/core/state.py` · installed CPython 3.14.9 / pytest 9.1.1 / flet 1.0.4 at `.venv/` · `pyproject.toml` `[tool.pytest.ini_options]` `pythonpath=["src"]` · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/test_core.py` ("Core-side tests: the grp/pwd shims and the payload probe") exercises the Android `pwd`/`grp` shims in `src/core/posixdb.py`, the environment/payload probe in `src/core/proot_probe.py`, and (out of module-scope per its own docstring) `src/core/state.py`. It runs under `pythonpath=["src"]` so `import core.*` resolves. It contains 7 tests, no `unittest.mock`/`patch`, and one autouse fixture `_restore_db_modules` (`tests/test_core.py:12-21`) that saves/restores `sys.modules["pwd"]`/`["grp"]` around every test to stop shims installed by `posixdb.ensure()` from leaking between tests. Ground truth: `pytest tests/test_core.py` → `7 passed in 0.34s`.

## Findings

### F1 · P2 · Shim cleanup fixture is module-local — order-dependency risk on `sys.modules["pwd"]`/`["grp"]` (flagged by sibling audit)
- **Where:** `tests/test_core.py:12-21` (`_restore_db_modules` autouse save/restore); `tests/test_core.py:40-45` (`test_ensure_only_shims_what_is_missing` mutates `sys.modules` via `posixdb.ensure()`); `tests/test_core.py:32-34` (Windows branch asserts `probe == {"pwd": False, "grp": False}`).
- **What:** `test_ensure_only_shims_what_is_missing` installs shims into `sys.modules` and relies entirely on the autouse fixture teardown (`tests/test_core.py:17-21`) to undo it. The fixture lives only in this file (not `tests/conftest.py`), so the sibling pytest audit flags this as order-dependent and recommends promoting `_restore_db_modules` verbatim into `tests/conftest.py` as a session/module-scoped autouse fixture (`docs/swarm/file-audits/tests__conftest.py.md` F5 cites `test_core.py:12-21`). On Windows neither module exists natively, so `ensure()` installs both and `test_probe_reports_real_modules:32-34` depends on them being absent afterward; a teardown lapse, xdist reorder, or `--ff` would leak a shim and flip the probe result. Currently holds on Linux (7 passed); Windows branch and cross-order behavior UNVERIFIED (no Windows host).
- **Evidence:** `tests/test_core.py:12-21,40-45,32-34`; pytest run `7 passed`; `docs/swarm/file-audits/tests__conftest.py.md` F5 (`"order-dependency risk on Windows"`, `"--ff/xdist change the answer"`).
- **Fix / opportunity:** Move `_restore_db_modules` (`tests/test_core.py:12-21`) into `tests/conftest.py` as an `autouse` fixture. Zero behavior change today (test_core.py is the sole posixdb consumer); removes the cross-test/xdist leak vector.
- **Risk if ignored:** order-dependent red tests where a shimmed module is read as present (`probe` returns `True` for a shim), breaking `tests/test_core.py:32-34` on Windows and any future posixdb consumer.

### F2 · P2 · `test_ensure_only_shims_what_is_missing` is a tautology — it never verifies the shim actually works
- **Where:** `tests/test_core.py:40-45`.
- **What:** `missing` is computed with the same `_module_present` that `ensure()` consults (`src/core/posixdb.py:76-107`), then `assert shimmed == missing` merely re-states `ensure()`'s own implementation. It never asserts the installed shim is importable or functional (no `import pwd` / `pwd.getpwuid(1)` after `ensure()`), nor that `sys.modules` gained the shim. On this Linux dev host both `pwd`/`grp` are native → `missing == []` → the shim-install branch never executes here; the install path is only touched indirectly by the direct factory calls in `:48-73`. Windows install-path UNVERIFIED.
- **Evidence:** `tests/test_core.py:43-45`; `src/core/posixdb.py:83-107`; pytest run `7 passed` (`[] == []` on Linux).
- **Fix / opportunity:** Add a post-condition that each name returned by `ensure()` is importable and behaves (call `getpwuid`/`getgrgid` after `ensure()`), or deterministically exercise the install path (temporarily hide the native module).
- **Risk if ignored:** a regression where `ensure()` still returns `missing` but installs a broken/non-importable shim would pass this test and poison `proot_distro` imports downstream (`src/services/proot_service.py:32-41` calls `ensure()` first).

### F3 · P2 · Weak, platform-dependent assertion in `test_f2fs_probe_reports_a_verdict`
- **Where:** `tests/test_core.py:91-98` (`assert "f2fs" in verdict.lower()` at `:98`); `src/core/proot_probe.py:38-62` (`_f2fs_probe`).
- **What:** `_f2fs_probe` returns `"f2fs bug NOT present in ..."` (contains "f2fs") on case-sensitive fs, `"f2fs-bug signature present in ..."` (contains "f2fs") on a buggy f2fs, but `"case-INSENSITIVE filesystem in ..."` (NO "f2fs") on a case-insensitive fs and `"probe failed: ..."` (NO "f2fs") if `mkdtemp` fails. So the assertion passes whenever the probe merely runs, regardless of the actual case-sensitivity result, and cannot distinguish working vs buggy f2fs. It will FAIL on case-insensitive filesystems/dev. Verified-passing here (Linux ext4); case-insensitive behavior UNVERIFIED.
- **Evidence:** `tests/test_core.py:92-98`; `src/core/proot_probe.py:41-52` (return strings); pytest run `7 passed`.
- **Fix / opportunity:** Assert the actual expected verdict for the host filesystem (e.g. `"f2fs bug NOT present"` on case-sensitive ext4) rather than a substring both outcomes satisfy.
- **Risk if ignored:** false green on filesystems where f2fs case-sensitivity matters; test is environment-sensitive and can flip between dev/CI.

### F4 · P2 · Missing coverage: `storage_paths.py` and `changelog.py` are not tested at all
- **Where:** `tests/test_core.py` (full read — no `import core.storage_paths` or `import core.changelog` anywhere; imports are only `core.posixdb` `:28,:41,:55,:66`, `core.proot_probe` `:80,:94`, `core.state` `:105`).
- **What:** `src/core/storage_paths.py` (`support_root`, `xdg_data_home`, `containers_dir`, `env_contract` at `:36-53` — the env proot-distro must see before first import) and `src/core/changelog.py` (`notes_for` at `:16-18`, with the `next(iter(CHANGELOG.values()), "")` fallback for unknown versions) have zero test coverage in this file. `notes_for("missing")` fallback is untested.
- **Evidence:** `tests/test_core.py` imports list; `src/core/storage_paths.py:36-53`; `src/core/changelog.py:16-18`.
- **Fix / opportunity:** Add tests for `storage_paths.env_contract()` (all six keys present, values derived from `support_root`) and `changelog.notes_for` (known version, unknown-version fallback, empty changelog).
- **Risk if ignored:** regressions in the env contract (read import-time by proot-distro, mirrored to upstream `constants.py:47-99`) go undetected until device runtime.

### F5 · P3 · `test_probe_reports_a_problem_without_native_libs` covers only the early-return branch; `assert result.ok is True` is trivial
- **Where:** `tests/test_core.py:79-88`; `src/core/proot_probe.py:65-136`.
- **What:** Deleting `ANDROID_NATIVE_LIBRARY_DIR` (`tests/test_core.py:82,86`) makes `_native_library_dir()` return `None` (`src/core/proot_probe.py:26-35`), so `bootstrap_env` returns early at `:72-74` with `problems=["no nativeLibraryDir — ..."]` — exactly what `:88` asserts. `assert result.ok is True` (`:84`) is just a fresh-dataclass default check. The rest of `bootstrap_env` (payload staging `:80-99`, f2fs `:109-113`, proot exec `:115-125`, storage write `:127-134`) is unreachable without native libs/flet-proot and is NOT exercised in dev. Note `bootstrap_env` is reached twice (`:82` and `:86` both delete the same var — redundant). The f2fs probe itself IS separately covered via `:91-98` calling `_f2fs_probe` directly.
- **Evidence:** `tests/test_core.py:79-88`; `src/core/proot_probe.py:72-74,80-134`; pytest run `7 passed`.
- **Fix / opportunity:** environmental (needs Android/native libs + flet-proot wheel) — document as out of scope for dev CI; optionally stage a fake native dir via monkeypatch to reach staging/f2fs paths if a fixture tree can be built.
- **Risk if ignored:** bootstrap regressions (staging, proot exec, storage write) invisible on dev host.

### F6 · P3 · Chained single assert obscures which field failed
- **Where:** `tests/test_core.py:59` (`entry.gr_name == "3003" and entry.gr_gid == 3003 and entry.gr_mem == []`).
- **What:** One assert covers three fields; a failure reports only line 59, not which field mismatched. Cosmetic/debuggability only.
- **Evidence:** `tests/test_core.py:59`; contract verified by passing run (`grp.getgrgid(3003)` shape matches).
- **Fix / opportunity:** Split into three independent asserts.
- **Risk if ignored:** slower debugging when a shim field drifts; no functional impact.

## Mocking-what-it-should-verify check
None found. The file has no `unittest.mock`/`patch` (verified by full read). `monkeypatch.delenv("ANDROID_NATIVE_LIBRARY_DIR", ...)` at `tests/test_core.py:82,86` only removes an env var to create the absence condition — legitimate setup, not a mock of the SUT. `test_grp_shim_shapes`/`test_pwd_shim_shapes` (`:48-73`) call the shim factories directly, but that is intentional per their docstrings ("Called on the factories directly so the contract is covered everywhere").

## Missed capabilities (dependency audits only)
N/A — this is a first-party file audit, not a dependency audit.

## Verified-good list
- `pytest tests/test_core.py` → `7 passed in 0.34s` on CPython 3.14.9 / pytest 9.1.1 (ground truth).
- `tests/test_core.py:37` (`probe["pwd"] is True` on Linux) and `:45` (`shimmed == missing`, `[] == []` since both modules native on Linux) pass.
- `tests/test_core.py:88` (`"nativeLibraryDir" in res.problems[0]` via `bootstrap_env` early return at `src/core/proot_probe.py:72-74`) passes.
- `tests/test_core.py:48-73` shim shapes match `src/core/posixdb.py:27-73` (`grp.getgrgid(3003)` → `gr_name=="3003"`/`gr_gid==3003`/`gr_mem==[]`; `getgrall()==[]`; `getgrnam` raises `KeyError`; `pwd.getpwuid(10315)` → `pw_name=="u0_a315"`/`pw_uid==10315`/`pw_shell=="/sbin/nologin"`; `getpwnam` raises).
- `src/core/state.py` imports cleanly under flet 1.0.4 and `test_state_starts_empty` (`tests/test_core.py:104-109`) passes (`containers==[]`, `installing is None`, `probe_passed is False`).
- `src/core/posixdb.py` has no import-time side effects (does not call `ensure()` / mutate `sys.modules` at import).
- `except ValueError, ImportError:` at `src/core/posixdb.py:87` is valid Python 3.14 and catches both exceptions (empirically verified); `_module_present` correctly checks `sys.modules` before `find_spec` (`:83-88`).

## Unverified
- `tests/test_core.py:32-34` Windows branch (`probe == {"pwd": False, "grp": False}`) — no Windows host; `sys.platform == "win32"` path not executed here.
- `tests/test_core.py:44-45` shim-install branch of `ensure()` on Windows (`missing == ["pwd","grp"]`) — on Linux `missing == []` so install path not exercised by this test.
- `tests/test_core.py:98` on a case-insensitive filesystem (`"case-INSENSITIVE filesystem"` verdict lacks "f2fs" → would fail) — not reproducible on this ext4 host.
- Whether `test_ensure_only_shims_what_is_missing`'s sys.modules mutation ever leaks under xdist/`--ff`/reorder — held by fixture teardown on this run; order-dependency risk is F1, not a current failure.
- Real Android 16/arm64 `grp`/`pwd` behavior referenced in `tests/test_core.py:36-37` comment ("Device truth (Android log)") — no device available; taken as prior knowledge, not re-executed here.
