"""Android window control through pyjnius (guarded: a no-op off-device).

Two things Flet cannot express on Android from Python:

- **Keyboard overlay**: the activity's default soft-input mode resizes the
  Flutter view, so opening the keyboard in the display viewer shrinks the
  WebView and noVNC re-fits the whole desktop into a sliver (device
  2026-11-17: "the whole screen moves up and it's now tiny"). ADJUST_NOTHING
  lets the keyboard sit ON TOP of the viewer, which is what the user expects.
- **Real fullscreen**: `page.window.full_screen` is desktop-only (mobile apps
  are embedded), so our orientation-based fullscreen still showed the status
  and navigation bars. Hiding the system bars makes the viewer actually
  full-screen, and restoring them brings the bars back on exit.

Every call is best-effort: no pyjnius (desktop/dev) or a refused call only
logs at debug level.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import ClassVar

logger = logging.getLogger(__name__)


def _activity():
    try:
        from jnius import autoclass

        return autoclass("com.flet.serious_python_android.PythonActivity").mActivity
    except Exception:
        return None


def _run_on_ui(activity, action: Callable[[], None]) -> None:
    """Run `action` on the Android UI thread (pyjnius Runnable, proven shape)."""
    try:
        from jnius import PythonJavaClass, java_method

        class _UiRunnable(PythonJavaClass):
            __javainterfaces__: ClassVar[list[str]] = ["java/lang/Runnable"]
            __javacontext__: ClassVar[str] = "app"

            @java_method("()V")
            def run(self) -> None:
                try:
                    action()
                except Exception as exc:  # never crash the UI thread
                    logger.debug("android ui action failed: %s", exc)

        activity.runOnUiThread(_UiRunnable())
    except Exception as exc:
        logger.debug("android ui runnable unavailable: %s", exc)


def set_keyboard_overlay(overlay: bool) -> None:
    """ADJUST_NOTHING while the viewer is mounted; ADJUST_RESIZE afterwards."""
    activity = _activity()
    if activity is None:
        return
    try:
        from jnius import autoclass

        params = autoclass("android.view.WindowManager$LayoutParams")
        mode = params.SOFT_INPUT_ADJUST_NOTHING if overlay else params.SOFT_INPUT_ADJUST_RESIZE

        def _apply() -> None:
            activity.getWindow().setSoftInputMode(mode)

        _run_on_ui(activity, _apply)
    except Exception as exc:
        logger.debug("soft input mode not changed: %s", exc)


def set_system_bars_hidden(hidden: bool) -> None:
    """Immersive fullscreen: hide/show the status and navigation bars."""
    activity = _activity()
    if activity is None:
        return
    try:
        from jnius import autoclass

        window = activity.getWindow()

        def _apply() -> None:
            # API 30+: the modern insets controller.
            try:
                controller = window.getInsetsController()
                if controller is not None:
                    insets = autoclass("android.view.WindowInsets$Type")
                    controller.setSystemBarsBehavior(
                        autoclass(
                            "android.view.WindowInsetsController"
                        ).BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                    )
                    if hidden:
                        controller.hide(insets.systemBars())
                    else:
                        controller.show(insets.systemBars())
                    return
            except Exception:
                pass
            # Legacy flags (still honored on older releases).
            view = autoclass("android.view.View")
            if hidden:
                flags = (
                    view.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | view.SYSTEM_UI_FLAG_FULLSCREEN
                    | view.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    | view.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | view.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | view.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                )
            else:
                flags = 0
            window.getDecorView().setSystemUiVisibility(flags)

        _run_on_ui(activity, _apply)
    except Exception as exc:
        logger.debug("system bars not changed: %s", exc)
