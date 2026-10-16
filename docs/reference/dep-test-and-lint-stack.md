# dep-test-and-lint-stack.md — pytest stack / ruff / watchdog

Verified 2026-10-16 against `.venv/Lib/site-packages` (D4 + D5 studies). All dev-only.

## pytest 9.1.1 (MIT) — house config compatibility
- `strict_config`, `strict_markers`, `filterwarnings` (linelist), `pythonpath` (paths ini) all exist with expected semantics in this version.
- **Config mode**: use `[tool.pytest.ini_options]` (string-INI compat). `[tool.pytest]` (native-TOML) is a different, mutually exclusive mode — having BOTH = hard `UsageError`. First config-bearing file wins in rootdir discovery order.
- Plugin autoload on by default → pytest-timeout autoloads with no extra config.
- Optional hardening available: `minversion`, `required_plugins` (packaging-backed).

## pytest-timeout 2.4.0 (MIT)
- Key is `timeout` (ini or `--timeout`); default = none.
- **Method default is platform-dependent**: `signal` where SIGALRM exists (Linux/CI), `thread` on Windows. For a Windows+Linux CI matrix, pin **`timeout_method = "thread"`** for uniform behavior (house style uses `timeout = 60`).

## packaging 26.3 (Apache-2.0 OR BSD-2-Clause)
- Version/specifier parsing under pytest (and flet-cli). No config surface needed.

## ruff 0.17.1 (MIT)
- Single Rust binary (`maturin`-built, no Python deps); host-only, never ships.
- All house keys valid at this version: `target-version = "py313"`, full select list, `per-file-ignores`, `line-length`. **Unknown/renamed keys hard-error** (fails loudly — desirable).
- Run via the locked venv (`uv sync` then `ruff check`) so the version can't float.

## watchdog 6.0.0 (Apache-2.0)
- Used **only** by `flet run` hot-reload (`flet_cli/commands/run.py`); zero effect in `flet build`/CI.
- Pure-Python with per-OS observer backends; inert in our context.

## pluggy 1.7.0 / iniconfig 2.3.1 / colorama 0.4.6
- pytest internals + Windows ANSI (also `qrcode`'s dep in flet-cli). Nothing to configure.
