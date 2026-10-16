# dep-proot-distro.md — proot-distro 5.10.0 wheel (integration contract)

Verified 2026-10-16 against the INSTALLED wheel in `.venv/Lib/site-packages/proot_distro` (R6 study). This is the contract `services/proot_service.py` must be written against.

## Identity
GPL-3.0-only, `Requires-Python >=3.9`, **zero runtime deps**. Console scripts: **`pd`** and `proot-distro` (`proot_distro.cli:main`). 93 files incl. the full Dockerfile build engine + shell completions. `__init__.py` exports nothing — `cli.main` is the public entry point.

## Install path (in-process)
`commands/install.py::command_install` (argparse namespace + **`sys.exit(1)` on every error**) → `_run_install(name, image_ref, local_path, url, dist_arch, allow_insecure)` → `helpers/docker/pull.py::pull_image(ref, rootfs_fd, arch, insecure) -> {manifest, image_config}` (raises `RuntimeError`) or `install_local.py::install_from_local_file(archive, rootfs_fd, arch)`. `pull_image` needs a **pinned `rootfs_fd`** from `paths.open_container_pair(name, create=True)` — not a path (dirfd convention).

## Login (never in-process)
`command_login` ends in **`os.execvpe`** — calling it in-process replaces the app. `--get-proot-cmd` prints a command line BUT it deliberately differs from the real exec (path pinning). Two viable routes: (a) build argv ourselves via `commands/login/proot_cmd.py::build_proot_args` (**13 keyword-only params**, fragile) after replicating the preamble (`migrate_legacy_proot`, `open_container_pair`, `_detect_dist_type`, `_resolve_login_user`, `_build_normal_env`, `get_emulator_args`, `get_proot_bin`); or (b) keep login as the ONLY subprocess spawn and let the CLI own its argv (public CLI contract — better update-safety). **Our design: (b), with the structured mode wrapping one-shot commands.**

## Progress (no callbacks)
`progress.progress_active()` = `sys.stderr.isatty() and not quiet` → **bars auto-suppress on non-TTY**; `log_info` stage lines go to stderr unless `--quiet`. **Do not monkeypatch `draw_bytes_bar`.** Capture stage lines with `contextlib.redirect_stderr` around in-process calls, or parse subprocess stderr; UI shows stage-level + indeterminate progress.

## Env/storage contract (set BEFORE first import — constants are computed at import time)
`TERMUX_APP_PACKAGE` / `TERMUX_HOME` / `TERMUX_PREFIX` (env-overridable; defaults are com.termux paths), `PD_PROOT_BIN` (absolute proot path; else `shutil.which`), `XDG_DATA_HOME`/`XDG_CACHE_HOME` (non-Termux storage root), `PD_DOCKER_AUTH` (private registries). `IS_TERMUX` = ≥2 of (android-ish platform, TERMUX_VERSION env, prefix accessible) — in our app it will be False → generic mode: **skips** `--kill-on-exit`/`--link2symlink`/`--sysvipc`/kernel-release fake and Termux-only binds (roadmap parking-lot: consider TERMUX-masquerade env to unlock Termux-mode flags after M0).
Writes: `containers/<name>/{rootfs,manifest.json,shm,.l2s}`, `locks/`, `sessions/<pid>.json`, `oci_layers/`, `oci_manifests/`.

## Blocking
All synchronous `urllib` (120 s timeout, 5×5 s retries, time.sleep). Download/layer-apply/tar-extract are long — always off the Flet main thread.

## Failure modes
No proot → `crit_error` + `sys.exit(1)` (startup probe exempts build/push/kill/ps/search); network → `RuntimeError("Cannot download …")`/`("Network error: …")`; bad ref → `InvalidReference(RuntimeError)`; nested proot → `_refuse_nested_proot` always runs (TracerPid check). **Wrap every call expecting `SystemExit` + `RuntimeError`.**

## Update safety (bump = cheap, but re-verify)
SAFE surfaces: env-var contract, on-disk layout, pure helpers (`parse_reference`, `derive_alias`, `iter_cached_images`, `paths.installed_container_names/container_rootfs`, `arch.*`, `progress.fmt_size`).
FRAGILE (isolate behind one adapter): `command_*` signatures, `build_proot_args` (13 kwargs), `_run_install`/`_login_with_rootfs`, `ContainerLock`, the rootfs_fd convention. Re-verify `constants.py` + `build_proot_args` on each 5.x bump.
