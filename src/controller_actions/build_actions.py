"""Build + push actions (Dockerfile → OCI image → registry)."""

from __future__ import annotations

import asyncio
import logging

from core.state import state

logger = logging.getLogger(__name__)


class BuildActions:
    """Dockerfile build + registry push, streamed live like installs."""

    async def run_build(self, opts: dict) -> None:
        if state.build_busy:
            return
        state.build_busy = True
        state.build_stage = "preparing"
        state.build_logs = []
        state.build_result = None

        loop = self.page.loop

        def _apply_line(line: str) -> None:
            clean = line.strip()
            state.build_stage = clean or state.build_stage
            if clean:
                state.build_logs.append(clean)
                if len(state.build_logs) > 500:
                    state.build_logs.pop(0)

        def _on_line(line: str) -> None:
            loop.call_soon_threadsafe(_apply_line, line)

        try:
            outcome = await asyncio.to_thread(self.proot.build_image, on_line=_on_line, **opts)
            state.build_stage = (
                "build finished" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
            if outcome.ok:
                # The tags/layers summary is the last stage lines; keep them visible.
                state.build_result = {
                    "tags": opts.get("tags") or [],
                    "output": outcome.output[-2000:],
                }
            self.show_snack(state.build_stage)
        except Exception as exc:
            state.build_stage = f"build failed: {exc!r}"
            self.show_snack(state.build_stage)
            logger.exception("Build failed")
            raise
        finally:
            state.build_busy = False
            await self.refresh_containers()

    async def push_image(self, image_ref: str, arch: str = "", insecure: bool = False) -> None:
        if state.push_busy:
            return
        state.push_busy = True
        state.push_status = f"pushing {image_ref}…"
        loop = self.page.loop

        def _on_line(line: str) -> None:
            loop.call_soon_threadsafe(lambda ln: setattr(state, "push_status", ln.strip()), line)

        try:
            outcome = await asyncio.to_thread(
                self.proot.push_image,
                image_ref,
                override_arch=arch or None,
                allow_insecure=insecure,
                on_line=_on_line,
            )
            state.push_status = (
                f"pushed {image_ref}" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
            self.show_snack(state.push_status)
        except Exception as exc:
            state.push_status = f"push failed: {exc!r}"
            self.show_snack(state.push_status)
            logger.exception("Push failed for %s", image_ref)
            raise
        finally:
            state.push_busy = False

    async def clear_build_cache(self) -> None:
        outcome = await asyncio.to_thread(self.proot.clear_cache, build_cache=True)
        self.show_snack(
            "build cache cleared" if outcome.ok else self.proot.friendly_job_error(outcome)
        )
        await self.refresh_containers()

    async def storage_detail(self) -> dict:
        return await asyncio.to_thread(self.proot.storage_detail)

    async def refresh_storage_detail(self) -> None:
        try:
            state.storage_detail = await asyncio.to_thread(self.proot.storage_detail)
        except Exception as exc:
            state.data_note = f"storage detail failed: {exc}"
