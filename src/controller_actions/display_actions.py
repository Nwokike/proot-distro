"""Display (X11) session actions: probe, start/stop, provision, view routing.

The DeskManager (desk_service) owns the guest processes — one per session key
`container:display`, so a container can run several displays at once (a desktop
on :0 plus single apps on :1, :2…). This mixin owns the UI state and the FGS
ref-count shared with the terminal actions. The wrap is complete: fps/quality/
geometry are upstream server params, `lan` maps to the upstream host=0.0.0.0
binding, `tunnel` runs upstream's LocalhostRunTunnel, and fullscreen locks
orientation + keeps the screen awake via the ONE shared Wakelock service and
flet's `set_allowed_device_orientations` (Flet 1.1).
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme, tokens
from core.state import DEFAULT_DISPLAY_SETTINGS, state
from services import desk_service, proot_service
from services.desk_service import script as desk_script

from ._common import _reason

logger = logging.getLogger(__name__)

# Xvfb screen for "auto" geometry: long side 1280 keeps JPEG capture + WS
# streaming sane on phones; the viewer letterboxes any aspect anyway, and a
# preset/custom resolution bypasses this.
_AUTO_GEOMETRY_LONG_SIDE = 1280

# In-flight probe dedup (error results are never cached — see probe_display).
_probing: set[str] = set()


def _auto_geometry(page, orientation: str = "landscape") -> str:
    width = max(1, int(getattr(page, "width", 0) or 0))
    height = max(1, int(getattr(page, "height", 0) or 0))
    # The screen must match the LOCKED orientation, not the (portrait) page the
    # start sheet happened to render in — otherwise fullscreen shows a portrait
    # desktop letterboxed inside the landscape viewer.
    if (orientation == "landscape" and height > width) or (
        orientation == "portrait" and width > height
    ):
        width, height = height, width
    long_side = max(width, height)
    scale = _AUTO_GEOMETRY_LONG_SIDE / long_side
    even_w = max(2, round(width * scale / 2) * 2)
    even_h = max(2, round(height * scale / 2) * 2)
    return f"{even_w}x{even_h}"


def invalidate_display_support(container: str) -> None:
    """Drop the cached capability probe — call on remove/reset/rename."""
    if state.display_support and container in state.display_support:
        state.display_support = {k: v for k, v in state.display_support.items() if k != container}


class DisplayActions:
    # ── probe ─────────────────────────────────────────────────────────────────

    async def probe_display(self, container: str) -> None:
        """Cache the container's rootfs capability probe in state.display_support.
        Failures are NOT cached — the next mount re-probes (a transient failure
        must not pin an error until app restart). In-flight probes dedup via a
        set so a render loop never spawns parallel proot commands."""
        if state.display_support is None:
            state.display_support = {}
        cached = state.display_support.get(container)
        if cached is not None and "error" not in cached:
            return
        if container in _probing:
            return
        _probing.add(container)
        try:
            caps = await asyncio.to_thread(proot_service.guest_capabilities, container)
        except Exception as exc:
            logger.warning("display probe failed for %s: %s", container, exc)
            return  # not cached — retried next mount
        finally:
            _probing.discard(container)
        # REASSIGN: nested dict-item mutation does not notify the observable,
        # so card labels ("Open display"/"Install display support") never flipped.
        state.display_support = {**(state.display_support or {}), container: caps}

    def _display_caps(self, container: str) -> dict:
        return (state.display_support or {}).get(container) or {}

    def _display_settings(self) -> dict:
        return {**DEFAULT_DISPLAY_SETTINGS, **(state.display_settings or {})}

    def _resolve_geometry(self, settings: dict) -> str:
        preset = str(settings.get("geometry", "auto"))
        if preset != "auto" and desk_script.is_valid_geometry(preset):
            return preset
        return _auto_geometry(self.page, str(settings.get("orientation", "landscape")))

    def _lock_orientation(self, on: bool) -> None:
        """Fullscreen → orientation lock per the setting (landscape default,
        portrait optional), exit → system default. Android 16 devices ≥600dp
        ignore the lock — documented upstream."""
        from flet import DeviceOrientation

        orientations: list = []
        if on:
            which = self._display_settings().get("orientation", "landscape")
            if which == "landscape":
                orientations = [DeviceOrientation.LANDSCAPE_LEFT, DeviceOrientation.LANDSCAPE_RIGHT]
            elif which == "portrait":
                orientations = [DeviceOrientation.PORTRAIT_UP]
        try:
            self.page.run_task(self.page.set_allowed_device_orientations, orientations)
        except Exception as exc:
            logger.debug("orientation lock failed: %s", exc)

    def _wakelock(self, on: bool) -> None:
        """Keep the screen awake while a display is being viewed/mirrored.
        Uses the ONE app-wide Wakelock service mounted by shared_services."""
        service = getattr(self.page, "wakelock", None)
        if service is None:
            return
        try:
            self.page.run_task(service.enable if on else service.disable)
        except Exception as exc:
            logger.debug("wakelock toggle failed: %s", exc)

    # ── routing ───────────────────────────────────────────────────────────────

    async def open_display(self, container: str) -> None:
        """Card/tab entry point: probe, then resume a running display — or start
        the installed desktop — or open the launcher sheet (app-first, with the
        desktop install below it) when no desktop is installed yet."""
        state.display_error = ""
        await self.probe_display(container)
        caps = self._display_caps(container)
        running = [
            s for s in self.desk_manager.for_container(container) if s.status.value == "running"
        ]
        if running:
            # Prefer the desktop session: a container can also host a running
            # single-app display, and "Open desktop" must not resume that.
            desktop = next((s for s in running if s.mode == "desktop"), None)
            state.active_display = (desktop or running[0]).key
            self._wakelock(True)
            return
        if any((caps.get("desktops") or {}).values()):
            await self.start_display(container)
        else:
            from screens.display_launcher import show_display_sheet

            show_display_sheet(self.page, self.methods, container, caps)

    async def start_display(
        self,
        container: str,
        desktop_env: str | None = None,
        app_command: str | None = None,
        display: int | None = None,
        options: dict | None = None,
    ) -> None:
        """Start one display session (key `container:display`). `app_command`
        switches to single-app mode (bare Xvfb, no DE). `options` carries the
        advanced login options (user, work_dir, env, bind, shared_tmp,
        shared_home, isolated, fix_low_ports) — everything proot-distro's
        login supports, so a technical user has full control."""
        manager = self.desk_manager
        if any(
            s.status.value == "starting"
            for s in manager.running() + manager.for_container(container)
        ) or any(
            s.status is desk_service.DeskStatus.STARTING for s in manager.for_container(container)
        ):
            self.show_snack("a display is already starting — wait a moment")
            return
        caps = self._display_caps(container)
        installed_desktops = caps.get("desktops") or {}
        env = desktop_env or next(
            (key for key, present in installed_desktops.items() if present),
            "xfce",
        )
        settings = self._display_settings()
        state.display_error = ""
        state.display_status = "starting"
        state.display_status_text = f"starting the X11 display in {container}…"
        state.display_logs = []
        # Immediate, visible feedback wherever the user is (home, display, or
        # any tab) — the in-app snack, like the distro install flow.
        self.show_snack(state.display_status_text)
        try:
            session = await manager.start(
                container,
                display=display,
                desktop_env=env,
                app_command=app_command,
                options=options,
                fps=float(settings["fps"]),
                quality=int(settings["quality"]),
                compression=int(settings.get("compression", 2)),
                geometry=self._resolve_geometry(settings),
                # LAN sharing maps to the server's bind host (S104 is the point).
                host=(
                    "0.0.0.0" if settings["lan"] else "127.0.0.1"  # noqa: S104 - LAN feature
                ),
                tunnel=bool(settings["tunnel"]),
            )
        except Exception as exc:
            if state.display_status == "starting":
                state.display_status = "error"
                state.display_error = _reason(exc)
                self.show_snack(f"display failed: {state.display_error}")
            logger.exception("display start failed for %s", container)
            return
        state.active_display = session.key
        state.display_status = "running"
        state.display_status_text = f"X11 on :{session.display} ({session.mode})"
        state.display_url = session.url
        state.display_error = ""
        # Persist the settings that produced this session (prefs service).
        prefs = getattr(self, "prefs", None)
        if prefs is not None:
            try:
                import json

                await prefs.set("display_settings", json.dumps(self._display_settings()))
            except Exception as exc:
                logger.debug("display_settings persist failed: %s", exc)
        self._wakelock(True)
        await self._update_fgs()

    async def stop_display(self, key: str) -> None:
        await self.desk_manager.stop(key)
        if state.active_display == key:
            state.active_display = None
            state.display_status = "idle"
            state.display_url = ""
            self._wakelock(False)
            self._lock_orientation(False)
        await self._update_fgs()

    async def resume_display(self, key: str) -> None:
        """Re-enter a running display (Running-row Open / card tap) — reacquire
        the wakelock exactly like start_display does, which leave_display
        released when the user navigated away."""
        session = self.desk_manager.get(key)
        if session is None or session.status is not desk_service.DeskStatus.RUNNING:
            self.show_snack("that display is not running")
            return
        state.active_display = key
        self._wakelock(True)

    async def cancel_install_display(self) -> None:
        """Stop the running desktop-install capture (the card/cell Stop)."""
        session = getattr(self, "_install_session", None)
        if session is None:
            self.show_snack("no install is running")
            return
        session.stop()
        self.show_snack("install stopped")

    async def leave_display(self) -> None:
        """Back from the display screen; the session keeps running in the background."""
        state.active_display = None
        state.display_fullscreen = False
        self._lock_orientation(False)
        self._wakelock(False)

    async def set_display_fullscreen(self, on: bool) -> None:
        state.display_fullscreen = bool(on)
        self._lock_orientation(bool(on))

    # ── sharing (LAN + tunnel + code) ─────────────────────────────────────────

    async def share_display(self, key: str) -> None:
        """Local / LAN / tunnel URLs + the access code for one session, each
        copyable, with a system share sheet. Clipboard/Share are the shared
        page services mounted by shared_services."""
        session = self.desk_manager.get(key)
        if session is None or not session.url:
            self.show_snack("the display is not running")
            return
        clipboard = getattr(self.page, "clipboard", None) or ft.Clipboard()
        share = getattr(self.page, "share", None) or ft.Share()
        rows: list[ft.Control] = []

        def _url_row(label: str, url: str) -> ft.Control:
            return ft.Row(
                controls=[
                    ft.Text(label, size=tokens.FONT_SM, color=theme.text_dim(), width=80),
                    ft.Text(
                        url,
                        size=tokens.FONT_XS,
                        font_family=tokens.MONO_FONT,
                        color=theme.text(),
                        expand=True,
                        selectable=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.COPY_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Copy URL",
                        on_click=lambda _e: self.page.run_task(clipboard.set, url),
                    ),
                ],
                spacing=tokens.SPACE_XS,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        rows.append(_url_row("Local", session.url))
        if session.host == "0.0.0.0":  # noqa: S104 - LAN mode flag, no bind here
            from services.desk_service.manager import _local_ip

            ip = _local_ip()
            if ip:
                rows.append(_url_row("LAN", f"http://{ip}:{session.port}/"))
        if session.tunnel_url:
            rows.append(_url_row("Tunnel", session.tunnel_url))
        elif session.tunnel:
            rows.append(
                ft.Text(
                    "the tunnel is still negotiating its URL… (it appears here and "
                    "in the guest logs when ssh answers)",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                )
            )
        rows.append(
            ft.Row(
                controls=[
                    ft.Text("Code", size=tokens.FONT_SM, color=theme.text_dim(), width=80),
                    ft.Text(
                        session.code,
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.BOLD,
                        font_family=tokens.MONO_FONT,
                        color=theme.primary(),
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.COPY_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Copy access code",
                        on_click=lambda _e: self.page.run_task(clipboard.set, session.code),
                    ),
                ],
                spacing=tokens.SPACE_XS,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        rows.append(
            ft.Text(
                "Any device opening a URL above must enter this access code — "
                "localhost.run's free URLs rotate after a few hours.",
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
        )

        share_url = session.tunnel_url or session.url
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Share display — {key}",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=[*rows],
                    tight=True,
                    spacing=tokens.SPACE_SM,
                    width=tokens.DIALOG_WIDTH,
                ),
                actions=[
                    ft.TextButton(
                        "Share…",
                        on_click=lambda _e: (
                            self.page.pop_dialog(),
                            self.page.run_task(share.share_uri, share_url),
                        ),
                    ),
                    ft.TextButton("Close", on_click=lambda _e: self.page.pop_dialog()),
                ],
            )
        )

    # ── provisioning ──────────────────────────────────────────────────────────

    async def _notify_install(self, title: str, body: str) -> None:
        """Simple local notification for desktop-install start/finish/fail
        (owner: just a simple notification, no complications). Reuses the id
        so the finish message replaces the ongoing one."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        try:
            await self._ensure_notification_permission()
            await notifications.show(id=2100, title=title, body=body)
        except Exception as exc:
            logger.debug("install notification failed: %s", exc)

    async def install_display_support(
        self, container: str, desktop_env: str = "xfce", script_text: str | None = None
    ) -> None:
        """Install desktop support, streaming live into TWO surfaces — the
        notebook-style command cell on the launcher sheet
        (`page._display_install_cell`) and the reactive progress card on the
        Display tab (`state.display_progress`, the CollabShell NotebookCell
        mechanism: a small observable model passed as the component argument).

        `script_text` (the possibly-EDITED cell source) runs verbatim via
        `login -- /bin/sh -lc <script>` with NO timeout; without it the canned
        per-distro script runs."""
        from core.state import display_progress

        state.display_installing = container
        state.display_install_logs = []
        state.display_error = ""
        display_progress.clear(container)
        display_progress.set_running(True)
        self.show_snack(f"installing desktop in {container}…")
        await self._notify_install(
            "Installing desktop", f"{container} — installing desktop support…"
        )
        cell = getattr(self.page, "_display_install_cell", None)
        if cell is not None:
            cell.set_running(True)
            cell.clear_output()
        await self.probe_display(container)
        caps = self._display_caps(container)

        def _on_chunk(data: bytes) -> None:
            text = data.decode("utf-8", "replace")
            if not text:
                return

            async def _apply(t: str = text) -> None:
                # Runs inside page.run_task: run_task sets ft.context's page
                # var in the calling thread and the loop task inherits that
                # context, so the observable notify schedules the card update.
                state.display_install_logs = [*state.display_install_logs, t]
                display_progress.append(t)
                if cell is not None:
                    cell.append_output(t)

            self.page.run_task(_apply)

        try:
            if script_text:
                from services import session_service

                result = await asyncio.to_thread(
                    session_service.command_capture,
                    container,
                    ["/bin/sh", "-lc", script_text],
                    None,
                    None,  # timeout=None — an install must never be killed
                    on_chunk=_on_chunk,
                    # The Stop button kills this PTY session (edit honoree runs verbatim).
                    on_start=lambda s: setattr(self, "_install_session", s),
                )
            else:
                result = await desk_service.install(
                    container, caps, desktop_env, on_chunk=_on_chunk
                )
        except Exception as exc:
            self._install_session = None
            state.display_error = _reason(exc)
            state.display_installing = None
            display_progress.set_running(False)
            display_progress.append(f"install failed: {_reason(exc)}")
            await self._notify_install("Install failed", f"{container}: {_reason(exc)}")
            if cell is not None:
                cell.set_running(False)
                cell.append_output(f"install failed: {_reason(exc)}")
            logger.exception("display install failed for %s", container)
            return
        self._install_session = None
        state.display_installing = None
        display_progress.finish(bool(result.get("ok")))
        if cell is not None:
            cell.set_running(False)
        if result.get("ok"):
            self.show_snack(f"desktop installed in {container}")
            await self._notify_install(
                "Desktop installed", f"{container} — open it from the Display tab"
            )
            # Re-probe without the cache guard: the container changed on disk.
            try:
                caps = await asyncio.to_thread(proot_service.guest_capabilities, container)
                # REASSIGN the whole dict: nested item assignment on the
                # observable does not notify, so card labels would keep saying
                # "Install display support" after it is installed.
                state.display_support = {**(state.display_support or {}), container: caps}
            except Exception as exc:
                logger.warning("display re-probe failed for %s: %s", container, exc)
            # Repaint the launcher sheet (if still open) into its ready state.
            try:
                from screens.display_launcher import rebuild_display_sheet

                rebuild_display_sheet(self.page, container)
            except Exception:
                pass
        else:
            state.display_error = f"install exited {result.get('returncode')} — see the log tail"
            self.show_snack(f"display install failed in {container}")
            if cell is not None:
                cell.append_output(state.display_error)

    # ── diagnostics ───────────────────────────────────────────────────────────

    async def show_display_logs(self, key: str) -> None:
        session = self.desk_manager.get(key)
        lines = list(session.log_tail) if session else list(state.display_logs or [])
        tail = "\n".join(lines[-200:]) or "(no logs yet)"
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Display logs — {key}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=ft.Container(
                    content=ft.Text(
                        tail,
                        font_family=tokens.MONO_FONT,
                        size=tokens.FONT_XXS,
                        color=theme.text_dim(),
                        selectable=True,
                    ),
                    width=tokens.DIALOG_WIDTH_LG,
                    height=320,
                ),
                actions=[ft.TextButton("Close", on_click=lambda _e: self.page.pop_dialog())],
            )
        )
