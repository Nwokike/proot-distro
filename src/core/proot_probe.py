"""Environment + payload probe — the gates run before any UI."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    native_dir: Path | None = None
    runtime_dir: Path | None = None
    staged: list[str] = field(default_factory=list)
    payload_provenance: str = "unavailable"
    f2fs: str = "not probed"
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


_PACKAGE_NAME = "ng.kiri.prootdistro"
_ABI_DIRS = frozenset({"arm64", "arm64-v8a", "armeabi-v7a", "x86_64", "x86"})


def is_android() -> bool:
    """True when running inside the packaged Android app."""
    return bool(os.environ.get("ANDROID_NATIVE_LIBRARY_DIR")) or Path("/data/app").exists()


def _native_dir_from_maps() -> Path | None:
    """Derive the APK native lib dir from this process's loaded libraries.

    The Flutter engine (libflutter.so) always loads from the same
    `lib/<abi>` directory our proot payload is extracted into, so
    `/proc/self/maps` names that directory — and unlike the env var it is
    always readable from inside the app process.
    """
    try:
        with open("/proc/self/maps", "rb") as f:
            blob = f.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in blob.splitlines():
        parts = line.split(maxsplit=5)
        if len(parts) != 6 or not parts[5].startswith("/"):
            continue
        path = Path(parts[5])
        if _PACKAGE_NAME not in str(path):
            continue
        # .../<pkg>-<hash>/lib/<abi>/libfoo.so → .../lib/<abi>
        if path.parent.parent.name == "lib" and path.parent.name in _ABI_DIRS:
            return path.parent
    return None


def _native_library_dir() -> Path | None:
    """The APK's extracted native libs dir (empty unless on a packaged app)."""
    native = os.environ.get("ANDROID_NATIVE_LIBRARY_DIR", "")
    if native and Path(native).is_dir():
        return Path(native)
    if os.environ.get("PD_PROOT_BIN"):
        # A previously resolved payload (e.g. by ensure_proot_env) wins over
        # re-globbing: its parent is the dir the binary was proven to be in.
        candidate = Path(os.environ["PD_PROOT_BIN"]).parent
        if candidate.is_dir():
            return candidate
    # This process's own loaded native libraries name the directory (the
    # Flutter engine lives beside the proot payload).
    from_maps = _native_dir_from_maps()
    if from_maps is not None:
        return from_maps
    # Dev fallback: support Android 11+ (~~), legacy /data/app, and nested
    # "~~" base64 directory layouts used by modern installers.
    for pattern in (
        "~~*/ng.kiri.prootdistro-*/lib/*",
        "*/ng.kiri.prootdistro-*/lib/*",
        "ng.kiri.prootdistro-*/lib/*",
    ):
        for hit in sorted(Path("/data/app").glob(pattern)):
            if hit.is_dir():
                return hit
    return None


_PAYLOAD_ENV_DONE = False


def ensure_proot_env(force: bool = False) -> bool:
    """Resolve the payload env (PD_PROOT_BIN/PROOT_LOADER/LD_LIBRARY_PATH) once.

    Lightweight — no subprocess — and safe to call from any service entry.
    Returns True when a proot binary is available after the call. This is the
    guarantee `bootstrap()` gives every proot_distro call, so a login can never
    run before the binary path was resolved (the "proot utility does not exist"
    failure on device).
    """
    global _PAYLOAD_ENV_DONE
    if _PAYLOAD_ENV_DONE and not force:
        return True

    from . import storage_paths

    native = _native_library_dir()
    if native is not None:
        proot_bin = native / "libproot.so"
        if proot_bin.is_file():
            runtime = storage_paths.support_root() / "runtime"
            runtime.mkdir(parents=True, exist_ok=True)
            ld = [str(p) for p in (native, runtime) if p]
            os.environ["LD_LIBRARY_PATH"] = ":".join(ld)
            os.environ["PD_PROOT_BIN"] = str(proot_bin)
            loader = native / "libproot-loader.so"
            if loader.is_file():
                os.environ["PROOT_LOADER"] = str(loader)
            os.environ["PROOT_TMP_DIR"] = str(storage_paths.proot_tmp_dir())
            _PAYLOAD_ENV_DONE = True
            return True

    # Desktop/dev: system proot or an explicit override.
    import shutil

    sys_proot = os.environ.get("PD_PROOT_BIN") or shutil.which("proot")
    if sys_proot and Path(sys_proot).is_file() and os.access(sys_proot, os.X_OK):
        os.environ["PD_PROOT_BIN"] = str(Path(sys_proot).resolve())
        os.environ["PROOT_TMP_DIR"] = str(storage_paths.proot_tmp_dir())
        _PAYLOAD_ENV_DONE = True
        return True

    return False


