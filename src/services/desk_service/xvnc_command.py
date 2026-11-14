"""The Xvnc argv (every flag maps to a real 1.16.2 parameter)."""

from __future__ import annotations

import logging
from pathlib import Path

from .xvnc_paths import (
    RFB_PORT_BASE,
    _payload_env,
    ensure_lock_dir,
    ensure_prefix_bin,
    xvnc_binary,
)

logger = logging.getLogger(__name__)


def xvnc_command(
    display: int,
    geometry: str,
    xauth_path: Path,
    xkb_dir: Path,
    *,
    depth: str = "24",
    frame_rate: int = 30,
    shared_policy: str = "always",
    clipboard: bool = True,
    disconnect_timeout: int = 0,
    desktop_name: str = "",
    font_paths: list[str] | None = None,
    localhost_only: bool = False,
    compare_fb: int = 2,
    dpi: int = 0,
    idle_timeout: int = 0,
    max_connection_time: int = 0,
    view_only: bool = False,
    max_cut_text: int = 0,
    disconnect_clients: bool = False,
) -> tuple[list[str], dict[str, str]]:
    """The Xvnc argv + env.

    Defaults keep the historical behaviour: `-SecurityTypes None`, and
    TigerVNC 1.16.2's own default `-localhost false` / interface "all" — so the
    RFB port is reachable from other interfaces unless the user opts into
    `localhost_only` (`-localhost=1`). The stream server's access code gates the
    viewer page and WebSocket; this flag gates the raw RFB port itself.
    TigerVNC's `-Password`/`-rfbauth` need an OBFUSCATED 8-byte secret (its
    BinaryParameter hex-decodes, then the server deobfuscates), which needs
    vncpasswd's DES — we ship neither, so no half-working password control.

    Every option here maps 1:1 to a real Xvnc 1.16.2 parameter: depth → -depth,
    frame_rate → -FrameRate, shared_policy → -AlwaysShared/-NeverShared,
    clipboard → -AcceptCutText/-SendCutText, disconnect_timeout →
    -MaxDisconnectionTime, desktop_name → -desktop."""
    ensure_lock_dir()  # the rewritten prefix's <app>/tmp must exist before start
    ensure_prefix_bin()  # <app>/bin/sh + <app>/bin/xkbcomp, the paths Xvnc execs
    binary = xvnc_binary()
    argv = [
        str(binary),
        f":{display}",
        "-geometry",
        geometry,
        "-depth",
        str(depth),
        "-rfbport",
        str(RFB_PORT_BASE + display),
        "-SecurityTypes",
        "None",
        "-auth",
        str(xauth_path),
        "-xkbdir",
        str(xkb_dir),
        # FrameRate default in Xvnc is 60; the app default is 30 (phone CPU).
        f"-FrameRate={int(frame_rate)}",
        # 2 = compare the framebuffer before sending (Xvnc default), 1 = region
        # compare, 0 = always send the update.
        f"-CompareFB={max(0, min(2, int(compare_fb)))}",
        # The unix socket lives under /tmp/.X11-unix, which does not exist on
        # Android; the guest apps connect over TCP anyway (shared loopback).
        # -listen tcp sets PartialNetwork, so the missing unix socket is
        # tolerated instead of a FatalError.
        "-listen",
        "tcp",
        "-nolisten",
        "unix",
        "-noreset",
    ]
    if localhost_only:
        argv.append("-localhost=1")
    if int(dpi) > 0:
        # X server DPI: font/UI scaling inside the guest.
        argv.extend(["-dpi", str(int(dpi))])
    if int(idle_timeout) > 0:
        # Drop an idle VIEWER; the session keeps running.
        argv.append(f"-IdleTimeout={int(idle_timeout)}")
    if int(max_connection_time) > 0:
        # Hard cap on a viewer connection's lifetime.
        argv.append(f"-MaxConnectionTime={int(max_connection_time)}")
    if view_only:
        # Server-side view-only: the screenshot is live, input is refused.
        argv.extend(["-AcceptKeyEvents=0", "-AcceptPointerEvents=0"])
    if int(max_cut_text) > 0:
        argv.append(f"-MaxCutText={int(max_cut_text)}")
    if disconnect_clients:
        argv.append("-DisconnectClients=1")
    if shared_policy == "always":
        argv.append("-AlwaysShared=1")
    elif shared_policy == "never":
        # One viewer at a time; a new connection takes over.
        argv.extend(["-NeverShared=1", "-DisconnectClients=1"])
    if not clipboard:
        # Clipboard sync off in BOTH directions (privacy for shared displays).
        argv.extend(["-AcceptCutText=0", "-SendCutText=0"])
    if int(disconnect_timeout) > 0:
        # Auto-teardown N seconds after the last viewer leaves.
        argv.append(f"-MaxDisconnectionTime={int(disconnect_timeout)}")
    if desktop_name:
        argv.extend(["-desktop", str(desktop_name)])
    if font_paths:
        # -fp is a COMMA-separated list; a path containing a comma would split
        # the list, so such paths are dropped rather than corrupting it.
        cleaned = [p for p in font_paths if p and "," not in p]
        if cleaned:
            argv.extend(["-fp", ",".join(cleaned)])
    return argv, _payload_env(binary.parent)
