"""Per-container actions: rename, backup/restore, copy/sync, inspect, run."""

from __future__ import annotations

import asyncio

import flet as ft

from core import storage_paths, theme

from ._common import _COMPRESS_EXT


class ContainerActions:
    async def rename_container(self, orig: str, new: str) -> None:
        new = new.strip()
        if not new:
            self.show_snack("name must not be empty")
            return
        if "/" in new:
            self.show_snack("name must not contain '/'")
            return
        outcome = await asyncio.to_thread(self.proot.rename_container, orig, new)
        self.show_snack(
            f"renamed to {new}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )
        if outcome.ok:
            # The caps cache is keyed by name — move the entry to the new key.
            from controller_actions.display_actions import invalidate_display_support

            invalidate_display_support(orig)
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def backup_container(
        self, container: str, compression: str | None = None, name: str | None = None
    ) -> None:
        if self.file_picker is None:
            self.show_snack("file picker unavailable on this build")
            return
        # Stage the archive in app storage first, then hand the BYTES to the
        # picker: on mobile `save_file` without `src_bytes` raises ValueError
        # (there is no writable shared path to stream to), which made the
        # backup action die silently on the only platform that ships.
        # `name` is the user-chosen archive name — honored, not discarded.
        suffix = _COMPRESS_EXT.get(compression or "", ".tar.gz") if compression else ".tar.gz"
        stem = (name or "").strip() or container
        if stem.endswith(".tar") or stem.endswith(".tar.gz") or stem.endswith(suffix):
            stem = stem[: -len(suffix)] if stem.endswith(suffix) else stem.removesuffix(".tar")
        safe_stem = "".join(c for c in stem if c.isalnum() or c in "-_.").strip(".") or container
        staging = storage_paths.exports_root() / f"{safe_stem}{suffix}"

        def _stage() -> object:
            staging.parent.mkdir(parents=True, exist_ok=True)
            # A previous backup of the same name must not make this one fail
            # ("file exists" — upstream refuses to overwrite).
            staging.unlink(missing_ok=True)
            return self.proot.backup_container(container, str(staging), compression=compression)

        outcome = await asyncio.to_thread(_stage)
        if not outcome.ok:
            self.show_snack(self.proot.friendly_job_error(outcome))
            return
        target = await self.file_picker.save_file(
            dialog_title=f"Backup {container}",
            file_name=f"{safe_stem}{suffix}",
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

    async def copy_path(
        self, source: str, destination: str, move: bool = False, recursive: bool = True
    ) -> None:
        source = source.strip()
        destination = destination.strip()
        if not source or not destination:
            self.show_snack("copy needs a source and a destination")
            return
        outcome = await asyncio.to_thread(
            self.proot.copy_path, source, destination, move, recursive=recursive
        )
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
        env_list = cfg.get("Env") or []
        if isinstance(env_list, list):
            env_text = "\n".join(str(e) for e in env_list) or "(none)"
        else:
            env_text = "(none)"

        content = ft.Column(
            controls=[
                ft.Text(
                    f"OS: {pretty_name} {version_id}".strip(),
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_600,
                    color=theme.text(),
                ),
                ft.Text(
                    f"Origin: {info.get('image', 'local')} ({info.get('arch', 'unknown')})"
                    + (f" · ID {info.get('image_id', '')[:12]}" if info.get("image_id") else ""),
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
                ft.Divider(),
                ft.Text(
                    "Image Env:", size=tokens.FONT_XS, weight=ft.FontWeight.BOLD, color=theme.text()
                ),
                ft.Text(env_text, size=tokens.FONT_XS, color=theme.text_dim(), selectable=True),
                ft.Divider(),
                ft.Text(
                    "Guest session env also carries PD_CONTAINER, PD_IMAGE, PD_IMAGE_ID "
                    "and container=proot-distro (upstream identity vars).",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                    selectable=True,
                ),
            ],
            spacing=tokens.SPACE_XS,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
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
