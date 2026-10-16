"""M0 device spike — throwaway gate harness (see docs/roadmap.md M0).

Proves on-device, in order:
  G1  nativeLibraryDir exec: libproot.so --version
  G1b Python self-spawn probe (sys.executable -c)  -> informs the CLI route
  G2  in-process proot-distro install (alpine:3.21 via Docker Hub OCI)
  G3  one-shot guest exec (proot -0 -r rootfs ... /bin/sh -c ...)
  G4  OCI pull debian:bookworm + apt-get install cowsay + run it
      (proves loader mmap-exec of newly written guest binaries)
  G5  long-lived interactive session in flet-terminal (ProotSession)
  G6  evidence export to the app documents dir

Everything runs on the Flet app thread via asyncio.to_thread; env is set
BEFORE any proot_distro import (its constants are import-time). This file is
disposable: M0 results go to docs/m0-checklist.md, then the real app replaces it.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import glob
import io
import json
import os
import platform
import struct
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

import flet as ft

APP_DIR = Path(__file__).resolve().parent
RESULTS: dict[str, str] = {}

# Activity terminal — house pattern (Courier New, #A6E22E on #0D0D0D).
TERMINAL_BG = "#0D0D0D"
TERMINAL_TEXT = "#A6E22E"


# ── bootstrap (env must be set before proot_distro is ever imported) ────────


def _env_dir(name: str, fallback: Path) -> Path:
    v = os.environ.get(name)
    return Path(v) if v else fallback


def bootstrap_env() -> dict:
    data = _env_dir("FLET_APP_STORAGE_DATA", Path.cwd())
    dirs = {
        "data": data,
        "home": data / "home",
        "xdg_data": data / ".local" / "share",
        "xdg_cache": data / ".local" / "cache",
        "tmp": data / "tmp",
        "runtime": data / "runtime",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    native = os.environ.get("ANDROID_NATIVE_LIBRARY_DIR", "")
    if not native or not Path(native).is_dir():
        hits = glob.glob("/data/app/*/ng.kiri.m0spike-*/lib/arm64")
        native = hits[0] if hits else ""
    native_p = Path(native) if native else None

    os.environ.update(
        {
            "HOME": str(dirs["home"]),
            "XDG_DATA_HOME": str(dirs["xdg_data"]),
            "XDG_CACHE_HOME": str(dirs["xdg_cache"]),
            "TMPDIR": str(dirs["tmp"]),
        }
    )

    staged = stage_runtime_libs(native_p, dirs["runtime"]) if native_p else []

    ld = [str(p) for p in (native_p, dirs["runtime"]) if p]
    os.environ["LD_LIBRARY_PATH"] = ":".join(ld)
    if native_p:
        os.environ["PD_PROOT_BIN"] = str(native_p / "libproot.so")
        os.environ["PROOT_LOADER"] = str(native_p / "libproot-loader.so")
        os.environ["PROOT_TMP_DIR"] = str(dirs["tmp"])

    return {"dirs": dirs, "native": native_p, "staged": staged}


def stage_runtime_libs(native: Path, runtime: Path) -> list[str]:
    """Copy payloads whose DT_SONAME differs from their jni filename so the
    linker can satisfy DT_NEEDED names via LD_LIBRARY_PATH (mmap-exec of
    app-data files stays allowed; execve is not involved here)."""
    staged: list[str] = []
    try:
        import flet_proot  # type: ignore[import-not-found]

        for lib in getattr(flet_proot, "LIBS", []):
            soname, jni = lib.get("soname"), lib["jni"]
            if not soname or soname == jni:
                continue
            src, dst = native / jni, runtime / soname
            if not src.exists():
                staged.append(f"MISSING {src}")
                continue
            if not dst.exists() or dst.stat().st_size != src.stat().st_size:
                dst.write_bytes(src.read_bytes())
            dst.chmod(0o755)
            staged.append(f"{jni} -> {dst.name}")
    except Exception as e:  # manifest absent in dev / partial builds
        staged.append(f"manifest unavailable: {e!r}")
    return staged


# ── gates ────────────────────────────────────────────────────────────────────


def _run(argv: list[str], timeout: int, cwd: str | None = None, env: dict | None = None) -> str:
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout, cwd=cwd, env=env)
        out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        return f"rc={p.returncode} in {time.time() - t0:.1f}s\n{out.strip()[-4000:]}"
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout}s — HANG (this is the signal we are hunting)"
    except Exception as e:
        return f"spawn failed: {e!r}\n{traceback.format_exc()[-1500:]}"


def _install(image_ref: str, name: str) -> str:
    """In-process proot-distro install (lazy import AFTER env is set)."""
    try:
        from proot_distro.commands.install import command_install
    except (ImportError, AttributeError) as e:
        # e.g. os.O_DIRECTORY missing on Windows: proot-distro uses POSIX
        # dir-fd APIs and only imports on Linux/Android.
        return (
            f"proot-distro cannot import on this platform ({e!r}).\n"
            "It is Linux-only (POSIX dir-fd APIs) — this gate runs on the Android device."
        )

    ns = SimpleNamespace(
        image_ref=image_ref,
        custom_container_name=name,
        override_arch=None,
        allow_insecure=False,
    )
    buf = io.StringIO()
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            command_install(ns)
        return f"OK in {time.time() - t0:.1f}s\n{buf.getvalue().strip()[-3000:]}"
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        return f"SystemExit({code}) in {time.time() - t0:.1f}s\n{buf.getvalue().strip()[-3000:]}"
    except Exception:
        return f"EXCEPTION in {time.time() - t0:.1f}s\n{buf.getvalue().strip()[-1500:]}\n{traceback.format_exc()[-1500:]}"


def rootfs_path(name: str, dirs: dict) -> Path:
    return dirs["xdg_data"] / "proot-distro" / "containers" / name / "rootfs"


def _container_shm(rootfs: Path) -> Path:
    """Per-container shm dir exactly as proot-distro creates it
    (`containers/<name>/shm`, mode 1777) and binds to /dev/shm — required by
    the --sysvipc path we enable (root-caused 2026-10-16; we previously passed
    --sysvipc without any shm dir/bind)."""
    shm = rootfs.parent / "shm"
    with contextlib.suppress(OSError):
        shm.mkdir(parents=True, exist_ok=True)
        os.chmod(shm, 0o1777)
    return shm


def guest_argv(native: Path, rootfs: Path, script: str) -> list[str]:
    return [
        str(native / "libproot.so"),
        "-0",
        *proot_extensions(),
        "-r",
        str(rootfs),
        "-b",
        "/dev",
        "-b",
        "/proc",
        "-b",
        "/sys",
        # proot-distro's non-minimal binds (verified diff, root-cause research):
        f"--bind={_container_shm(rootfs)}:/dev/shm",
        "--bind=/dev/urandom:/dev/random",
        "--bind=/proc/self/fd:/dev/fd",
        "-w",
        "/",
        "/bin/sh",
        "-c",
        script,
    ]


def proot_extensions() -> list[str]:
    """Termux-mode extension flags — one-to-one with proot-distro's
    commands/login/proot_cmd.py::_add_proot_extensions (non-minimal branch).

    --link2symlink is REQUIRED on Android: SELinux denies the link() syscall
    to apps, and dpkg's backup-link step fails without it (observed on-device:
    "unable to make backup link of './usr/bin/perl' ... Permission denied" /
    "error creating new backup file '/var/lib/dpkg/status-old'").
    -L is theirs too ("Fix lstat for dpkg symlink warnings"). All flags
    verified present in proot 5.1.107.96 (src/cli/proot.h lines 157/199/239/285).
    """
    try:
        from proot_distro.constants import DEFAULT_FAKE_KERNEL_VERSION
    except Exception:  # desktop / proot-distro not importable here
        DEFAULT_FAKE_KERNEL_VERSION = "#1 SMP PREEMPT_DYNAMIC Fri, 10 Oct 2025 00:00:00 +0000"
    uname_m = platform.machine() or "aarch64"
    return [
        "--kill-on-exit",
        "--link2symlink",
        "--sysvipc",
        f"--kernel-release=\\Linux\\localhost\\{platform.release()}"
        f"\\{DEFAULT_FAKE_KERNEL_VERSION}\\{uname_m}\\localdomain\\-1\\",
        "-L",
    ]


def guest_env(rootfs: Path | None = None) -> dict:
    """Guest environment — one-to-one with proot-distro's own defaults.

    PATH = constants.py DEFAULT_PATH_ENV (non-Termux variant, :115-118);
    HOME/USER/TERM mirror commands/login/__init__.py::_build_normal_env
    (:281-286: HOME=login_home, USER=login_user, TERM or xterm-256color).
    Merged over the host essentials proot itself needs to start
    (LD_LIBRARY_PATH, PROOT_LOADER, PROOT_TMP_DIR) — without PATH the guest's
    sh cannot find id/ls/apt-get even though they exist in the rootfs.
    """
    env = dict(os.environ)
    env.update(
        {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ":/usr/local/games:/usr/games",
            "HOME": "/root",
            "USER": "root",
            "TERM": os.environ.get("TERM") or "xterm-256color",
            # proot's f2fs workaround (canon.c: substitute_binding_stat ->
            # should_skip_file_access_due_to_f2fs_bug) SYNTHESIZES -ENOENT when
            # its readdir probe misses a just-created entry — which is exactly
            # dpkg's .dpkg-new + link2symlink sequence on f2fs app storage.
            # Root-caused 2026-10-16 ("error setting ownership of .dpkg-new:
            # No such file or directory"); disabling trusts the kernel.
            "PROOT_F2FS_WORKAROUND": "0",
        }
    )
    if rootfs is not None:
        # l2s.py:70-71 — proot-distro pins PROOT_L2S_DIR to <rootfs>/.l2s;
        # every link2symlink intermediate lives there.
        l2s = rootfs / ".l2s"
        with contextlib.suppress(OSError):
            l2s.mkdir(parents=True, exist_ok=True)
        env["PROOT_L2S_DIR"] = str(l2s)
    return env


# ── interactive session — PTY-backed ────────────────────────────────────────
#
# One-to-one adoption of the OWNER'S OWN recipe: Nwokike/flet-terminal's
# examples/flet_terminal_example/src/pty_service.py ("cross-platform process
# and PTY management for Linux, Windows, and Android"), which the owner built
# and ran on Android: pty.openpty() -> Popen(argv, stdio=slave_fd,
# start_new_session=True) -> os.read(master) loop; resize via TIOCSWINSZ
# ioctl on the master fd. termios/fcntl/pty ship in the Android stdlib build
# (libtermios.so / libfcntl.so appear in nativeLibraryDir).


class ProotSession:
    @staticmethod
    def availability() -> str:
        if sys.platform in ("emscripten", "wasi", "win32"):
            return f"posix-pty not applicable on {sys.platform}"
        try:
            import fcntl  # noqa: F401
            import pty
            import termios  # noqa: F401

            m, s = pty.openpty()
            os.close(m)
            os.close(s)
            return "posix-pty available (openpty OK)"
        except Exception as e:
            return f"posix-pty unavailable: {e!r}"

    def __init__(self, argv: list[str], deliver, on_error, env: dict | None = None):
        self.argv = argv
        self.deliver = deliver  # callable(bytes), session-thread safe
        self.on_error = on_error
        self.env = env
        self.master_fd: int | None = None
        self._slave_fd: int | None = None
        self.proc: subprocess.Popen | None = None

    def _preexec(self) -> None:  # child-only: own session + controlling tty
        os.setsid()
        if self._slave_fd is not None:
            with contextlib.suppress(OSError):
                import fcntl
                import termios

                fcntl.ioctl(self._slave_fd, termios.TIOCSCTTY, 0)

    def start(self) -> None:
        import pty

        master_fd, slave_fd = pty.openpty()
        self._slave_fd = slave_fd
        self.proc = subprocess.Popen(
            self.argv,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
            preexec_fn=self._preexec,
            env=self.env,
        )
        self._slave_fd = None
        os.close(slave_fd)
        self.master_fd = master_fd
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._waiter, daemon=True).start()

    def _reader(self) -> None:
        fd = self.master_fd
        while self.master_fd == fd and fd is not None:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            self.deliver(data)

    def _waiter(self) -> None:
        rc = self.proc.wait()
        self.deliver(f"\r\n[session exited rc={rc}]\r\n".encode())

    def write(self, data) -> None:
        if self.master_fd is not None:
            with contextlib.suppress(OSError):
                os.write(self.master_fd, data)

    def resize(self, cols: int, rows: int) -> None:
        if self.master_fd is None or cols <= 0 or rows <= 0:
            return
        try:
            import fcntl
            import termios

            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except Exception as e:
            self.on_error(f"resize failed: {e!r}")

    def stop(self) -> None:
        if self.master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self.master_fd)
            self.master_fd = None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


# ── UI ───────────────────────────────────────────────────────────────────────


def main(page: ft.Page):
    page.appbar = ft.AppBar(adaptive=True, title="M0 Spike")
    page.padding = 16
    page.scroll = ft.ScrollMode.AUTO

    # `grp` is excluded from CPython's Android build (PEP 738) and the device
    # log confirms it (ModuleNotFoundError) — but proot-distro imports it
    # unconditionally. `probe()` reports which modules the device really has;
    # `ensure()` shims only the missing ones. Runs BEFORE any proot_distro import.
    sys.path.insert(0, str(APP_DIR))
    import posixdb

    posixdb_probe = posixdb.probe()
    posixdb_shimmed = posixdb.ensure()

    boot = bootstrap_env()
    dirs, native = boot["dirs"], boot["native"]

    # Activity terminal — house pattern: single growing Text inside a
    # fixed-height scrollable container (the scroll fix).
    log_text = ft.Text(value="", font_family="Courier New", size=11, color=TERMINAL_TEXT, selectable=True)
    log_col = ft.Column(controls=[log_text], scroll=ft.ScrollMode.AUTO, expand=True)
    log_terminal = ft.Container(
        content=log_col,
        bgcolor=TERMINAL_BG,
        padding=12,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
        border_radius=8,
        height=340,
    )

    def log(message: str) -> None:
        print(message, flush=True)
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        block = str(message).strip("\n")
        log_text.value = f"{log_text.value}\n[{ts}] {block}" if log_text.value else f"[{ts}] {block}"
        page.update(log_text)

        async def _scroll_to_end():
            await asyncio.sleep(0.05)
            with contextlib.suppress(Exception):
                await log_col.scroll_to(offset=-1)  # offset=-1: jump to newest

        page.run_task(_scroll_to_end)

    def gate_result(gate: str, body: str) -> None:
        RESULTS[gate] = body
        log(f"\n===== {gate} =====\n{body}")

    async def run_in_thread(gate: str, fn, *args) -> None:
        log(f"\n----- {gate} started -----")
        try:
            body = await asyncio.to_thread(fn, *args)
        except Exception:
            body = traceback.format_exc()
        gate_result(gate, body)

    # G1 ─────────────────────────────────────────────────────────────────────
    def g1() -> str:
        out = [f"proot path: {native/'libproot.so' if native else 'N/A'}"]
        if not native:
            return "\n".join(out) + "\nNO nativeLibraryDir — cannot continue"
        for f in sorted(native.iterdir()):
            st = f.stat()
            out.append(f"  {f.name:<28} {st.st_size:>9} mode={oct(st.st_mode)[-3:]}")
        p = native / "libproot.so"
        out.append(f"X_OK={os.access(p, os.X_OK)}")
        with contextlib.suppress(OSError):
            p.chmod(0o755)
        out.append(_run([str(p), "--version"], timeout=30))
        return "\n".join(out)

    def g1b() -> str:
        out = f"sys.executable={sys.executable!r}\n" + _run([sys.executable, "-c", "print('spawn-ok')"], timeout=30)
        return (
            out
            + "\nnote: on Android sys.executable is the Flutter host (app_process64), not the embedded\n"
            "interpreter — the CLI-subprocess route is NOT viable; use in-process APIs + direct proot spawn."
        )

    def d0_diag() -> str:
        """Diagnostics for the dpkg chown-ENOENT case (run after a failed apt)."""
        r = rootfs_path("debian", dirs)
        out = ["host-side <rootfs>/.l2s entries (last 10):"]
        l2s = r / ".l2s"
        out.append(
            "\n".join(sorted(p.name for p in l2s.iterdir())[-10:]) if l2s.is_dir() else "  (no .l2s dir)"
        )
        out.append("host-side perl leftovers:")
        out.append("\n".join(sorted(p.name for p in (r / "usr/bin").glob("perl*")) if native else []))
        out.append("guest-side evidence:")
        if native:
            out.append(
                _run(
                    guest_argv(
                        native,
                        r,
                        "ls -la /usr/bin/perl* 2>&1; "
                        "readlink /usr/bin/perl 2>&1; "
                        "readlink /usr/bin/perl5.36.0.dpkg-new 2>&1; "
                        "ls -la /var/lib/dpkg/status* 2>&1",
                    ),
                    60,
                    env=guest_env(r),
                )
            )
        return "\n".join(out)

    # G5 wiring (needs page; created before use) ────────────────────────────
    # NOTE: plain `Terminal` (a @control) — MobileTerminal composes
    # `@ft.component` children (ExtraKeysBar) and raises outside an active
    # renderer context ("no current renderer is set. Call render.render or
    # render.withContext") — a documented M1 flet-terminal refactor item.
    try:
        from flet_terminal import Terminal as FletTerminalControl  # type: ignore[import-not-found]

        mt: ft.Control = FletTerminalControl(
            scrollback=5000, font_family="monospace", auto_focus=False, expand=True
        )
    except Exception as e:  # dev previews / build without the extension
        mt = ft.Text(f"flet-terminal unavailable: {e!r}")
    session: ProotSession | None = None

    def deliver(data: bytes) -> None:
        if isinstance(mt, ft.Text):
            return
        page.loop.call_soon_threadsafe(mt.send_bytes, data)

    def on_bytes(data) -> None:
        if session:
            session.write(data)

    if not isinstance(mt, ft.Text):
        mt.set_on_bytes(on_bytes)

        def on_terminal_resize(e) -> None:
            if session is None:
                return
            with contextlib.suppress(Exception):
                dims = json.loads(e.data)
                session.resize(int(dims.get("cols", 0)), int(dims.get("rows", 0)))

        mt.on_resize = on_terminal_resize

    def session_start() -> str:
        nonlocal session
        if not native:
            return "no nativeLibraryDir — cannot start a session"
        r = rootfs_path("alpine", dirs)
        if not r.is_dir():
            return f"no alpine rootfs at {r} — run G2 first"
        session = ProotSession(
            [
                str(native / "libproot.so"), "-0", *proot_extensions(), "-r", str(r),
                "-b", "/dev", "-b", "/proc", "-b", "/sys",
                f"--bind={_container_shm(r)}:/dev/shm",
                "--bind=/dev/urandom:/dev/random",
                "--bind=/proc/self/fd:/dev/fd",
                "-w", "/",
                "/bin/sh", "-i",
            ],
            deliver,
            on_error=log,
            env=guest_env(r),
        )
        try:
            session.start()
            return (
                "session started (PTY + controlling tty, guest env from proot-distro defaults)\n"
                "(try: ls / ; cat /etc/os-release ; apt-get update ; exit) — resize via TIOCSWINSZ"
            )
        except Exception:
            return traceback.format_exc()

    # Buttons ────────────────────────────────────────────────────────────────
    def gate_button(label: str, handler) -> ft.Button:
        async def _click(_e):
            await run_in_thread(label.split(" ")[0], lambda: handler())

        return ft.Button(label, on_click=_click)

    async def run_all(_e):
        if not native:
            log("no nativeLibraryDir — aborting Run ALL")
            return
        await run_in_thread("G1", g1)
        await run_in_thread("G1b", g1b)
        await run_in_thread("G2", _install, "alpine:3.21", "alpine")
        await run_in_thread(
            "G3",
            lambda: _run(
                guest_argv(native, rootfs_path("alpine", dirs), "id; uname -a; cat /etc/os-release"),
                120,
                env=guest_env(rootfs_path("alpine", dirs)),
            )
            if native
            else "no native dir",
        )
        await run_in_thread("G4-install", _install, "debian:bookworm", "debian")
        if native:
            await run_in_thread(
                "G4-apt",
                lambda: _run(
                    guest_argv(
                        native,
                        rootfs_path("debian", dirs),
                        "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends cowsay && /usr/games/cowsay M0-OK",
                    ),
                    900,
                    env=guest_env(rootfs_path("debian", dirs)),
                ),
            )

    def export_report() -> str:
        doc = dirs["data"] / "m0-report.md"
        device = {
            "android_release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "flet_platform": os.environ.get("FLET_PLATFORM"),
            "flet_platform_version": os.environ.get("FLET_PLATFORM_VERSION"),
            "device_model": os.environ.get("FLET_PLATFORM_DEVICE_MODEL"),
        }
        with doc.open("w", encoding="utf-8") as f:
            f.write(f"# M0 spike report — {datetime.datetime.now(datetime.UTC).isoformat()}\n\n")
            f.write(f"device: `{json.dumps(device)}`\n\n")
            for gate, body in RESULTS.items():
                f.write(f"## {gate}\n\n```\n{body}\n```\n\n")
            f.write(f"## raw log tail\n\n```\n{log_text.value[-8000:]}\n```\n")
        return f"report written: {doc}"

    page.add(
        ft.Text("M0 Spike — proot on Android (go/no-go)", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("Tap Run ALL, then start the interactive session (G5). Results are recorded in docs/m0-checklist.md.",
                size=12, color=ft.Colors.GREY_600),
        ft.Row([
            ft.Button("Run ALL (G1-G4)", on_click=run_all, icon=ft.Icons.PLAY_ARROW),
            gate_button("G1 exec", g1),
            gate_button("G1b spawn-probe", g1b),
        ], wrap=True),
        ft.Row([
            gate_button("G2 install alpine", lambda: _install("alpine:3.21", "alpine")),
            gate_button("G3 one-shot alpine", lambda: _run(guest_argv(native, rootfs_path("alpine", dirs), "id; uname -a; cat /etc/os-release"), 120, env=guest_env(rootfs_path("alpine", dirs))) if native else "no native dir"),
            gate_button("G4 install debian", lambda: _install("debian:bookworm", "debian")),
            gate_button("G4 apt cowsay", lambda: _run(guest_argv(native, rootfs_path("debian", dirs), "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends cowsay && /usr/games/cowsay M0-OK"), 900, env=guest_env(rootfs_path("debian", dirs))) if native else "no native dir"),
            gate_button("D0 diag", d0_diag),
        ], wrap=True),
        ft.Divider(),
        ft.Text("G5 — interactive session (flet-terminal)", weight=ft.FontWeight.BOLD),
        ft.Row([
            gate_button("Start session", session_start),
            ft.Button("Stop session", on_click=lambda _e: session and session.stop()),
        ], wrap=True),
        ft.Container(mt, height=280, border=ft.Border.all(1, ft.Colors.GREY_400)),
        ft.Divider(),
        ft.Row([ft.Button("G6 export report", on_click=lambda _e: gate_result("G6", export_report()))]),
        ft.Text("Log", weight=ft.FontWeight.BOLD),
        log_terminal,
    )

    log("===== G0 bootstrap =====")
    log(f"platform: {platform.platform()}")
    uid = getattr(os, "getuid", lambda: "n/a")()
    euid = getattr(os, "geteuid", lambda: "n/a")()
    log(f"python: {sys.version.split()[0]}  uid={uid} euid={euid}")
    log(f"posixdb probe: {posixdb_probe}  shimmed: {posixdb_shimmed}")
    log(f"pty: {ProotSession.availability()}")
    log(f"proot extensions: {' '.join(proot_extensions())}")
    log(f"FLET_PLATFORM={os.environ.get('FLET_PLATFORM')!r} link64={Path('/system/bin/linker64').exists()}")
    log(f"nativeLibraryDir: {native!r}")
    log(f"storage: {json.dumps({k: str(v) for k, v in dirs.items()})}")
    log(f"staged runtime libs: {boot['staged']}")
    log(f"PD_PROOT_BIN={os.environ.get('PD_PROOT_BIN')!r}")
    log(f"LD_LIBRARY_PATH={os.environ.get('LD_LIBRARY_PATH')!r}")
    try:
        tracer = Path("/proc/self/status").read_text().split("TracerPid:")[1].split()[0]
        log(f"TracerPid={tracer}")
    except Exception as e:
        log(f"TracerPid read failed: {e!r}")


ft.run(main)
