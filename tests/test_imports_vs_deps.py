"""Every import in src/ must be declared in [project].dependencies.

`flet build` resolves ONLY the project dependencies; a desktop-only import
that isn't declared crashes the packaged app on Android. House pattern: the
DDGS app's guard, proven on real APKs.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _declared() -> set[str]:
    pp = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names: set[str] = set()
    # Project deps + the platform tables flet-cli appends at build time
    # (`tool.flet.<platform>.dependencies` — BB:2571-2574).
    deps = list(pp["project"]["dependencies"])
    for platform in ("android", "ios", "macos", "linux", "windows", "web"):
        deps += pp.get("tool", {}).get("flet", {}).get(platform, {}).get("dependencies", [])
    for dep in deps:
        base = dep.split(";")[0].strip()
        base = base.split("[")[0].strip()
        base = base.split()[0]
        base = base.split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("~")[0]
        names.add(base.lower().replace("-", "_"))
    return names


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_imports_all_declared():
    declared = _declared()
    dist_map = _dist_map()
    local = {p.name for p in (ROOT / "src").glob("*") if p.is_dir()}
    local |= {p.stem for p in (ROOT / "src").glob("*.py")}
    missing: set[str] = set()
    for path in sorted((ROOT / "src").rglob("*.py")):
        for mod in _imports(path):
            if mod in local or mod in sys.stdlib_module_names:
                continue
            providers = {d.lower().replace("-", "_") for d in (dist_map.get(mod) or [])}
            if not (providers & declared) and mod.lower() not in declared:
                missing.add(f"{path.relative_to(ROOT)}: {mod}")
    assert not missing, "imports without a declared dependency:\n" + "\n".join(sorted(missing))


def _dist_map() -> dict[str, list[str]]:
    try:
        from importlib import metadata

        return metadata.packages_distributions() or {}
    except Exception:  # the guard must not crash when metadata is unavailable
        return {}
