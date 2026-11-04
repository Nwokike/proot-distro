"""Entry point — construct the controller, run it."""

from __future__ import annotations

import atexit
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

# In-memory ring buffer for the Settings diagnostic terminal (Sherlock pattern):
# register on the ROOT logger so every module's log flows into it.
from core.logger_handler import in_memory_log_handler  # noqa: E402

logging.getLogger().addHandler(in_memory_log_handler)


def main(page) -> None:
    import flet as ft

    # Global FilePicker mounted at page level matching CollabShell standard
    file_picker = ft.FilePicker()
    page.services.append(file_picker)
    page.file_picker = file_picker

    from app_controller import AppController

    controller = AppController(page)

    # Register the house font once (Outfit variable — all weights).
    from core.theme import FONT_FILES

    page.fonts = FONT_FILES

    # A close/disconnect is NOT a shutdown: the foreground service (STICKY)
    # keeps the process alive in the background, and the shells (with their
    # scrollback) must survive until the user explicitly exits. Tearing down
    # sessions here killed everything whenever the activity was destroyed.
    page.on_disconnect = lambda _e=None: None
    page.on_close = lambda _e=None: None

    def _on_brightness(_e=None) -> None:
        # "System" mode must follow a runtime dark/light flip too, not just
        # the palette the app booted with.
        from core import theme

        theme.follow_platform_brightness(page)

    page.on_platform_brightness_change = _on_brightness
    page.on_resize = lambda _e: page.update()

    # Android back button: display fullscreen → display → terminal fullscreen
    # → terminal → default. Without this handler the back button closes the
    # activity outright.
    def _on_view_pop(_e) -> None:
        from core.state import state

        if state.active_display:
            if state.display_fullscreen:
                state.display_fullscreen = False
                page.update()
            else:
                page.run_task(controller.leave_display)
        elif state.terminal_fullscreen:
            state.terminal_fullscreen = False
            page.update()
        elif state.active_session:
            state.active_session = None
            page.update()

    page.on_view_pop = _on_view_pop

    atexit.register(controller.session_manager.close_all)
    page.run_task(controller.init)


if __name__ == "__main__":
    # Assets sit next to this file when packaged (tool.flet.app.path = "src").
    assets = Path(__file__).resolve().parent / "assets"
    import flet as ft

    ft.run(main, assets_dir=str(assets) if assets.is_dir() else None)
