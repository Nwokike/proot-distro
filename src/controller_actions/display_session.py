"""Start/stop/resume/share the display sessions."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import DEFAULT_DISPLAY_SETTINGS, state
from services import desk_service
from services.desk_service import script as desk_script

from ._common import _reason
from .display_common import _auto_geometry, _int_setting

logger = logging.getLogger(__name__)


class DisplaySessionMixin:
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
        switches to single-app mode (bare Xvnc, no DE). `options` carries the
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
        await self.ad_service.show_interstitial()
        caps = self._display_caps(container)
        installed_desktops = caps.get("desktops") or {}
        env = desktop_env or next(
            (key for key, present in installed_desktops.items() if present),
            "xfce",
        )
        settings = self._display_settings()
        tunnel_enabled = bool(settings.get("tunnel"))
        if tunnel_enabled and not await self._guest_has_ssh(container):
            self.show_snack(
                "the tunnel needs ssh in the container — installing desktop support "
                "adds openssh-client"
            )
            tunnel_enabled = False
        state.display_error = ""
        state.display_status = "starting"
        state.display_status_text = f"starting the X11 display in {container}…"
        # Immediate, visible feedback wherever the user is (home, display, or
        # any tab) — the in-app snack, like the distro install flow.
        self.show_snack(state.display_status_text)
        # The mic grant is asked through the official recorder service right
        # before the PulseAudio daemon (which loads the mic module) starts —
        # AFTER the starting feedback, so the dialog never appears out of
        # nowhere. A denial degrades audio only.
        mic_allowed = True
        if settings.get("mic", True):
            mic_allowed = await self._ensure_mic_permission()
            if not mic_allowed:
                self.show_snack(
                    "microphone permission not granted — display audio is playback-only"
                )
        # Every value below is clamped/validated here, then threads straight
        # into the Xvnc argv / PulseAudio module lines (no dead knobs).
        depth = str(settings.get("depth", "24"))
        if depth not in ("16", "24", "32"):
            depth = "24"
        shared_policy = str(settings.get("shared_policy", "always"))
        if shared_policy not in ("auto", "always", "never"):
            shared_policy = "always"
        resize_mode = str(settings.get("resize", "remote"))
        if resize_mode not in ("remote", "scale", "off"):
            resize_mode = "remote"
        frame_rate = _int_setting(settings.get("fps", 30), 30, 1, 60)
        disconnect_timeout = _int_setting(settings.get("disconnect_timeout", 0), 0, 0, 86400)
        audio_latency = _int_setting(settings.get("audio_latency_ms", 0), 0, 0, 2000)
        audio_pm = _int_setting(settings.get("audio_pm", 2), 2, 0, 3)
        try:
            session = await manager.start(
                container,
                display=display,
                desktop_env=env,
                app_command=app_command,
                options=options,
                frame_rate=frame_rate,
                quality=_int_setting(settings.get("quality", 70), 70, 0, 95),
                compression=_int_setting(settings.get("compression", 2), 2, 0, 9),
                geometry=self._resolve_geometry(settings),
                depth=depth,
                shared_policy=shared_policy,
                resize_mode=resize_mode,
                clipboard=bool(settings.get("clipboard", True)),
                localhost_only=bool(settings.get("restrict_local", False)),
                compare_fb=_int_setting(settings.get("compare_fb", 2), 2, 0, 2),
                dpi=_int_setting(settings.get("dpi", 0), 0, 0, 480),
                idle_timeout=_int_setting(settings.get("idle_timeout", 0), 0, 0, 86400),
                max_connection_time=_int_setting(
                    settings.get("max_connection_time", 0), 0, 0, 86400
                ),
                view_only=bool(settings.get("view_only", False)),
                max_cut_text=_int_setting(settings.get("max_cut_text", 0), 0, 0, 16 * 1024 * 1024),
                disconnect_clients=bool(settings.get("disconnect_clients", False)),
                audio_rate=_int_setting(settings.get("audio_rate", 0), 0, 0, 192000),
                audio_no_close_hack=bool(settings.get("audio_no_close_hack", False)),
                mic_rate=_int_setting(settings.get("mic_rate", 0), 0, 0, 192000),
                mic_format=str(settings.get("mic_format", "") or ""),
                mic_channels=_int_setting(settings.get("mic_channels", 0), 0, 0, 8),
                resample_method=str(settings.get("resample_method", "") or ""),
                viewer_bell=bool(settings.get("viewer_bell", True)),
                show_dot=bool(settings.get("show_dot", False)),
                viewer_logging=str(settings.get("viewer_logging", "warn") or "warn"),
                disconnect_timeout=disconnect_timeout,
                mic=bool(settings.get("mic", True)) and mic_allowed,
                audio_latency_ms=audio_latency,
                audio_pm=audio_pm,
                # LAN sharing maps to the server's bind host (S104 is the point).
                host=(
                    "0.0.0.0" if settings["lan"] else "127.0.0.1"  # noqa: S104 - LAN feature
                ),
                tunnel=tunnel_enabled,
            )
        except Exception as exc:
            if state.display_status == "starting":
                state.display_status = "error"
                state.display_error = _reason(exc)
                self.show_snack(f"display failed: {state.display_error}")
            from core import shared_services

            self.page.run_task(
                shared_services.announce, f"display failed in {container}", self.page
            )
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
        await self.ad_service.show_interstitial()
        await self.desk_manager.stop(key)
        if state.active_display == key:
            state.active_display = None
            state.display_status = "idle"
            state.display_url = ""
            self._wakelock(False)
            self._lock_orientation(False)
        await self._update_fgs()

    async def retry_display(self, key: str) -> None:
        """Retry a failed display with the SAME shape it had (mode, desktop
        env, login options, display number) — a bare start_display call
        would turn a failed single-app session into a desktop."""
        session = self.desk_manager.get(key)
        if session is None:
            self.show_snack("that display is gone")
            return
        await self.start_display(
            session.container,
            desktop_env=session.desktop_env,
            app_command=session.app_command or None,
            display=session.display,
            options=dict(getattr(session, "login_options", None) or {}),
        )

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
        # The ONE app-wide instances (shared_services) — never a fresh
        # Service per click (each construction registers another instance).
        clipboard = getattr(self.page, "clipboard", None)
        share = getattr(self.page, "share", None)
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
                # `/` gates the access code, so the shared URL must carry it —
                # the whole point of the Share dialog is a copyable URL.
                rows.append(_url_row("LAN", f"http://{ip}:{session.port}/?code={session.code}"))
        if session.tunnel_url:
            url = session.tunnel_url
            if "?" not in url:
                url = f"{url}?code={session.code}"
            rows.append(_url_row("Tunnel", url))
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

        share_url = session.tunnel_url
        if not share_url:
            self.page.pop_dialog()
            self.show_snack("no public URL yet — turn on the tunnel for this display to share it")
            return
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

    @staticmethod
    async def cancel_install_display(self) -> None:
        """Stop the running desktop-install capture (the card/cell Stop)."""
        session = getattr(self, "_install_session", None)
        if session is None:
            self.show_snack("no install is running")
            return
        session.stop()
        self.show_snack("install stopped")

    def _display_settings(self) -> dict:
        return {**DEFAULT_DISPLAY_SETTINGS, **(state.display_settings or {})}

    def _resolve_geometry(self, settings: dict) -> str:
        preset = str(settings.get("geometry", "auto"))
        if preset != "auto" and desk_script.is_valid_geometry(preset):
            return preset
        return _auto_geometry(self.page, str(settings.get("orientation", "landscape")))

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
