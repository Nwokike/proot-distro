"""Wheel-builder pure logic — payload resolution, soname rewrites, pin-set
integrity, platform tags, and the noVNC vendoring filter. No network: the
fetch test feeds a synthetic tarball.
"""

from __future__ import annotations

import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_flet_pulseaudio_wheel as pa_builder  # noqa: E402 - scripts/ is not a package
import build_flet_xvnc_wheel as xv_builder  # noqa: E402
import fetch_novnc  # noqa: E402

# ── payload resolution (the stem search that bit us twice) ───────────────────


def test_resolve_payload_prefers_exact_then_longest_versioned():
    files = {
        "usr/lib/libjpeg.so.8.3.2": b"real",
        "usr/lib/pkgconfig/libjpeg.pc": b"not-an-elf",
    }
    name, blob = xv_builder._resolve_payload(files, "libjpeg.so", None)
    assert name == "usr/lib/libjpeg.so.8.3.2"
    assert blob == b"real"


def test_resolve_payload_skips_non_shared_objects():
    """The .pc pkg-config file matches the stem but is not a .so — the bug that
    picked 'libcrypto.pc' over 'libcrypto.so.3' on the first run."""
    files = {
        "usr/lib/libcrypto.so.3": b"elf",
        "usr/lib/pkgconfig/libcrypto.pc": b"config",
    }
    name, _blob = xv_builder._resolve_payload(files, "libcrypto.so", None)
    assert name.endswith("libcrypto.so.3")


def test_resolve_payload_explicit_path_and_not_found():
    files = {"usr/bin/Xvnc": b"binary"}
    name, blob = xv_builder._resolve_payload(files, "libXvnc.so", "usr/bin/Xvnc")
    assert name == "usr/bin/Xvnc" and blob == b"binary"
    with pytest.raises(SystemExit):
        xv_builder._resolve_payload(files, "libXvnc.so", "usr/bin/Missing")
    with pytest.raises(SystemExit):
        xv_builder._resolve_payload({}, "libXvnc.so", None)


# ── soname rewrites (AGP drops versioned sonames — only lib*.so ships) ───────


def test_soname_rewrites_null_pad_the_shorter_name(monkeypatch):
    resolved = {
        "libjpeg.so": ("usr/lib/libjpeg.so.8.3.2", b"blob"),
        "libz.so": ("usr/lib/libz.so.1", b"blob"),
    }
    monkeypatch.setattr(
        xv_builder,
        "elf_info",
        lambda blob, label: {"soname": "libjpeg.so.8" if "jpeg" in label else "libz.so.1"},
    )
    rewrites = xv_builder._soname_rewrites(resolved)
    # every shipped soname maps to its lib*.so jniLibs name, null-padded
    assert (b"libjpeg.so.8\0", b"libjpeg.so\0\0\0") in rewrites
    assert (b"libz.so.1\0", b"libz.so\0\0\0") in rewrites


def test_soname_rewrites_are_applied_to_the_blob(monkeypatch):
    sonames = {"libjpeg.so": "libjpeg.so.8"}
    monkeypatch.setattr(xv_builder, "elf_info", lambda blob, label: {"soname": sonames[label]})
    rewrites = xv_builder._soname_rewrites({"libjpeg.so": ("x", b"b")})
    rewritten = xv_builder._rewrite(b"needs \0libjpeg.so.8\0 here", rewrites)
    assert b"libjpeg.so.8" not in rewritten
    assert b"libjpeg.so\0\0\0" in rewritten


# ── pin-set integrity (what CI fetches, sha-verified) ────────────────────────


def test_prefix_rewrite_points_xvnc_at_our_app_dir():
    """The device-fatal lock dir is a COMPILED-IN Termux prefix path; the builder
    rewrites it in place (SAME byte length — a trailing slash keeps the "/tmp"
    suffix intact) to our app dir, which the runtime creates before start."""
    blob = b"junk\0/data/data/com.termux/files/usr/tmp/.tX%d-lock\0tail"
    rewritten = xv_builder._rewrite_prefixes(blob)
    assert b"/data/data/com.termux/files/usr" not in rewritten
    assert f"/data/data/{xv_builder._APP_ID}//tmp/.tX%d-lock".encode() in rewritten
    assert len(rewritten) == len(blob)  # in place, nothing shifts


def test_pin_sets_match_across_arches():
    aarch64 = set(xv_builder._PINNED_SOURCES["aarch64"]["packages"])
    x86_64 = set(xv_builder._PINNED_SOURCES["x86_64"]["packages"])
    assert aarch64 == x86_64
    pa_aarch64 = set(pa_builder._PINNED_SOURCES["aarch64"]["packages"])
    pa_x86_64 = set(pa_builder._PINNED_SOURCES["x86_64"]["packages"])
    assert pa_aarch64 == pa_x86_64


