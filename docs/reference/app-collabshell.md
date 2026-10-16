# app-collabshell.md — CollabShell (+ notebook I/O formats + flet-terminal usage)

Verified 2026-10-16 against `C:\Users\nwoki\.zcode\workspace\default\CollabShell`. This is the **only shipped consumer of `flet-terminal`** and the house's richest I/O-mapping example.

## Identity
"Colab Shell" v2.1.1 build 13, Python 3.14, bundle `ng.kiri.collabshell`. Wraps `google-colab-cli==0.7.4`; terminal UI = `flet-terminal==0.3.9`; flet set pinned `==1.0.3` (guarded by `tests/services/test_version_sync.py::test_flet_pins_in_sync`).

## Wrapping pattern
`ColabService` facade: ~20 thin `async` methods, each lazily importing `services.colab.<area>` impl and calling upstream inside `asyncio.to_thread` for blocking parts. Direct imports, zero vendoring — **but** the heaviest patch surface in the house: `src/core/storage_patch.py` monkeypatches 6 upstream things (TOKEN_CONFIG_PATH, `State.__init__`, `HistoryLogger.__init__`, settings defaults, `setup_logging`, rich FileProxy) + 2 `sys.modules` stubs (wsgiref for google_auth_oauthlib; jupyter_kernel_client) + 2 stream wrappers. **Anti-example for proot-distro-flet** — our package offers env-based relocation, so we need none of this. Deliberate restraint worth copying: `execution.py::_to_cell_output` refuses to handle `clear_output` because "surfacing it would mean bypassing runtime.execute_code — forking an upstream contract".

## Notebook I/O formats (the transferable spec)
- **Input**: `exec_code(code: str, env: dict|None, timeout=30.0, stdin_hook, on_output)`; optional env prelude (`import os; os.environ[...]`) prepended after a `/content` preflight; env keys validated `[A-Za-z_][A-Za-z0-9_]*`; history logs `env_keys` only, never values.
- **Stdin**: `src/core/stdin_hook.py` — modal dialog (`threading.Event().wait(timeout=300)`) for `input()`/`getpass` (dict prompt or keyword sniff: password/token/secret/api_key) and GCP OAuth URL capture; answer sent back as `input_reply`.
- **Output normalization** (`_to_cell_output`): `stream → {type, text, name?}` (`_join_text` joins chunk lists — never repr); `execute_result`/`display_data → {type, data (FULL MIME bundle — flattening to text/plain was a fixed Phase-2 bug), metadata?, execution_count?, transient?}`; `error → {type, ename, evalue, traceback[]}`; unknown types preserved, not dropped. Append-only outputs (no update-in-place; `transient.display_id` kept but unused).
- **Renderers**: stream/error → ANSI-to-text (`_MAX_SPANS=2000`); results → `ft.Image(src_base64=image/png)` else text/plain (no html/svg). Budgets: 5000 output entries, 4 MiB images (drop oldest image-bearing), 1000-control render cap, output `ListView` height 36–220 px. Incremental cache keyed by `outputs_rev`+count (extend-only on append) to avoid flicker.
- **Statuses**: only `is_running` bool; cancel = `{"type":"error","traceback":["Execution cancelled by user"]}` via `kernel_client.interrupt()`.

## Terminal panel (remote PTY — decisive fact)
The shell process is **REMOTE on Google Colab**, not local: `terminal_client.py` does `POST {base}/api/terminals` then `wss://…/terminals/websocket/{name}`; keystrokes `["stdin", text]`, resize `["set_size", rows, cols]`, output `["stdout", …]`; re-attach by term_name after reconnect ("Colab's PTY outlives the WebSocket hop"). **Zero local process-spawn code in the repo.** → It proves the flet-terminal VIEW works on Android with real typing; it does NOT prove local spawning (our M0 gate 4).
Wiring worth porting: `MobileTerminal(show_search=False, show_settings=False, scrollback=10000, font_family="JetBrains Mono", theme=BUILTIN_THEMES[...], auto_focus=False, expand=True)`; output `on_stdout → scrollback deque(maxlen=2000) → mt.send_bytes`; input `mt.set_on_bytes + on_data`; resize `mt.on_resize → set_size`; on Dart `mount` → `clear_pending()` + replay scrollback; reconnect backoff 1→15 s (12 tries) + token-heal on 404.

## Tests as our template (copy shapes)
`tests/services/colab/test_output_mapping.py` (pure asserts on `_join_text`/`_to_cell_output` incl. source guards), `test_execution_env.py` (patch upstream `State`, fake runtime capturing kwargs — prelude ordering, redaction, timeout parity), `test_terminal_client.py` (fake store + patched connect; token refresh/reconnect), `tests/screens/test_terminal_panel_wiring.py` (MagicMock MobileTerminal; byte flow, replay-on-mount, shared Clipboard). This is the offline-testability template for our `ProotSession` bridge.

## CI
5 jobs; apk-split uses `--split-per-abi --exclude pyarrow --skip-flutter-doctor` + `scripts/check_elf_alignment.py`; `target_arch=[arm64-v8a, armeabi-v7a]` because pyzmq's x86_64 wheel lacked 16 KB ELF alignment (32-bit exempt); Play AAB stamps `CHANNEL="play"`; Windows/Linux installers. No test job in main workflow (local-only suite — do NOT copy that part).
