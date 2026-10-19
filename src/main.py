"""Entry point — construct the controller, run it."""

from __future__ import annotations

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

    async def _run() -> None:
        controller = AppController(page)
        await controller.init()

    def _flush(_e=None) -> None:
        pass

    page.on_disconnect = _flush
    page.on_close = _flush
    page.run_task(_run)


if __name__ == "__main__":
    # Assets sit next to this file when packaged (tool.flet.app.path = "src").
    assets = Path(__file__).resolve().parent / "assets"
    import flet as ft

    ft.run(main, assets_dir=str(assets) if assets.is_dir() else None)
