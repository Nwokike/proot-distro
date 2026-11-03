"""The notification icon drawables shipped via tool.flet.android.res_dir must
exist on disk — a silently dropped android_res/ breaks the FGS small icon."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENSITIES = ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi")


def test_notification_icon_drawables_exist_for_all_densities():
    for density in DENSITIES:
        icon = ROOT / "android_res" / f"drawable-{density}" / "ic_stat_prootdistro.png"
        assert icon.is_file() and icon.stat().st_size > 0, f"missing {icon}"


def test_pyproject_points_res_dir_at_android_res():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'res_dir = "android_res"' in pyproject
    assert 'android_default_icon' not in pyproject  # set in code, not here


def test_controller_uses_the_bundled_icon_name():
    src = (ROOT / "src" / "app_controller.py").read_text(encoding="utf-8")
    assert 'android_default_icon="ic_stat_prootdistro"' in src
