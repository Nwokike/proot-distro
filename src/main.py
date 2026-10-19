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


def main(page) -> None:
    from app_controller import AppController

    controller = AppController(page)

    def _on_close(_e=None) -> None:
        controller.session_manager.close_all()

    # A disconnect is not a shutdown: the app may just be backgrounded, and the
    # shells (with their scrollback) must survive the resume.
    page.on_disconnect = lambda _e=None: None
    page.on_close = _on_close
    atexit.register(controller.session_manager.close_all)
    page.run_task(controller.init)


if __name__ == "__main__":
    # Assets sit next to this file when packaged (tool.flet.app.path = "src").
    assets = Path(__file__).resolve().parent / "assets"
    import flet as ft

    ft.run(main, assets_dir=str(assets) if assets.is_dir() else None)
