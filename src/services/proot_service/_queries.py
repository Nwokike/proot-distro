"""Read-only queries: containers, cache, storage, inspect, sessions."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core import storage_paths

from ._core import _imp
from ._guard import ProotUnavailable

logger = logging.getLogger(__name__)


def _scan_tree(path: Path) -> tuple[int, int]:
    """(bytes, file count) in ONE scandir walk — os.walk + rglob walked twice."""
    total = count = 0
    stack = [Path(path)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                            count += 1
                    except OSError as exc:
                        logger.debug("size walk skipped %s: %r", entry.path, exc)
        except OSError as exc:
            logger.debug("size walk skipped %s: %r", current, exc)
    return total, count


def _tree_bytes(path: Path) -> int:
    return _scan_tree(path)[0]


def _container_rows() -> list[dict]:
    """Installed containers via upstream's paths + a host-side size walk."""
    paths = _imp("proot_distro.paths")

    containers_dir = storage_paths.containers_dir()
    rows: list[dict] = []
    for name in sorted(paths.installed_container_names()):
        image, arch = "", ""
        try:
            image, arch = paths.container_image_origin(name)
        except Exception as exc:
            logger.debug("image origin unavailable for %s: %r", name, exc)
        rows.append(
            {
                "name": name,
                "image": image,
                "arch": arch,
                "size_bytes": _tree_bytes(containers_dir / name),
            }
        )
    return rows


def list_containers() -> list[dict]:
    """Installed containers. Raises with the real reason — the controller
    surfaces it in the UI instead of showing a silently empty list."""
    return _container_rows()


def container_rootfs(container: str) -> Path:
    """Host-side rootfs path of an installed container."""
    return storage_paths.containers_dir() / container / "rootfs"


def container_users(container: str) -> list[dict]:
    """Accounts from the container's own /etc/passwd.

    This is the SAME file upstream's `--user` resolves against, so the shell
    options can only offer users that actually exist (device 2026-11-15:
    a free-text `-u kiri` died with "no user 'kiri' defined in /etc/passwd")."""
    passwd = container_rootfs(container) / "etc" / "passwd"
    users: list[dict] = []
    try:
        text = passwd.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("passwd unreadable for %s: %r", container, exc)
        return users
    for line in text.splitlines():
        fields = line.split(":")
        if len(fields) < 7 or not fields[0]:
            continue
        users.append(
            {
                "name": fields[0],
                "uid": fields[2],
                "gid": fields[3],
                "home": fields[5] or "/",
                "shell": fields[6] or "/bin/sh",
            }
        )
    return users


def guest_desktop_apps(container: str) -> list[dict]:
    """GUI applications registered in the container, read from its .desktop
    files on the host filesystem (no proot spawn).

    This is how Linux itself lists applications: `/usr/share/applications`
    plus `/usr/local/share/applications`. Only `Type=Application` entries with
    an `Exec=` are kept, hidden ones (`NoDisplay=true`) are skipped, and field
    codes such as `%U` or `%F` are stripped."""
    apps: dict[str, str] = {}
    for base in ("usr/share/applications", "usr/local/share/applications"):
        folder = container_rootfs(container) / base
        if not folder.is_dir():
            continue
        for entry in sorted(folder.glob("*.desktop")):
            try:
                text = entry.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fields: dict[str, str] = {}
            in_main = False
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("["):
                    in_main = stripped == "[Desktop Entry]"
                    continue
                if not in_main or "=" not in stripped:
                    continue
                key, _, value = stripped.partition("=")
                fields.setdefault(key.strip(), value.strip())
            if fields.get("Type") != "Application":
                continue
            if fields.get("NoDisplay", "").lower() == "true":
                continue
            exec_line = fields.get("Exec", "").strip()
            label = fields.get("Name", "").strip()
            if not exec_line or not label:
                continue
            cmd = " ".join(token for token in exec_line.split() if not token.startswith("%"))
            if not cmd:
                continue
            apps.setdefault(label, cmd)
    return [{"label": label, "cmd": cmd} for label, cmd in sorted(apps.items())]


def guest_path_exists(container: str, guest_path: str) -> bool:
    """True when an absolute guest path exists inside the container rootfs."""
    import posixpath

    if not guest_path.startswith("/"):
        return False
    normal = posixpath.normpath(guest_path)
    if normal.startswith(".."):
        return False
    return (container_rootfs(container) / normal.lstrip("/")).exists()


def search_images(query: str, limit: int = 25) -> list[dict]:
    """Docker Hub search — upstream's own normalized hits (plain dicts)."""
    docker_search = _imp("proot_distro.helpers.docker.search")

    results, _total = docker_search.search_images(query, limit)
    return [r for r in results if isinstance(r, dict)]


