"""The proot-distro integration contract, proven without a device.

Covers the three things that actually break in the field:
  1. env-before-import (upstream constants are import-time);
  2. the sole-importer rule (one module may import proot_distro);
  3. the argparse namespaces (field-for-field against upstream's parser).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── 1. the sole-importer rule ────────────────────────────────────────────────


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_only_proot_service_imports_proot_distro():
    importers = [
        str(p.relative_to(ROOT)).replace("\\", "/")
        for p in sorted((ROOT / "src").rglob("*.py"))
        if "proot_distro" in _imports_of(p)
    ]
    assert importers == ["src/services/proot_service.py"], (
        "proot_distro is imported outside the facade: " + ", ".join(importers)
    )


def test_screens_never_import_proot_distro_directly():
    # The transfer boundary is plain data — screens call the facade only.
    for path in (
        *sorted((ROOT / "src" / "screens").rglob("*.py")),
        ROOT / "src" / "app_controller.py",
    ):
        assert "proot_distro" not in _imports_of(path)


# ── 2. namespaces match upstream's parser ────────────────────────────────────


def test_install_namespace_matches_parser():
    pytest.importorskip("proot_distro")
    from proot_distro import parser

    from services.proot_service import _ns_install

    args = parser.build_parser().parse_args(["install", "debian:bookworm", "-n", "debian"])
    handled = vars(args)
    # Every field upstream's install handler reads must exist on the namespace.
    for field in ("image_ref", "custom_container_name", "override_arch", "allow_insecure"):
        assert field in handled, f"namespace missing {field}"
    assert handled["image_ref"] == "debian:bookworm"
    assert handled["custom_container_name"] == "debian"
    assert handled["override_arch"] is None and handled["allow_insecure"] is False
    # Our namespace must supply every field upstream reads — a subset of the
    # full parser namespace, which also carries global flags (command/help/quiet).
    assert set(vars(_ns_install("debian:bookworm", "debian"))) <= set(handled)


def test_remove_and_reset_namespaces():
    pytest.importorskip("proot_distro")
    from services.proot_service import _ns_remove, _ns_reset

    r, s = vars(_ns_remove("debian")), vars(_ns_reset("debian"))
    assert r["target"] == "debian" and r["image"] is False
    assert s["container_name"] == "debian"


# ── 3. env contract ──────────────────────────────────────────────────────────


def test_env_contract_is_import_safe():
    from core import storage_paths

    env = storage_paths.env_contract()
    for key in (
        "TERMUX_APP__PACKAGE_NAME",
        "TERMUX__PREFIX",
        "TERMUX__HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "PROOT_TMP_DIR",
    ):
        assert env.get(key), f"{key} missing/empty"
    # The containers root must live under our XDG home, never a Termux default.
    assert str(storage_paths.containers_dir()).startswith(env["XDG_DATA_HOME"])
    assert "com.termux" not in env["TERMUX_APP__PACKAGE_NAME"]


def test_bootstrap_is_idempotent_and_installs_shims(monkeypatch):
    pytest.importorskip("proot_distro")
    monkeypatch.delenv("PROOT_F2FS_WORKAROUND", raising=False)
    from services import proot_service

    monkeypatch.setattr(proot_service, "_BOOTSTRAPPED", False, raising=False)
    proot_service.bootstrap()
    assert proot_service._BOOTSTRAPPED is True
    import os

    assert os.environ.get("TERMUX_APP__PACKAGE_NAME") == "ng.kiri.prootdistro"
    proot_service.bootstrap()  # second call is a no-op


# ── 4. desktop fallback ──────────────────────────────────────────────────────


def test_available_is_false_off_device(monkeypatch):
    """On a desktop without proot_distro importable, the service says so."""
    from services import proot_service

    monkeypatch.setattr(proot_service, "_BOOTSTRAPPED", False, raising=False)
    monkeypatch.setitem(sys.modules, "proot_distro", None)  # poison the import
    assert proot_service.available() is False
    monkeypatch.delitem(sys.modules, "proot_distro", raising=False)


def test_dev_only_packages_are_not_imported_from_src():
    """The build-host tree must never reach the app (licensing A4)."""
    dev_only = {
        "chardet",
        "cookiecutter",
        "pytest",
        "ruff",
        "flet_cli",
        "flet_desktop",
        "binaryornot",
        "jinja2",
        "requests",
    }
    for path in sorted((ROOT / "src").rglob("*.py")):
        found = _imports_of(path) & dev_only
        assert not found, f"{path.relative_to(ROOT)} imports dev-only {sorted(found)}"


def test_pull_limit_is_reported_as_policy():
    from services.proot_service import Outcome, is_pull_limit

    limited = Outcome(ok=False, detail="failed", output="HTTP 429 Too Many Requests")
    assert is_pull_limit(limited) is True
    assert is_pull_limit(Outcome(ok=False, detail="boom", output="")) is False
