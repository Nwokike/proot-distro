#!/usr/bin/env python3
"""Fail if the app references any dotted `ft.*` chain that does not exist in
the INSTALLED flet — catches renamed/removed controls and helpers before a
build ever reaches a device.

Caught real M0 bugs: `ft.ElevatedButton` (removed in Flet 1.0) and
`ft.border.all()` (helper removed; use `ft.Border(...)`/`ft.BorderSide(...)`).
Walks FULL attribute chains, so `ft.border.all` and `ft.Icons.PLAY_ARROW` are
both verified member-by-member.

House precedent: the AST namespace guard in the Data Formulator app.

Usage: python tools/check_flet_api.py src/main.py
Exit 0 = every referenced chain exists; 1 = at least one is missing.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def chains(tree: ast.AST) -> set[tuple[str, ...]]:
    """All attribute chains rooted at the name `ft` (e.g. ('Colors','BLACK'))."""
    out: set[tuple[str, ...]] = set()

    def walk(node: ast.AST):
        if isinstance(node, ast.Attribute):
            parts = _flatten(node)
            if parts is not None:
                out.add(parts)
            for child in ast.iter_child_nodes(node):
                walk(child)
        else:
            for child in ast.iter_child_nodes(node):
                walk(child)

    def _flatten(node: ast.Attribute) -> tuple[str, ...] | None:
        parts: list[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name) and cur.id == "ft":
            return tuple(reversed(parts))
        return None

    walk(tree)
    return out


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "src/main.py")
    if not target.exists():
        print(f"target not found: {target}")
        return 2

    import flet

    tree = ast.parse(target.read_text(encoding="utf-8"))
    refs = sorted(chains(tree))

    missing: list[str] = []
    runtime_bound: list[str] = []
    for chain in refs:
        obj = flet
        for i, part in enumerate(chain):
            try:
                if not hasattr(obj, part):
                    missing.append(".".join(("ft", *chain[: i + 1])))
                    break
                obj = getattr(obj, part)
            except RuntimeError:
                # Runtime-context access (e.g. ft.context.page) — the API
                # exists but only resolves inside a running Flet app. The
                # chain prefix up to here is verified; accept it.
                runtime_bound.append(".".join(("ft", *chain[: i + 1])))
                break

    print(f"flet {getattr(flet, '__version__', '?')} — {len(refs)} chain(s) referenced in {target}")
    bad = set(missing)
    for chain in refs:
        dotted = ".".join(("ft", *chain))
        prefix_missing = any(dotted == m or dotted.startswith(m + ".") for m in bad)
        is_runtime = any(dotted == r or dotted.startswith(r + ".") for r in runtime_bound)
        status = "MISSING" if prefix_missing else ("ok*  " if is_runtime else "ok   ")
        print(f"  {status}  {dotted}" + ("  (runtime-context)" if is_runtime and " " else ""))

    if missing:
        print("\nFAIL: referenced flet API does not exist in the installed version:")
        for m in missing:
            print(f"  - {m}")
        return 1
    print("\nOK: every referenced flet API chain exists in the installed version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
