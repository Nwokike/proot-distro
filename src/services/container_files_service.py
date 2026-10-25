"""Container Files Service — safe, rootfs-jailed filesystem operations.

Implements directory listing, breadcrumbs, file reading, uploads, downloads,
folder zipping, folder creation, and deletions for container filesystems.
Confined to `<storage_root>/containers/<container>/rootfs/`.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import posixpath
import shutil
import zipfile
from pathlib import Path

from core import storage_paths

logger = logging.getLogger(__name__)

_MAX_TEXT_BYTES = 128 * 1024  # 128 KB text preview cap


def resolve_guest_path(container: str, guest_path: str = "/") -> tuple[Path, Path]:
    """Resolve guest POSIX path to host Path, preventing rootfs breakout.

    Returns (rootfs_path, host_target_path).
    Raises PermissionError if path resolves outside container rootfs.
    """
    rootfs = (storage_paths.containers_dir() / container / "rootfs").resolve()
    norm = posixpath.normpath(guest_path or "/")
    rel = norm.lstrip("/")
    host_target = (rootfs / rel).resolve()

    if not host_target.is_relative_to(rootfs):
        raise PermissionError(f"Security violation: path escapes container rootfs: {guest_path}")
    return rootfs, host_target


def list_container_dir(container: str, guest_path: str = "/") -> list[dict]:
    """List directory contents inside container rootfs.

    Returns list of dicts: name, path, is_dir, type, size, modified, mime_type.
    Directories are sorted first, then files alphabetically.
    """
    _rootfs, host_dir = resolve_guest_path(container, guest_path)
    if not host_dir.exists():
        raise FileNotFoundError(f"Path does not exist: {guest_path}")
    if not host_dir.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {guest_path}")

    norm_guest = posixpath.normpath(guest_path or "/")
    results: list[dict] = []

    with os.scandir(host_dir) as it:
        for entry in it:
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
                is_symlink = entry.is_symlink()
                st = entry.stat(follow_symlinks=False)

                entry_guest_path = posixpath.normpath(posixpath.join(norm_guest, entry.name))
                mime, _ = mimetypes.guess_type(entry.name)

                results.append(
                    {
                        "name": entry.name,
                        "path": entry_guest_path,
                        "is_dir": is_dir,
                        "type": "directory" if is_dir else "file",
                        "is_symlink": is_symlink,
                        "size": 0 if is_dir else st.st_size,
                        "modified": st.st_mtime,
                        "mime_type": mime
                        or ("inode/directory" if is_dir else "application/octet-stream"),
                    }
                )
            except OSError:
                continue

    results.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return results


def read_file_preview(container: str, guest_path: str) -> dict:
    """Read a preview of a file (text snippet or Base64 image)."""
    _, host_path = resolve_guest_path(container, guest_path)
    if not host_path.is_file():
        raise ValueError("Cannot read non-file")

    mime, _ = mimetypes.guess_type(host_path.name)
    mime = mime or "application/octet-stream"

    if mime.startswith("image/"):
        with open(host_path, "rb") as f:
            raw = f.read(10 * 1024 * 1024)
        return {
            "type": "image",
            "mime": mime,
            "base64": base64.b64encode(raw).decode("ascii"),
        }

    with open(host_path, "rb") as f:
        chunk = f.read(_MAX_TEXT_BYTES + 1)
    is_truncated = len(chunk) > _MAX_TEXT_BYTES
    content = chunk[:_MAX_TEXT_BYTES].decode("utf-8", errors="replace")
    if is_truncated:
        content += "\n... [Preview truncated: file exceeds 128 KB] ..."

    return {
        "type": "text",
        "mime": mime,
        "content": content,
    }


def create_folder(container: str, guest_dir: str, folder_name: str) -> None:
    """Create a new directory inside container rootfs."""
    clean = folder_name.strip().strip("/")
    if not clean or "/" in clean or "\\" in clean:
        raise ValueError("Invalid directory name")
    new_guest_path = posixpath.normpath(posixpath.join(guest_dir, clean))
    _, host_path = resolve_guest_path(container, new_guest_path)
    os.makedirs(host_path, exist_ok=False)


def delete_items(container: str, guest_paths: list[str]) -> list[str]:
    """Delete files or folders from container rootfs. Returns list of errors if any."""
    errors: list[str] = []
    for g_path in guest_paths:
        try:
            _, host_path = resolve_guest_path(container, g_path)
            if host_path.is_symlink() or host_path.is_file():
                os.unlink(host_path)
            elif host_path.is_dir():
                shutil.rmtree(host_path)
        except Exception as ex:
            errors.append(f"{posixpath.basename(g_path)}: {ex}")
    return errors


def zip_folder(container: str, guest_dir_path: str, dest_zip_path: str) -> None:
    """Archive a directory inside the container into a local zip file."""
    _, host_dir = resolve_guest_path(container, guest_dir_path)
    os.makedirs(os.path.dirname(dest_zip_path), exist_ok=True)

    with zipfile.ZipFile(dest_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(host_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, host_dir)
                zf.write(full_path, arcname=rel_path)


def write_file_bytes(container: str, guest_dir: str, filename: str, data: bytes) -> str:
    """Write binary data to a file inside the container."""
    _, host_dir = resolve_guest_path(container, guest_dir)
    target = host_dir / filename
    target.write_bytes(data)
    return str(target)


def copy_local_file_in(container: str, guest_dir: str, local_src_path: str) -> str:
    """Copy a host file into the container."""
    _, host_dir = resolve_guest_path(container, guest_dir)
    src = Path(local_src_path)
    target = host_dir / src.name
    shutil.copy2(src, target)
    return str(target)


def copy_container_file_out(container: str, guest_file_path: str, local_dest_path: str) -> None:
    """Copy a file out of the container to local host storage."""
    _, host_path = resolve_guest_path(container, guest_file_path)
    os.makedirs(os.path.dirname(local_dest_path), exist_ok=True)
    shutil.copy2(host_path, local_dest_path)
