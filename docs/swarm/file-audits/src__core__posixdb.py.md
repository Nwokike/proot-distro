# src/core/posixdb.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/core/posixdb.py` (108 lines) · `src/core/proot_probe.py` · `src/services/proot_service.py` · `tests/test_core.py` · `.venv/lib/python3.14/site-packages/proot_distro/helpers/rootfs.py` (register_android_ids_at) · installed CPython 3.14.9 (`pwd`, `grp`, `os`) · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/posixdb.py` builds in-memory `pwd`/`grp` modules (via `types.ModuleType` + `namedtuple`) and installs them into `sys.modules` only for names that are not already importable, so that `proot_distro` (which unconditionally `import pwd`/`import grp` in `helpers/rootfs.py`) can run on Android CPython, where `grp` is absent (PEP 738). It is invoked lazily through `proot_service.bootstrap()` (`src/services/proot_service.py:32-41`), which calls `posixdb.ensure()` before any `proot_distro` import. It also exposes `probe()` for `tests/test_core.py`. The shim's two calls that actually matter to proot-distro are `pwd.getpwuid(uid).pw_name` and `grp.getgrgid(g).gr_name` inside `register_android_ids_at` (`.venv/.../proot_distro/helpers/rootfs.py:258,282`).

---

## Findings

### F1 · P2 · `grp` shim's `getgrgid` never raises `KeyError`, diverging from real `grp` and proot's skip logic
- **Where:** `src/core/posixdb.py:57-60` (`getgrgid` returns `struct_group(str(gid), ...)` unconditionally) · `.venv/lib/python3.14/site-packages/proot_distro/helpers/rootfs.py:280-282` (`except KeyError: continue`) · real `.venv` grp: `grp.getgrgid(999999)` raises `KeyError` (verified above).
- **What:** Real `grp.getgrgid` raises `KeyError` for an unknown gid; proot-distro relies on that to skip gids that have no group entry. The shim returns a synthetic entry for *every* gid, so `register_android_ids_at` emits an `aid_<gid>` line for every gid in `os.getgroups()` instead of only the ones resolvable on the device. Container `/etc/group` contents differ from a Termux run.
- **Evidence:** verified `grp.getgrgid(999999)` → `KeyError('getgrgid(): gid not found: 999999')` on installed CPython 3.14.9; shim code at `posixdb.py:57-60` has no raise path.
- **Fix / opportunity:** make `getgrgid` raise `KeyError(gid)` for gids that are not in a small allow-list, or document that the shim intentionally resolves all gids. If matching Termux is the goal, the shim would need the device's real group table, which it does not have (UNVERIFIED what Termux's grp returns for shared gids).
- **Risk if ignored:** container group files contain synthetic `aid_<n>` entries that do not exist on a real Termux install; possible mismatch in permission checks inside the guest.

### F2 · P2 · `grp.getgrgid` returns numeric `gr_name`, but real Android group names may be symbolic
- **Where:** `src/core/posixdb.py:59-60` (`return struct_group(str(gid), "x", gid, [])`) · `.venv/.../proot_distro/helpers/rootfs.py:282-288` (`f"aid_{gname}:x:{g}:..."`).
- **What:** The shim assumes `gr_name` should be the decimal gid so that proot's `aid_` prefix yields `aid_3003`. If the device's real `grp` returns symbolic names (e.g. `inet`, `net_bt_admin`, or `aid_inet`), proot produces `aid_inet`/`aid_aid_inet` instead. The "numeric names reproduce Android's aid_<gid> convention exactly" claim (`posixdb.py:58-59`) is UNVERIFIED against a real Android `grp`.
- **Evidence:** comment at `posixdb.py:58-59`; no Android device available in this environment.
- **Fix / opportunity:** validate on-device (or against the NDK/Bionic group table) what `grp.getgrgid(3003).gr_name` returns, and adjust the shim's naming rule or proot's prefix accordingly.
- **Risk if ignored:** guest `/etc/group` group names may not match what Android apps expect, breaking group-based permission inside containers (UNVERIFIED).

### F3 · P2 · `pwd.getpwuid` hard-codes `pw_gecos="Android app"` and `pw_shell="/sbin/nologin"` for every uid
- **Where:** `src/core/posixdb.py:33`.
- **What:** Real `pwd.getpwuid` returns the device's actual gecos/shell/home; the shim fabricates them. proot-distro only reads `.pw_name` (`rootfs.py:258`), so this is not functionally broken today, but any future caller (or a library imported inside the guest tooling) relying on `pw_dir`/`pw_shell`/`pw_gecos` gets fabricated values.
- **Evidence:** `posixdb.py:33` vs real entry `pwd.struct_passwd(... pw_gecos='Super User', pw_dir='/root', pw_shell='/bin/bash')` (verified).
- **Fix / opportunity:** acceptable as-is for the current proot-distro contract; if broader pwd consumers appear, populate from `os.environ`/constants instead.
- **Risk if ignored:** latent incorrect data for any new consumer of the shimmed `pwd`.