def test_every_pin_is_a_64_hex_sha256():
    for builder in (xv_builder, pa_builder):
        for arch, spec in builder._PINNED_SOURCES.items():
            for pkg, (rel, sha) in spec["packages"].items():
                assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), (
                    f"{arch}/{pkg}: bad sha256"
                )
                assert rel.startswith("pool/main/"), f"{arch}/{pkg}: odd repo path"


def test_pool_routing_matches_the_termux_repos():
    """tigervnc/xorg-xkbcomp/xkeyboard-config/libfontenc live in the x11 repo;
    everything else comes from main (a wrong pool is a CI 404)."""
    for pkg in xv_builder._X11_PACKAGES:
        assert pkg in xv_builder._PINNED_SOURCES["aarch64"]["packages"]
    main_pkgs = set(xv_builder._PINNED_SOURCES["aarch64"]["packages"]) - xv_builder._X11_PACKAGES
    assert "openssl" in main_pkgs and "libgnutls" in main_pkgs


def test_platform_tags_are_the_underscore_android_form():
    """pip silently skips the dash form (android_24_arm64-v8a) — the underscore
    tag is the whole reason our payload wheels resolve."""
    for builder, version in (
        (xv_builder, xv_builder.XVNC_VERSION),
        (pa_builder, pa_builder.PA_VERSION),
    ):
        for spec in builder._PINNED_SOURCES.values():
            expected = f"py3-none-android_24_{spec['platform']}"
            assert spec["platform"] in ("arm64_v8a", "x86_64")
            wheel_name = f"{builder.DIST_NAME}-{version}-{builder.BUILD_TAG}-{expected}.whl"
            assert "android_24_arm64_v8a" in wheel_name or "android_24_x86_64" in wheel_name
            assert "-" not in expected.split("android_24_")[1]


# ── noVNC vendoring (the committed viewer assets) ────────────────────────────


def test_fetch_novnc_vendors_the_full_upstream_viewer(monkeypatch, tmp_path):
    """The viewer is upstream noVNC VERBATIM: vnc.html + app/ + core/ +
    vendor/ + the runtime-referenced JSON files. Deployment defaults are
    written over defaults.json (upstream's own override), and our hand-rolled
    index.html is gone."""
    version = "9.9.9-test"
    files = {
        f"noVNC-{version}/core/rfb.js": b"export default class RFB {}",
        f"noVNC-{version}/vendor/pako/lib/zlib/inflate.js": b"export const x = 1;",
        f"noVNC-{version}/app/ui.js": b"export default class UI {}",
        f"noVNC-{version}/app/styles/base.css": b"body{}",
        f"noVNC-{version}/LICENSE.txt": b"MPL-2.0",
        f"noVNC-{version}/vnc.html": b"<html>upstream UI</html>",
        f"noVNC-{version}/package.json": b'{"version": "x"}',
        f"noVNC-{version}/defaults.json": b"{}",
        f"noVNC-{version}/mandatory.json": b"{}",
        f"noVNC-{version}/docs/EMBEDDING.md": b"not runtime",
        f"noVNC-{version}/po/noVNC.pot": b"not runtime",
        f"noVNC-{version}/vnc_lite.html": b"alternate page",
    }
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, blob in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))
    blob = buf.getvalue()

    monkeypatch.setattr(fetch_novnc, "NOVNC_VERSION", version)
    monkeypatch.setattr(
        fetch_novnc,
        "TARBALL_URL",
        f"https://example.invalid/noVNC-{version}.tar.gz",
    )
    monkeypatch.setattr(
        fetch_novnc,
        "TARBALL_SHA256",
        __import__("hashlib").sha256(blob).hexdigest(),
    )
    monkeypatch.setattr(fetch_novnc, "fetch", lambda: blob)
    monkeypatch.setattr(fetch_novnc, "DEST", tmp_path / "novnc")

    assert fetch_novnc.main() == 0
    dest = tmp_path / "novnc"
    for rel in (
        "core/rfb.js",
        "vendor/pako/lib/zlib/inflate.js",
        "app/ui.js",
        "app/styles/base.css",
        "vnc.html",
        "package.json",
        "mandatory.json",
        "LICENSE.txt",
    ):
        assert (dest / rel).is_file(), rel
    # defaults.json is OUR deployment override, not upstream's empty {}
    defaults = json.loads((dest / "defaults.json").read_text(encoding="utf-8"))
    assert defaults["resize"] == "remote"
    assert defaults["reconnect"] is True
    provenance = (dest / "PROVENANCE").read_text(encoding="utf-8")
    assert version in provenance and "sha256" in provenance
    # Non-runtime upstream payloads stay out.
    assert not (dest / "docs").exists()
    assert not (dest / "po").exists()
    assert not (dest / "vnc_lite.html").exists()
