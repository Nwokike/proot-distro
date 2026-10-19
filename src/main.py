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
    import threading

    from app_controller import AppController

    controller = AppController(page)

    def _shutdown(_e=None) -> None:
        if threading.current_thread() is threading.main_thread():
            controller.session_manager.close_all()

    page.on_disconnect = _shutdown
    page.on_close = _shutdown
    atexit.register(controller.session_manager.close_all)
    page.run_task(controller.init)


if __name__ == "__main__":
    # Assets sit next to this file when packaged (tool.flet.app.path = "src").
    assets = Path(__file__).resolve().parent / "assets"
    import flet as ft

    ft.run(main, assets_dir=str(assets) if assets.is_dir() else None)