### F4 · P2 · `ensure()` and `_module_present()` are not thread-safe
- **Where:** `src/core/posixdb.py:76-107` (`_module_present`, `ensure`) · `src/services/proot_service.py:18,32-41` (`_BOOTSTRAPPED` plain bool).
- **What:** `ensure()` mutates `sys.modules` and `_module_present` reads it without a lock; `_BOOTSTRAPPED` is a module-global bool with no synchronization. `proot_service` calls `ensure()` from `asyncio.to_thread` paths (`refresh_containers`, etc.) and from the main thread, so concurrent first-time calls can both install shims / both run bootstrap.
- **Evidence:** `posixdb.py:101-107` (no lock); `proot_service.py:32-41` (plain `global _BOOTSTRAPPED`).
- **Fix / opportunity:** guard `ensure()` with a module-level `threading.Lock()` and make `bootstrap()` use the same lock (or `functools.lru_cache`/`threading`).
- **Risk if ignored:** double shim installation (benign-ish) or partial env contract application under concurrent startup.

### F5 · P3 · `_module_present` can mistake a failed import (`sys.modules[name] is None`) for "present"
- **Where:** `src/core/posixdb.py:83-88`.
- **What:** `if name in sys.modules: return True` treats a `None` entry left by a failed import as present, so `ensure()` skips it and leaves `pwd`/`grp` unimportable.
- **Evidence:** `posixdb.py:83-84`.
- **Fix / opportunity:** `mod = sys.modules.get(name); if mod is not None: return True` (and still run `find_spec` otherwise).
- **Risk if ignored:** rare import-ordering edge case where a prior failed import poisons the shim decision.

