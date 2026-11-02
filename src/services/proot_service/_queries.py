"""Read-only queries: containers, cache, storage, inspect, sessions."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from core import storage_paths

from ._core import _imp
from ._guard import ProotUnavailable

logger = logging.getLogger(__name__)


def _tree_bytes(path: Path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += (Path(dirpath) / f).stat().st_size
            except OSError as exc:
                logger.debug("size walk skipped %s: %r", Path(dirpath) / f, exc)
    return total


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


def search_images(query: str, limit: int = 20) -> list[dict]:
    """Docker Hub search — upstream's own normalized hits (plain dicts)."""
    docker_search = _imp("proot_distro.helpers.docker.search")

    results, _total = docker_search.search_images(query, limit)
    return [r for r in results if isinstance(r, dict)]


def cached_images() -> list[dict]:
    """Cached OCI images (host-side sizes) for the storage screen."""
    cache = _imp("proot_distro.helpers.docker.cache")

    rows = []
    for image in cache.iter_cached_images():
        size = 0
        try:
            path = image.get("full_path") or image.get("path")
            if path and Path(path).is_dir():
                size = _tree_bytes(Path(path))
        except Exception as exc:
            logger.debug("cached image size unavailable: %r", exc)
        rows.append(
            {
                "identifier": image.get("image_ref") or image.get("id") or "?",
                "arch": image.get("arch", ""),
                "size_bytes": size,
            }
        )
    return rows


def storage_bytes() -> int:
    try:
        return _tree_bytes(storage_paths.xdg_data_home() / "proot-distro")
    except OSError as exc:
        raise ProotUnavailable(f"storage size unavailable: {exc}") from exc


def _area(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "bytes": 0, "count": 0}
    return {
        "path": str(p),
        "bytes": _tree_bytes(p),
        "count": sum(1 for entry in p.rglob("*") if entry.is_file()),
    }


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
    except Exception as exc:
        logger.warning("active_sessions failed: %r", exc)
        return []
