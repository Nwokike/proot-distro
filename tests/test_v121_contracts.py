"""v1.2.1 contract pins — the behaviours the 2026-11-17 device test demanded.

Each test names the device complaint it guards, so a future regression reads
as a user-visible bug rather than an abstract assertion.
"""

from __future__ import annotations

from pathlib import Path

from core.constants import AD_SLOT_INSTALL_LIST
from services.desk_service.guest_notifications import NotifyStreamParser
from services.session_service.argv import _harden_session

ROOT = Path(__file__).resolve().parents[1]


def test_notify_parser_reads_a_dbus_monitor_block():
    """Guest apps' Notify calls become (app, summary, body) triples."""
    parser = NotifyStreamParser()
    lines = [
        "method call time=1.2 sender=:1.4 -> destination=org.freedesktop.Notifications"
        " serial=7 path=/org/freedesktop/Notifications;"
        " interface=org.freedesktop.Notifications; member=Notify",
        '   string "Antigravity"',
        "   uint32 0",
        '   string "/usr/share/icons/app.png"',
        '   string "Build finished"',
        '   string "Your project compiled in 12s"',
        "   array [",
        "   ]",
        "   array [",
        "   ]",
        "   int32 -1",
    ]
    hits = [hit for hit in (parser.feed_line(line) for line in lines) if hit]
    assert hits == [("Antigravity", "Build finished", "Your project compiled in 12s")]


def test_notify_parser_ignores_other_calls_and_escapes():
    parser = NotifyStreamParser()
    assert parser.feed_line("method call time=1.0 -> destination=org.foo; member=Bar") is None
    lines = [
        "method call time=1.2 sender=:1.4 -> destination=org.freedesktop.Notifications"
        " serial=7 path=/org/freedesktop/Notifications;"
        " interface=org.freedesktop.Notifications; member=Notify",
        '   string "App"',
        "   uint32 0",
        '   string ""',
        '   string "Line\\nbreak"',
        '   string "Quote \\"x\\""',
    ]
    hits = [hit for hit in (parser.feed_line(line) for line in lines) if hit]
    assert hits == [("App", "Line\nbreak", 'Quote "x"')]


def test_pacman_sandbox_is_disabled_for_the_guest(tmp_path):
    """Arch's libalpm 7 sandbox cannot run under proot ("seccomp: 22"),
    so the session hardening disables it and pins the download user."""
    rootfs = tmp_path / "rootfs"
    (rootfs / "etc").mkdir(parents=True)
    conf = rootfs / "etc" / "pacman.conf"
    conf.write_text("[options]\nHoldPkg = pacman glibc\nDownloadUser = alpm\n", encoding="utf-8")
    _harden_session({}, ["proot", f"--rootfs={rootfs}", "/bin/sh"], "arch")
    text = conf.read_text(encoding="utf-8")
    assert "DisableSandbox" in text
    assert "DownloadUser = root" in text
    assert "DownloadUser = alpm" not in text
    # Idempotent: a second session must not append twice.
    _harden_session({}, ["proot", f"--rootfs={rootfs}", "/bin/sh"], "arch")
    assert conf.read_text(encoding="utf-8").count("DisableSandbox") == 1


def test_share_opens_without_a_tunnel():
    """A Local/LAN URL plus the code must be copyable even when the public
    tunnel is off (device 2026-11-17); the Share sheet needs a public URL."""
    src = (ROOT / "src" / "controller_actions" / "display_session.py").read_text(encoding="utf-8")
    share_fn = src.split("async def share_display")[1].split("async def ")[0]
    assert "no public URL yet. Turn on the tunnel" not in share_fn
    assert "Turn on the public tunnel to get a shareable link." in share_fn
    assert "Local" in share_fn and "LAN" in share_fn and "share_uri" in share_fn


