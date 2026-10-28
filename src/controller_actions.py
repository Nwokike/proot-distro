"""AppController — owns the services and every action."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import storage_paths, theme
from core.state import state

logger = logging.getLogger(__name__)


def _reason(exc: BaseException) -> str:
    """One honest line for a failure — never a bare swallow."""
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:200]


class DistroActions:
    async def install_distro(self, image: str, name: str) -> None:
        if state.installing:
            return
        if await asyncio.to_thread(self.proot.busy_locks):
            state.busy_note = "another install is already running"
            return
        state.installing = name or image
        state.install_stage = "preparing"
        state.install_logs = []
        state.install_completed = False
        state.install_dialog_minimized = False
        state.busy_note = ""

        loop = self.page.loop

        def _apply_line(line: str) -> None:
            clean = line.strip()
            state.install_stage = clean
            if clean:
                state.install_logs.append(clean)
                if len(state.install_logs) > 500:
                    state.install_logs.pop(0)
            # Live-update the modal controls if the dialog is still open.
            stage_ctrl = getattr(self.page, "_install_stage_text", None)
            logs_ctrl = getattr(self.page, "_install_logs_column", None)
            if stage_ctrl is not None:
                stage_ctrl.value = clean or state.install_stage
                stage_ctrl.update()
            from core import tokens as _t

            if logs_ctrl is not None:
                logs_ctrl.controls = [
                    ft.Text(
                        ln,
                        font_family="JetBrains Mono",
                        size=_t.FONT_XXS,
                        color=theme.text_dim(),
                    )
                    for ln in state.install_logs[-60:]
                ]
                logs_ctrl.update()
            dialog = getattr(self.page, "_install_dialog", None)
            if dialog is not None and dialog.open:
                dialog.update()

        def _on_line(line: str) -> None:
            loop.call_soon_threadsafe(_apply_line, line)

        def _run():
            return self.proot.install(image, name, on_line=_on_line)

        outcome = None
        try:
            outcome = await asyncio.to_thread(_run)
            if outcome.ok:
                state.install_stage = f"installed {state.installing}"
            else:
                state.install_stage = (
                    self.proot.PULL_LIMIT_COPY
                    if self.proot.is_pull_limit(outcome)
                    else self.proot.friendly_job_error(outcome)
                )
                self.show_snack(state.install_stage)
        except Exception as exc:
            state.install_stage = f"install failed: {exc!r}"
            self.show_snack(state.install_stage)
            logger.exception("Could not install %s", image)
            raise
        finally:
            installed_now = state.installing
            state.installing = None
            await self.refresh_containers()
            # Close the install progress modal automatically when done, unless
            # the user already minimized it into the background banner.
            if not state.install_dialog_minimized:
                self.page.pop_dialog()
            dialog = getattr(self.page, "_install_dialog", None)
            if dialog is not None and not dialog.open:
                self.page._install_dialog = None
                self.page._install_stage_text = None
                self.page._install_logs_column = None
            if installed_now and outcome is not None and outcome.ok:
                state.install_completed = True
                state.last_installed = installed_now
                await self.ad_service.show_interstitial()

    async def remove_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.remove_container, name)
        self.show_snack(f"removed {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def reset_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.reset_container, name)
        self.show_snack(f"reset {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def search_distro(self, query: str) -> None:
        state.search_status = f"searching “{query}”…"
        await self.ad_service.show_interstitial()
        try:
            results = await asyncio.to_thread(self.proot.search_images, query)
        except Exception as exc:
            state.search_results = []
            state.search_status = f"search failed: {_reason(exc)}"
            logger.exception("Distro search failed for %r", query)
            raise
        state.search_results = results
        state.search_status = (
            f"{len(results)} result(s) — tap one to fill the fields"
            if results
            else "no results (or the search failed)"
        )

    async def clear_cache(self) -> None:
        if state.cache_busy:
            return
        state.cache_busy = True
        try:
            outcome = await asyncio.to_thread(self.proot.clear_cache)
            self.show_snack(
                "cached downloads cleared" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
        except Exception as exc:
            self.show_snack(f"cache clear failed: {exc!r}")
            logger.exception("Could not clear the image cache")
            raise
        finally:
            state.cache_busy = False
            await self.refresh_containers()

    async def clear_orphan_layers(self) -> None:
        if state.cache_busy:
            return
        state.cache_busy = True
        try:
            outcome = await asyncio.to_thread(self.proot.clear_cache, orphan=True)
            self.show_snack(
                "orphan layers cleared" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
        except Exception as exc:
            self.show_snack(f"orphan sweep failed: {exc!r}")
            logger.exception("Could not sweep orphan image layers")
            raise
        finally:
            state.cache_busy = False
            await self.refresh_containers()

    async def remove_cached_image(self, identifier: str) -> None:
        if state.cache_busy:
            return
        state.cache_busy = True
        try:
            outcome = await asyncio.to_thread(self.proot.remove_cached_image, identifier)
            self.show_snack(
                f"removed {identifier}" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
        except Exception as exc:
            self.show_snack(f"image remove failed: {exc!r}")
            logger.exception("Could not remove cached image %s", identifier)
            raise
        finally:
            state.cache_busy = False
            await self.refresh_containers()


class ContainerActions:
    async def rename_container(self, orig: str, new: str) -> None:
        new = new.strip()
        if not new:
            return
        outcome = await asyncio.to_thread(self.proot.rename_container, orig, new)
        self.show_snack(
            f"renamed to {new}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )
        await self.refresh_containers()

    async def backup_container(self, container: str) -> None:
        if self.file_picker is None:
            self.show_snack("file picker unavailable on this build")
            return
        # Stage the archive in app storage first, then hand the BYTES to the
        # picker: on mobile `save_file` without `src_bytes` raises ValueError
        # (there is no writable shared path to stream to), which made the
        # backup action die silently on the only platform that ships.
        staging = storage_paths.support_root() / "exports" / f"{container}.tar.gz"

        def _stage() -> object:
            staging.parent.mkdir(parents=True, exist_ok=True)
            return self.proot.backup_container(container, str(staging))

        outcome = await asyncio.to_thread(_stage)
        if not outcome.ok:
            self.show_snack(self.proot.friendly_job_error(outcome))
            return
        target = await self.file_picker.save_file(
            dialog_title=f"Backup {container}",
            file_name=f"{container}.tar.gz",
            src_bytes=staging.read_bytes(),
        )
        if not target:
            self.show_snack(f"backup staged at {staging}")
            return
        self.show_snack(f"backup written to {target}")
        await self.ad_service.show_interstitial()

    async def restore_container(self) -> None:
        if self.file_picker is None:
            self.show_snack("file picker unavailable on this build")
            return
        picked = await self.file_picker.pick_files(
            dialog_title="Restore a container archive", allow_multiple=False
        )
        if not picked:
            return
        path = picked[0].path
        outcome = await asyncio.to_thread(self.proot.restore_container, path)
        self.show_snack(
            "container restored" if outcome.ok else self.proot.friendly_job_error(outcome)
        )
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def copy_path(self, source: str, destination: str) -> None:
        source = source.strip()
        destination = destination.strip()
        if not source or not destination:
            self.show_snack("copy needs a source and a destination")
            return
        outcome = await asyncio.to_thread(self.proot.copy_path, source, destination)
        self.show_snack(
            f"copied {source} -> {destination}"
            if outcome.ok
            else self.proot.friendly_job_error(outcome)
        )

    async def sync_path(
        self, source: str, destination: str, checksum: bool = True, delete: bool = False
    ) -> None:
        source = source.strip()
        destination = destination.strip()
        if not source or not destination:
            self.show_snack("sync needs a source and a destination")
            return
        outcome = await asyncio.to_thread(
            self.proot.sync_path, source, destination, checksum, delete
        )
        self.show_snack(
            f"synced {source} -> {destination}"
            if outcome.ok
            else self.proot.friendly_job_error(outcome)
        )

    async def inspect_container(self, name: str) -> None:
        info = await asyncio.to_thread(self.proot.inspect_container, name)
        from core import tokens

        os_rel = info.get("os_release", {})
        pretty_name = os_rel.get("PRETTY_NAME") or os_rel.get("NAME") or name
        version_id = os_rel.get("VERSION_ID", "")
        cfg = info.get("config", {})
        entrypoint = cfg.get("Entrypoint") or "default"
        cmd = cfg.get("Cmd") or "default"
        workdir = cfg.get("WorkingDir") or "/"

        content = ft.Column(
            controls=[
                ft.Text(
                    f"OS: {pretty_name} {version_id}".strip(),
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                    color=theme.text(),
                ),
                ft.Text(
                    f"Origin: {info.get('image', 'local')} ({info.get('arch', 'unknown')})",
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                ),
                ft.Divider(),
                ft.Text(
                    f"WorkingDir: {workdir}",
                    size=tokens.FONT_SM,
                    color=theme.text(),
                ),
                ft.Text(
                    f"Entrypoint: {entrypoint}",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
                ft.Text(
                    f"Cmd: {cmd}",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
            ],
            spacing=tokens.SPACE_XS,
            tight=True,
        )

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Container: {name}",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=content,
                actions=[ft.TextButton("Close", on_click=lambda _e: self.page.pop_dialog())],
            )
        )


class SessionActions:
    async def list_sessions(self) -> None:
        rows = await asyncio.to_thread(self.proot.active_sessions)
        if not rows:
            self.show_snack("no running sessions")
            return
        from core import tokens

        def _close_dlg(_e=None):
            self.page.pop_dialog()

        def _kill(pid):
            _close_dlg()
            self.page.run_task(self.kill_session, str(pid))

        def _kill_all(_e):
            _close_dlg()
            self.page.run_task(self.kill_all_sessions)

        items = []
        for r in rows:
            pid_val = str(r.get("pid", ""))
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.primary()),
                    title=ft.Text(
                        f"{r.get('container')} (PID {r.get('pid')})",
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.W_600,
                    ),
                    subtitle=ft.Text(
                        f"user: {r.get('user')} · cmd: {r.get('command')}",
                        size=tokens.FONT_XS,
                    ),
                    trailing=ft.IconButton(
                        icon=ft.Icons.STOP_CIRCLE_ROUNDED,
                        icon_color=theme.warn(),
                        tooltip="Stop session",
                        on_click=lambda _e, p=pid_val: _kill(p),
                    ),
                )
            )

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Active Sessions",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=items,
                    spacing=tokens.SPACE_XS,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[
                    ft.TextButton("Stop All", on_click=_kill_all),
                    ft.TextButton("Close", on_click=_close_dlg),
                ],
            )
        )

    async def kill_all_sessions(self) -> None:
        outcome = await asyncio.to_thread(self.proot.kill_session, "", True)
        self.show_snack(
            "stopped all sessions" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def kill_session(self, pid: str) -> None:
        outcome = await asyncio.to_thread(self.proot.kill_session, str(pid))
        self.show_snack(
            f"stopped session {pid}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def open_session(self, container: str) -> None:
        state.session_error = ""
        try:
            await self.session_manager.open(container)
        except Exception as exc:
            state.session_error = f"could not open {container}: {_reason(exc)}"
            self.show_snack(state.session_error)
            logger.exception("Could not open shell for %s", container)
            raise
        state.active_session = container

    async def leave_session(self) -> None:
        state.active_session = None
        await self.ad_service.show_interstitial()

    async def close_session(self, container: str) -> None:
        await asyncio.to_thread(self.session_manager.close, container)
        if state.active_session == container:
            state.active_session = None
        await self.ad_service.show_interstitial()
