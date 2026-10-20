"""Version drift guard — pyproject, the runtime constants, the feed, the
changelog and the workflow defaults must all agree."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from core.changelog import CHANGELOG, notes_for
from core.constants import APP_BUILD_NUMBER, APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_runtime_constants_match_pyproject():
    proj = _pyproject()
    assert proj["project"]["version"] == APP_VERSION
    assert int(proj["tool"]["flet"]["build_number"]) == APP_BUILD_NUMBER


def test_changelog_has_an_entry_for_the_current_version():
    assert APP_VERSION in CHANGELOG
    assert notes_for(APP_VERSION)


def test_feed_never_leads_the_shipped_build():
    feed = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    assert int(feed["build_number"]) <= APP_BUILD_NUMBER
    assert len(feed["release_notes"]) > 80


def test_workflow_defaults_match():
    workflow = (ROOT / ".github" / "workflows" / "app.yml").read_text(encoding="utf-8")
    assert f'default: "{APP_VERSION}"' in workflow
    assert f'default: "{APP_BUILD_NUMBER}"' in workflow