def _f2fs_probe(base_dir: Path) -> str:
    """Replicate proot's f2fs-bug probe (src/path/f2fs-bug.c)."""
    try:
        d = Path(tempfile.mkdtemp(prefix="proot_f2fsbug_", dir=str(base_dir)))
    except Exception as exc:
        return f"probe failed: {exc!r}"
    try:
        try:
            (d / "aa").write_bytes(b"x")
            try:
                (d / "Aa").write_bytes(b"x")
            except OSError:
                return f"case-INSENSITIVE filesystem in {base_dir} (unexpected)"
            if (d / "aA").exists():
                return f"f2fs-bug signature present in {base_dir}"
            return f"f2fs bug NOT present in {base_dir}"
        except Exception as exc:
            # Any probe failure is a report, never a startup crash — this
            # runs inside bootstrap_env before the UI exists.
            return f"probe failed: {exc!r}"
    finally:
        for p in sorted(d.glob("*"), reverse=True):
            try:
                p.unlink()
            except OSError as exc:
                logger.debug("f2fs probe left %s behind: %r", p, exc)
        try:
            d.rmdir()
        except OSError as exc:
            logger.debug("f2fs probe dir %s not removed: %r", d, exc)


def bootstrap_env(runtime_root: Path | None = None) -> ProbeResult:
    """Stage payloads and return the probe. Call BEFORE any proot_distro import."""
    from . import storage_paths

    res = ProbeResult()
    native = _native_library_dir()
    res.native_dir = native

    is_android = (
        bool(os.environ.get("ANDROID_NATIVE_LIBRARY_DIR"))
        or Path("/data/app").exists()
        or (native is not None)
    )

    if native is None:
        if is_android:
            res.problems.append("no nativeLibraryDir — this build cannot exec proot")
            return res

        # Desktop Linux / local development: locate system proot or bundled binary
        import shutil

        sys_proot = (
            os.environ.get("PD_PROOT_BIN")
            or shutil.which("proot")
            or ("/usr/bin/proot" if Path("/usr/bin/proot").is_file() else None)
        )
        if sys_proot and Path(sys_proot).is_file() and os.access(sys_proot, os.X_OK):
            proot_path = Path(sys_proot).resolve()
            os.environ["PD_PROOT_BIN"] = str(proot_path)
            res.native_dir = proot_path.parent
            res.payload_provenance = f"system proot ({proot_path})"
        else:
            # Desktop dev runs only: the packaged Android APK always ships the
            # proot payload, so this can only appear running unbundled source.
            res.problems.append(
                "no proot binary for this dev run — the packaged APK bundles it. "
                "For local source runs, install proot ('sudo dnf install proot' / "
                "'sudo apt install proot') or set PD_PROOT_BIN to a proot binary."
            )
            return res

    runtime = runtime_root or (storage_paths.support_root() / "runtime")
    runtime.mkdir(parents=True, exist_ok=True)
    res.runtime_dir = runtime

    if native is not None:
        try:
            import flet_proot  # type: ignore[import-not-found]

            version = getattr(flet_proot, "VERSION", "?")
            pinned = ", ".join(
                f"{s.get('package')} {s.get('version')}" for s in getattr(flet_proot, "SOURCES", [])
            )
            res.payload_provenance = f"flet-proot {version} build 1 [{pinned}]"
            for lib in getattr(flet_proot, "LIBS", []):
                soname, jni = lib.get("soname"), lib["jni"]
                if not soname or soname == jni:
                    continue
                src, dst = native / jni, runtime / soname
                if not src.exists():
                    res.staged.append(f"MISSING {src}")
                    continue
                if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                    dst.write_bytes(src.read_bytes())
                dst.chmod(0o755)
                res.staged.append(f"{jni} -> {dst.name}")
        except Exception as exc:  # manifest absent in dev / partial builds
            res.staged.append(f"manifest unavailable: {exc!r}")

        ld = [str(p) for p in (native, runtime) if p]
        os.environ["LD_LIBRARY_PATH"] = ":".join(ld)
        os.environ["PD_PROOT_BIN"] = str(native / "libproot.so")
        os.environ["PROOT_LOADER"] = str(native / "libproot-loader.so")

    os.environ["PROOT_TMP_DIR"] = str(storage_paths.proot_tmp_dir())

    res.f2fs = _f2fs_probe(
        storage_paths.proot_tmp_dir() if storage_paths.proot_tmp_dir().is_dir() else runtime
    )

    try:
        proc = subprocess.run(  # noqa: S603 - our own staged payload from the flet-proot wheel
            [os.environ["PD_PROOT_BIN"], "--version"],
            capture_output=True,
            timeout=30,
            env=dict(os.environ),
        )
        if proc.returncode != 0:
            res.problems.append(f"proot --version rc={proc.returncode}")
    except Exception as exc:
        res.problems.append(f"proot exec failed: {exc!r}")

    croot = storage_paths.containers_dir()
    try:
        croot.mkdir(parents=True, exist_ok=True)
        probe_file = croot / ".write-probe"
        probe_file.write_bytes(b"x")
        probe_file.unlink()
    except Exception as exc:
        res.problems.append(f"storage not writable: {exc!r}")

    return res