### F6 · P3 · `os.O_DIRECTORY` is not shimmed; `proot_distro` cannot import on Windows dev hosts
- **Where:** `src/core/posixdb.py` (scope is pwd/grp only) · `.venv/lib/python3.14/site-packages/proot_distro/dirfd.py:73` (`_O_RD_DIR = os.O_RDONLY | os.O_DIRECTORY`) · `src/services/proot_service.py:21-22`.
- **What:** The shim covers `pwd`/`grp` but not `os.O_DIRECTORY`, which CPython on Windows lacks. Consequently `proot_distro` (and the app's `available()`/`bootstrap()`) fail on the house dev platform (Windows, Python 3.14). This is an environmental limitation rather than a posixdb defect, but it is the reason the app's proot path is untestable locally.
- **Evidence:** `grep -rn "O_DIRECTORY" src/` → no hits; `.venv/.../proot_distro/dirfd.py:73` requires it; `os.O_DIRECTORY` present on this Linux venv (65536).
- **Fix / opportunity:** document the Windows dev limitation; optionally expose a dev-only `os.O_DIRECTORY` fallback (e.g. `getattr(os, "O_DIRECTORY", 0)`) only for import smoke tests, without changing production behavior. Do not fork proot-distro (D-001).
- **Risk if ignored:** local/CI-on-Windows test loops cannot exercise the proot path; already worked around by source-level audits.

### F7 · P3 · API-parity gaps vs. real `pwd`/`grp`
- **Where:** `src/core/posixdb.py:27-30, 52-55` (shimmed `struct_passwd`/`struct_group` are `namedtuple`s).
- **What:** Real `pwd.struct_passwd`/`grp.struct_group` expose `n_fields`, `n_sequence_fields`, `n_unnamed_fields` (verified on installed CPython 3.14.9); the shim's namedtuple classes do not. Conversely the shim exposes `_fields`/`_asdict` extras that real structs lack. Real `getpwuid`/`getgrgid` raise `KeyError` with descriptive messages; shim's `getpwuid` never raises and `getpwnam` raises `KeyError(name)`. `getpwall` returns only the current user; `getgrall` returns `[]` (intentional Termux parity). `getgrnam` always raises.
- **Evidence:** verified real struct attrs (`n_fields=7`, etc.) and exception messages above; shim code `posixdb.py:32-73`.
- **Fix / opportunity:** add `n_fields`/`n_sequence_fields`/`n_unnamed_fields` class attributes to both shimmed structs for closer parity; keep namedtuple base for indexing/field access.
- **Risk if ignored:** code that introspects `entry.n_fields` (none today) would break on the shimmed path.

### F8 · P3 · `_pw_name` naming convention is an assumption, not verified
- **Where:** `src/core/posixdb.py:15-17` (`f"u0_a{uid - 10000}" if uid >= 10000 else str(uid)`).
- **What:** Android app uids conventionally start at AID_APP_START (10000), so the formula is reasonable, but it is UNVERIFIED on the target Android 16 / arm64 device and does not account for multi-user (`u1_a…`) or isolated (`u0_i…`) process uids. proot-distro only uses the current process uid.
- **Evidence:** `posixdb.py:15-17`; no device available.
- **Fix / opportunity:** none needed for the single-app-uid case; document the multi-user limitation if the app ever runs under work profiles.
- **Risk if ignored:** wrong `pw_name` (and thus `aid_u0_a…` passwd entry) under multi-user/isolated uids.

### F9 · P3 · `probe()`/`ensure()` return values and idempotency are correct but `ensure()` is not idempotent across a *removed* native module
- **Where:** `src/core/posixdb.py:91-107`.
- **What:** `ensure()` correctly returns `[]` on a second call (verified by `test_ensure_only_shims_what_is_missing`), and `probe()` reports the right booleans. However, once a shim is installed it is never replaced even if a native module later becomes importable; and `ensure()` has no "uninstall"/reset path. The test fixture `_restore_db_modules` (`tests/test_core.py:12-21`) is the only cleanup, and it is module-local (flagged by the pytest audit).
- **Evidence:** `posixdb.py:96-107`; `tests/test_core.py:12-21`.
- **Fix / opportunity:** acceptable for production; consider a `reset()` helper for tests instead of hand-rolled fixture (optional).
- **Risk if ignored:** test-ordering leaks (already observed in the pytest utilization audit).

---

## Missed capabilities (dependency audits only)

Not applicable (this is a first-party shim, not a dependency). Adjacent missed capability: `proot_distro.helpers.rootfs.register_android_ids_at` is the sole consumer; the app does not register container ids itself (correct per D-001).

---

## Verified-good list

- **No import-time side effects:** importing `core.posixdb` does not call `ensure()` or mutate `sys.modules` (`posixdb.py` top-level only imports + definitions).
- **Shim shapes match the tests' contract:** `grp.getgrgid(3003)` → `gr_name=="3003"`, `gr_gid==3003`, `gr_mem==[]`; `getgrall()==[]`; `getgrnam` raises `KeyError`; `pwd.getpwuid(10315)` → `pw_name=="u0_a315"`, `pw_uid==10315`, `pw_shell=="/sbin/nologin"`; `getpwnam` raises for unknown names. (`tests/test_core.py:48-73`.)
- **Idempotency of `ensure()`:** returns exactly the missing set on first call and `[]` thereafter (`tests/test_core.py:40-45`).
- **`_module_present` handles the shimmed case:** a shimmed module has `__spec__ is None`, which makes `find_spec` raise `ValueError`; the function checks `sys.modules` first (`posixdb.py:83-88`). Verified syntax `except ValueError, ImportError:` is valid PEP 758 on Python 3.14 (packaging audit).
- **Field count matches:** `_STRUCT_PASSWD` has 7 fields and `_STRUCT_GROUP` has 4, matching real `pwd`/`grp` (verified).
- **`os.getuid`/`os.getgid`/`os.getgroups`/`os.O_DIRECTORY` exist on the installed Linux interpreter** (verified: `os.getuid()=1000`, `os.getgid()=1000`, `os.getgroups()=[10,1000]`, `os.O_DIRECTORY=65536`).
- **One upstream importer:** only `proot_service.py` imports `proot_distro`, and it calls `posixdb.ensure()` first (`proot_service.py:37-39`), respecting D-001.
- **Tests pass:** `pytest tests/test_core.py` → 7 passed.

---

## Unverified

- Behavior of a real Android 16 / arm64 `grp` module (Termux-style) for well-known and app gids; specifically whether `getgrgid(...).gr_name` is numeric or symbolic, and whether `getgrgid` raises `KeyError` for unknown gids. No Android device in this environment.
- Whether `pwd`/`grp` are actually absent/present on the target Flet Android runtime exactly as `test_core.py` assumes (device log cited in `docs/decisions.md:70-71`, not re-executed here).
- Whether `os.O_DIRECTORY` is available on the target Android interpreter (expected yes, UNVERIFIED).
- Multi-user / isolated-uid handling of `_pw_name`.