def cached_images() -> list[dict]:
    """Cached OCI images (host-side sizes) for the storage screen.

    Upstream's record (helpers/docker/cache.py) already carries the computed
    blob total in `size` — the old `full_path`/`id` keys do not exist in the
    record, and `path` is the manifest-cache JSON file, so walking it made
    every size read 0 (device audit 2026-11-13)."""
    cache = _imp("proot_distro.helpers.docker.cache")

    rows = []
    for image in cache.iter_cached_images():
        size = image.get("size") or 0
        if not size:
            try:
                path = image.get("path")
                if path and Path(path).is_dir():
                    size = _tree_bytes(Path(path))
            except Exception as exc:
                logger.debug("cached image size unavailable: %r", exc)
        rows.append(
            {
                "identifier": image.get("image_ref")
                or image.get("image_id")
                or image.get("key")
                or "?",
                "arch": image.get("arch", ""),
                "size_bytes": size,
            }
        )
    return rows


def storage_bytes() -> int:
    """Total footprint of containers AND the OCI cache — the OCI layers live in
    the CACHE root, so counting only the data root understated it badly (the
    UI label says "containers and cache")."""
    total = 0
    for root in (storage_paths.xdg_data_home(), storage_paths.xdg_cache_home()):
        try:
            total += _tree_bytes(root / "proot-distro")
        except OSError as exc:
            raise ProotUnavailable(f"storage size unavailable: {exc}") from exc
    return total


def storage_split() -> tuple[int, int]:
    """(data root bytes, cache root bytes) — the same two walks as
    storage_bytes, split so Settings can say where the space actually is."""
    try:
        data = _tree_bytes(storage_paths.xdg_data_home() / "proot-distro")
        cache = _tree_bytes(storage_paths.xdg_cache_home() / "proot-distro")
    except OSError as exc:
        raise ProotUnavailable(f"storage size unavailable: {exc}") from exc
    return data, cache


def _area(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "bytes": 0, "count": 0}
    total, count = _scan_tree(p)
    return {"path": str(p), "bytes": total, "count": count}


def storage_detail() -> dict:
    """Every proot-distro area under the three Flet storage roots, with sizes.

    Layout (upstream appends `proot-distro` to the XDG roots; D-024 maps those
    onto FLET_APP_STORAGE_DATA/CACHE): data → containers/, locks/, sessions/;
    cache → oci_layers/, oci_manifests/, build_cache_index.json; temp → exports/.
    """
    data = storage_paths.xdg_data_home() / "proot-distro"
    cache = storage_paths.xdg_cache_home() / "proot-distro"
    temp = storage_paths.temp_root()
    build_index = cache / "build_cache_index.json"
    return {
        "roots": {
            "data": str(storage_paths.data_root()),
            "cache": str(storage_paths.cache_root()),
            "temp": str(temp),
        },
        "containers": _area(data / "containers"),
        "locks": _area(data / "locks"),
        "sessions": _area(data / "sessions"),
        "oci_layers": _area(cache / "oci_layers"),
        "oci_manifests": _area(cache / "oci_manifests"),
        "build_index": {
            "path": str(build_index),
            "bytes": build_index.stat().st_size if build_index.is_file() else 0,
            "count": 1 if build_index.is_file() else 0,
        },
        "temp_exports": _area(temp / "exports"),
        "busy_locks": busy_locks(),
    }


def busy_locks() -> list[str]:
    """Locks held by other processes — 'install in progress' states."""
    try:
        locking = _imp("proot_distro.locking")

        return [hint for _path, hint in locking.busy_locks()]
    except Exception:
        return []


def inspect_container(name: str) -> dict:
    """Inspect installed container: image origin, OCI config, guest /etc/os-release."""
    guestfile = _imp("proot_distro.guestfile")
    paths = _imp("proot_distro.paths")

    rootfs = paths.container_rootfs(name)
    origin_image, origin_arch = "", ""
    try:
        origin_image, origin_arch = paths.container_image_origin(name)
    except Exception as exc:
        logger.debug("image origin unavailable for %s: %r", name, exc)

    config = {}
    image_id = ""
    try:
        config = paths.container_image_config(name) or {}
    except Exception as exc:
        logger.debug("OCI config unavailable for %s: %r", name, exc)
    try:
        manifest = paths.read_container_manifest(name)
        cache_mod = _imp("proot_distro.helpers.docker.cache")
        image_id = cache_mod.manifest_config_digest(manifest.get("manifest") or {})
    except Exception as exc:
        logger.debug("image id unavailable for %s: %r", name, exc)

    os_release = {}
    try:
        raw = guestfile.read_guest_file(rootfs, "etc/os-release") or guestfile.read_guest_file(
            rootfs, "usr/lib/os-release"
        )
        if raw:
            for line in raw.splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os_release[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as exc:
        logger.debug("guest os-release unreadable for %s: %r", name, exc)

    return {
        "name": name,
        "image": origin_image,
        "arch": origin_arch,
        "image_id": image_id,
        "os_release": os_release,
        "config": config,
    }


def active_sessions() -> list[dict]:
    """Live sessions as upstream sees them (read-only; we never register)."""
    try:
        session = _imp("proot_distro.session")

        return [
            {
                "pid": record.get("pid"),
                "container": record.get("container"),
                "kind": record.get("kind"),
                "user": record.get("user"),
                "command": record.get("command"),
                "start_time": record.get("start_time"),
            }
            for record in session.active_sessions()
        ]
    except Exception:
        # Re-raise: the caller's "no running sessions" must not lie on failure.
        logger.warning("active_sessions failed", exc_info=True)
        raise
