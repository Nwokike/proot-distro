"""Start/stop/resume/share the display sessions."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.constants import PREF_DISPLAY_SETTINGS
from core.state import DEFAULT_DISPLAY_SETTINGS, state
from services import desk_service
from services.desk_service import script as desk_script

from ._common import _reason
from .display_common import _auto_geometry, _int_setting

logger = logging.getLogger(__name__)


class DisplaySessionMixin:
    async def open_display(self, container: str) -> None:
        """Card/tab entry point: ALWAYS opens the launch sheet. A running
        display is listed under Running on the tab (the user can resume it
        there); this entry point never silently resumes one — multi-display
        and kill reliability depend on the sheet being the only start path."""
        state.display_error = ""
        await self.probe_display(container)
        caps = self._display_caps(container)
        from screens.display_launcher import show_display_sheet

        show_display_sheet(self.page, self.methods, container, caps)

    async def start_display(
        self,
        container: str,
        app_command: str | None = None,
        display: int | None = None,
        options: dict | None = None,
    ) -> None:
        """Start one display session (key `container:display`). `app_command`
        is the command that runs on its own display (a desktop starter such as
        startxfce4 is just another command). `options` carries the advanced
        login options (user, work_dir, env, bind, shared_tmp, shared_home,
        isolated, fix_low_ports) — everything proot-distro's login supports, so
        a technical user has full control."""
        manager = self.desk_manager
        if any(
            s.status.value == "starting"
            for s in manager.running() + manager.for_container(container)
        ) or any(
            s.status is desk_service.DeskStatus.STARTING for s in manager.for_container(container)
        ):
            self.show_snack("a display is already starting. Wait a moment")
            return
        await self.ad_service.show_interstitial()
        settings = self._display_settings()
        tunnel_enabled = bool(settings.get("tunnel"))
        if tunnel_enabled and not await self._guest_has_ssh(container):
            self.show_snack(
                "the tunnel needs ssh in the container. Install openssh-client in it first"
            )
            tunnel_enabled = False
        state.display_error = ""
        state.display_status = "starting"
        state.display_status_text = f"starting the X11 display in {container}…"
        # Immediate, visible feedback wherever the user is (home, display, or
        # any tab) — the in-app snack, like the distro install flow.
        self.show_snack(state.display_status_text)
        # The microphone is OFF at start and never prompts here (owner ruling
        # 2026-11-17): the viewer toolbar's mic button is the only source of
        # truth and requests the Android grant itself the moment it is tapped.
        # Audio playback is unaffected by this choice.
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
                mic=False,  # always off at start; the toolbar owns the mic
                guest_notifications=bool(settings.get("forward_guest_notifications", True)),
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

                await prefs.set(PREF_DISPLAY_SETTINGS, json.dumps(self._display_settings()))
            except Exception as exc:
                logger.debug("display_settings persist failed: %s", exc)
        self._wakelock(True)
        await self._update_fgs()

    async def set_display_mic(self, key: str, enabled: bool) -> None:
        """Toggle the mic at runtime for a running display (owner 2026-11-16:
        the mic must not be always-on — the user controls it from the toolbar;
        owner 2026-11-17: this button is the ONLY place the Android grant is
        requested, and the reported state must be real).

        Turning ON requests RECORD_AUDIO first; the daemon only loads the mic
        module after the grant, and a denial leaves the mic off instead of
        claiming it is on."""
        manager = getattr(self, "desk_manager", None)
        if manager is None:
            return
        if enabled:
            granted = await self._ensure_mic_permission()
            if not granted:
                self.show_snack("microphone permission denied. Allow it to use the mic")
                return
            await manager.set_mic(key, True)
            session = manager.get(key)
            alive = manager.pulse_server_alive()
            if session is not None and session.mic and alive:
                self.show_snack("microphone on")
            else:
                # Honest: the grant is there but the daemon did not come back
                # with the mic module — do not claim success.
                self.show_snack("microphone could not start. Check the display logs")
            return
        await manager.set_mic(key, False)
        self.show_snack("microphone off")

    async def stop_display(self, key: str) -> None:
        await self.ad_service.show_interstitial()
        await self.desk_manager.stop(key)
        if state.active_display == key:
            state.active_display = None
            state.display_status = "idle"
            state.display_url = ""
            self._wakelock(False)
            self._lock_orientation(False)
            self._set_system_bars(hidden=False)
        await self._update_fgs()

    async def retry_display(self, key: str) -> None:
        """Retry a failed display with the SAME shape it had (command, login
        options, display number) — a bare start_display call would lose them."""
        session = self.desk_manager.get(key)
        if session is None:
            self.show_snack("that display is gone")
            return
        await self.start_display(
            session.container,
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
        self._set_system_bars(hidden=False)

    async def set_display_fullscreen(self, on: bool) -> None:
        state.display_fullscreen = bool(on)
        self._lock_orientation(bool(on))
        # Real fullscreen on Android: hide the system bars (page.window is
        # desktop-only). Best effort; harmless where unsupported.
        self._set_system_bars(hidden=bool(on))

    def _set_system_bars(self, *, hidden: bool) -> None:
        from core.android_ui import set_system_bars_hidden

        try:
            set_system_bars_hidden(hidden)
        except Exception as exc:
            logger.debug("system bar toggle failed: %s", exc)

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

        def _copy(text: str) -> None:
            if clipboard is not None:
                self.page.run_task(clipboard.set, text)

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
                        on_click=lambda _e, u=url: _copy(u),
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
                        on_click=lambda _e: _copy(session.code),
                    ),
                ],
                spacing=tokens.SPACE_XS,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        rows.append(
            ft.Text(
                "Any device opening a URL above must enter this access code on the "
                "display's sign-in page. localhost.run's free URLs rotate after a few hours.",
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
        )

        # The dialog is useful without a tunnel: the Local (and LAN) URL plus the
        # code are how a browser on the same phone or Wi-Fi opens the display
        # (device 2026-11-17). The system share sheet needs a public URL.
        actions: list[ft.Control] = []
        if session.tunnel_url and share is not None:
            actions.append(
                ft.TextButton(
                    "Share…",
                    on_click=lambda _e: (
                        self.page.pop_dialog(),
                        self.page.run_task(share.share_uri, session.tunnel_url),
                    ),
                )
            )
        else:
            rows.append(
                ft.Text(
                    "Turn on the public tunnel to get a shareable link.",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                )
            )
        actions.append(ft.TextButton("Close", on_click=lambda _e: self.page.pop_dialog()))
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Share display: {key}",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=[*rows],
                    tight=True,
                    spacing=tokens.SPACE_SM,
                    width=tokens.DIALOG_WIDTH,
                ),
                actions=actions,
            )
        )

    # ── settings ──────────────────────────────────────────────────────────────

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
