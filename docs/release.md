# Release process

One page, so nothing is folklore.

## Version truth

Four places must agree before a release (CI's `quality` job fails otherwise):

| Where | Field |
| --- | --- |
| `pyproject.toml` | `project.version`, `tool.flet.build_number` |
| `src/core/constants.py` | `APP_VERSION`, `APP_BUILD_NUMBER` |
| workflow env | `BUILD_VERSION`, `BUILD_NUMBER` fallbacks |
| `version.json` | `version` + `build_number` (the in-app update feed, held back until the release is live) |

## Building

`flet build` never runs locally. Push the commit, then **delete and re-push the
`v*` tag** — that is what triggers GitHub Actions:

```bash
git push
git tag -d v1.2.0 && git push origin :refs/tags/v1.2.0
git tag v1.2.0 && git push origin v1.2.0
```

## Release notes

The GitHub release body is generated, never written by hand:

1. `src/core/changelog.py` — `CHANGELOG[version]` bullet list. This is the same
   entry the in-app **Release notes** dialog shows.
2. `scripts/generate_release_notes.py` renders it to `release_notes.md`.
3. The workflow's `prepare-release` job uploads that file as `body_path`
   (lm-router's pattern).

So: edit the changelog, tag, and both the app and the GitHub release show the
same notes.

## Checklist before tagging

```bash
uv run ruff check src tests scripts/*.py
uv run ruff format --check src tests scripts/*.py
uv run pytest -m "not live"
for f in $(find src -name "*.py"); do uv run --no-sync python tests/check_flet_api.py "$f"; done
```

Then an **independent verifier** pass on the exact tree: a fresh reviewer checks
every Flet constructor keyword against the installed package (not just call
chains), reads the diff for behavioural regressions, and must return PASS.
Only then the tag.