def test_sandbox_flag_is_per_preset_with_sensible_defaults():
    """Detected apps start checked, user-made presets start unchecked, and the
    flag is never injected silently: unchecking removes it again (owner ruling
    2026-11-17)."""
    from screens.display_sheets.sheet_parts import with_sandbox

    assert with_sandbox("chromium", True).endswith(" --no-sandbox")
    assert with_sandbox("chromium --no-sandbox", True).count("--no-sandbox") == 1
    assert with_sandbox("xterm", False) == "xterm"
    assert "sandbox_prone" not in (ROOT / "src/services/proot_service/_queries.py").read_text(
        encoding="utf-8"
    )
    sheet = (ROOT / "src" / "screens" / "display_sheets" / "launcher_sheet.py").read_text(
        encoding="utf-8"
    )
    assert "sandbox_checks.setdefault(cmd, True)" in sheet  # detected app
    assert "sandbox_checks.setdefault(cmd, False)" in sheet  # saved preset
    view = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    assert "sandbox.get(cmd, True)" in view and "sandbox.get(cmd, False)" in view
    parts = (ROOT / "src" / "screens" / "display_sheets" / "sheet_parts.py").read_text(
        encoding="utf-8"
    )
    assert "sandbox_prone" not in parts
    assert "sandbox_checked" in parts  # preset_row exposes the checkbox


def test_ads_between_display_sections_and_after_the_home_distro_list():
    view = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    distros = view.index('_section("Distros"')
    banner = view.index("pooled_banner_ad(AD_SLOT_DISPLAY, page)")
    presets = view.index('_section("Presets"')
    assert distros < banner < presets
    assert 'insert_periodic(preset_rows, "display-presets"' in view
    home = (ROOT / "src" / "screens" / "distro" / "__init__.py").read_text(encoding="utf-8")
    tiles = home.index("_POPULAR_DISTROS]")
    home_banner = home.index("pooled_banner_ad(AD_SLOT_INSTALL_LIST, page)")
    assert tiles < home_banner
    assert AD_SLOT_INSTALL_LIST == "install-list-1"


def test_terminal_theme_defaults_follow_the_app_mode():
    state_src = (ROOT / "src" / "core" / "state.py").read_text(encoding="utf-8")
    assert '"theme": ""' in state_src  # auto: follows the app mode
    controls = (ROOT / "src" / "screens" / "terminal_controls.py").read_text(encoding="utf-8")
    assert '"Colab Light" if theme.is_light_theme() else "Dracula"' in controls


def test_guest_notification_watcher_is_wired():
    spawn = (ROOT / "src" / "services" / "desk_service" / "spawn_mixin.py").read_text(
        encoding="utf-8"
    )
    assert "_watch_guest_notifications" in spawn
    assert "on_guest_notification" in spawn
    manager = (ROOT / "src" / "services" / "desk_service" / "manager.py").read_text(
        encoding="utf-8"
    )
    assert "on_guest_notification" in manager
    assert "guest_notifications" in manager


def test_android_window_helpers_are_guarded_off_device():
    """pyjnius is absent in dev: every call must be a silent no-op."""
    from core import android_ui

    android_ui.set_keyboard_overlay(True)
    android_ui.set_keyboard_overlay(False)
    android_ui.set_system_bars_hidden(True)
    android_ui.set_system_bars_hidden(False)


def test_apps_probe_force_bypasses_the_cache():
    src = (ROOT / "src" / "controller_actions" / "display_apps.py").read_text(encoding="utf-8")
    assert "force" in src
    assert 'probe_cache.drop("apps", container)' in src
    assert "APPS_STALE_AFTER_SEC" in src
    state_src = (ROOT / "src" / "core" / "state.py").read_text(encoding="utf-8")
    assert "detected_apps_at" in state_src


def test_guest_exit_zero_ends_the_display_cleanly():
    """A command that finishes with 0 is not a crash: running a CLI file in a
    display must not leave a Failed row (device 2026-11-17)."""
    src = (ROOT / "src" / "services" / "desk_service" / "spawn_mixin.py").read_text(
        encoding="utf-8"
    )
    assert 'kind == "guest" and process.returncode == 0' in src


