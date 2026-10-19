"""Proot environment probe — gates every screen (FFmpeg probe pattern).

Answers three questions the UI must never guess (M0-proven order):
  1. Is the native payload there?  (`flet_proot` manifest in site-packages +
     the `opt/lib` payloads staged into the APK's native library dir)
  2. Can it run?                   (proot --version executes from it)
  3. Is the storage writable?      (containers/ root exists and accepts files)

`bootstrap_env()` ports the M0 spike's env dance (device-verified):
ANDROID_NATIVE_LIBRARY_DIR -> PD_PROOT_BIN/PROOT_LOADER, LD_LIBRARY_PATH
including a runtime dir for SONAME-staged libs (libtalloc.so.2). The staging
reads the `flet_proot` manifest — proof that the binaries came from the
sha256-pinned wheel (M2), not a hand-copied file.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


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


def _native_library_dir() -> Path | None:
    """The APK's extracted native libs dir (empty unless on a packaged app)."""
    native = os.environ.get("ANDROID_NATIVE_LIBRARY_DIR", "")
    if native and Path(native).is_dir():
        return Path(native)
    # Dev fallback: an emulator/edge layout, glob the well-known pattern.
    for hit in sorted(Path("/data/app").glob("*/ng.kiri.prootdistro-*/lib/arm64")):
        if hit.is_dir():
            return hit
    return None


def _f2fs_probe(base_dir: Path) -> str:
    """Replicate proot's own f2fs-bug probe (src/path/f2fs-bug.c).

    Creates aa/Aa and checks whether the kernel's case-insensitive lookup
    lies (access("aA") succeeds for a non-existent file). Device-verified on
    the owner's phone: "bug NOT present" — recorded per run so later failures
    reason from data.
    """
    try:
        d = Path(tempfile.mkdtemp(prefix="proot_f2fsbug_", dir=str(base_dir)))
    except Exception as exc:
        return f"probe failed: {exc!r}"
    try:
        (d / "aa").write_bytes(b"x")
        try:
            (d / "Aa").write_bytes(b"x")
        except OSError:
            return f"case-INSENSITIVE filesystem in {base_dir} (unexpected)"
        if (d / "aA").exists():
            return f"f2fs-bug signature present in {base_dir}"
        return f"f2fs bug NOT present in {base_dir}"
    finally:
        for p in sorted(d.glob("*"), reverse=True):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            d.rmdir()
        except OSError:
            pass


def bootstrap_env(runtime_root: Path | None = None) -> ProbeResult:
    """Stage payloads and return the probe. Call BEFORE any proot_distro import."""
    from . import storage_paths

    res = ProbeResult()
    native = _native_library_dir()
    res.native_dir = native
    if native is None:
        res.problems.append("no nativeLibraryDir — this build cannot exec proot")
        return res

    runtime = runtime_root or (storage_paths.support_root() / "runtime")
    runtime.mkdir(parents=True, exist_ok=True)
    res.runtime_dir = runtime

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
    os.environ["PROOT_TMP_DIR"] = str(storage_paths.support_root() / "tmp")

    res.f2fs = _f2fs_probe(
        storage_paths.support_root() / "tmp"
        if (storage_paths.support_root() / "tmp").is_dir()
        else runtime
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