def test_reporting_a_problem_copies_the_log_then_opens_github():
    """Every log surface offers Copy + Report: copy, open GitHub Issues, paste."""
    dialogs = (ROOT / "src" / "screens" / "settings" / "dialogs.py").read_text(encoding="utf-8")
    assert "GITHUB_ISSUES_URL" in dialogs
    assert "Report on GitHub" in dialogs
    logs = (ROOT / "src" / "controller_actions" / "display_logs.py").read_text(encoding="utf-8")
    assert "Copy log" in logs and "Report on GitHub" in logs
    diag = (ROOT / "src" / "screens" / "help" / "diagnostics.py").read_text(encoding="utf-8")
    assert "def report_problem" in diag and "GITHUB_ISSUES_URL" in diag
    help_src = (ROOT / "src" / "screens" / "help" / "__init__.py").read_text(encoding="utf-8")
    assert "Report a problem on GitHub" in help_src


def test_xvnc_tmp_dir_exists_under_both_android_spellings():
    """The payload's baked prefix uses /data/data/<pkg> while Flet reports
    /data/user/0/<pkg>; Waydroid exposed only one, so both are created."""
    src = (ROOT / "src" / "services" / "desk_service" / "xvnc_paths.py").read_text(encoding="utf-8")
    assert 'Path("/data/data")' in src
    assert "PACKAGE_NAME" in src


def test_version_is_1_2_1_build_5():
    import tomllib

    from core.constants import APP_BUILD_NUMBER, APP_VERSION

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert APP_VERSION == "1.2.1"
    assert APP_BUILD_NUMBER == 5
    assert project["project"]["version"] == "1.2.1"
    assert int(project["tool"]["flet"]["build_number"]) == 5
    workflow = (ROOT / ".github" / "workflows" / "app.yml").read_text(encoding="utf-8")
    assert "'1.2.1'" in workflow and "'5'" in workflow


def test_play_features_are_declared_not_required():
    """RECORD_AUDIO implies android.hardware.microphone REQUIRED unless the
    feature is declared false — that filtered 18 devices in 1.2.0."""
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    features = project.split("[tool.flet.android.feature]")[1].split("\n\n")[0]
    for feature in (
        "android.hardware.microphone",
        "android.hardware.touchscreen",
        "android.software.leanback",
    ):
        assert f'"{feature}" = false' in features
    workflow = (ROOT / ".github" / "workflows" / "app.yml").read_text(encoding="utf-8")
    assert "uses-feature $feature must be declared required=false" in workflow


def test_file_preview_runs_in_the_files_own_folder():
    """Device 2026-11-17: `./file` was typed in a shell rooted at /root, so a
    run outside the home folder missed the file. Every run now uses the file's
    folder, and the default action streams output in place."""
    src = (ROOT / "src" / "screens" / "files" / "operations.py").read_text(encoding="utf-8")
    run_src = (ROOT / "src" / "screens" / "files" / "run_dialog.py").read_text(encoding="utf-8")
    assert "def open_file_run_dialog(" in run_src
    assert "open_file_run_dialog(page, container, folder, command)" in src  # used
    assert '{"work_dir": folder}' in src  # display run
    assert "open_session_with_options" in src  # terminal run starts in the folder
    assert 'shlex.quote(f"./{name}")' in src  # quoted default for names with spaces
    assert "command_capture" in run_src  # in-place runner streams the PTY output
    assert "for _ in range(80)" in src  # readiness wait, not a blind sleep
    assert "await _a.sleep(1.5)" not in src
    assert "Working dir:" in run_src
    assert "run_on_top=True" in run_src  # the keyboard never hides Run
    # The editable command lives in the Run dialog only: the preview shows the
    # three buttons and the file itself (owner ruling 2026-11-17).
    assert "Run command" not in src
    assert "binary_preview_card(" in src


def test_binary_files_are_described_not_dumped():
    from services.container_files_service import is_binary

    assert is_binary(b"\x00\x01\x02")
    assert is_binary(b"\xff\xfe\x00\x00")  # invalid UTF-8
    assert not is_binary(b"#!/bin/sh\necho hi\n")
    assert not is_binary("Grüße".encode())
