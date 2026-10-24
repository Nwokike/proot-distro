# tests/test_version_sync.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_version_sync.py · src/core/constants.py · src/core/changelog.py · pyproject.toml · version.json · .github/workflows/app.yml · docs/decisions.md · .venv/lib/python3.14/site-packages/ · Date: 2026-10-24

## What it does / how the app uses it

tests/test_version_sync.py is the release-identity guard: four tests assert that pyproject.toml ([project].version line 5, [tool.flet].build_number line 26), the runtime constants (src/core/constants.py:11-12), the bundled changelog (src/core/changelog.py:5-13), the update feed (version.json), and the CI workflow defaults (.github/workflows/app.yml:19-24, 33-34) all agree on version "1.0.0" / build 1. The same five sources are cross-checked again in CI at .github/workflows/app.yml:59-106 ("Release identity consistency" step, run before `uv run pytest` at :108). Empirically: `uv run pytest tests/test_version_sync.py -q` → 4 passed.

## Findings

### F1 · P2 · version.json["version"] is never compared to APP_VERSION in the test
- **Where:** tests/test_version_sync.py:34-41; version.json:3; src/core/constants.py:11; pyproject.toml:5; .github/workflows/app.yml:88-99 (CI does check this)
- **What:** test_feed_never_leads_the_shipped_build asserts only `int(feed["build_number"]) <= APP_BUILD_NUMBER` (:39) and `len(feed["release_notes"]) > 80` (:40). It never reads feed["version"], so a feed advertising version "9.9.9" (or anything) passes as long as build_number <= 1 and notes exceed 80 chars. The CI identity step does compare version.json vs pyproject (app.yml:91-99), but that step runs in CI only; the pytest gate on PRs (:108) has the hole.
- **Evidence:** full read of tests/test_version_sync.py — `feed["version"]` does not occur anywhere in the file; version.json:3 declares "version": "1.0.0".
- **Fix / opportunity:** add `assert feed["version"] == APP_VERSION == _pyproject()["project"]["version"]` to test_feed_never_leads_the_shipped_build (string compare consistent with :25, or PEP 440 per F2).
- **Risk if ignored:** a stale or ahead feed ships; the update flow could offer users a version that does not exist.

### F2 · P2 · Raw string comparison throughout; no PEP 440, although packaging 26.3 is installed and unused
- **Where:** tests/test_version_sync.py:25,30; .github/workflows/app.yml:85-86; .venv/lib/python3.14/site-packages/packaging/version.py (exists, packaging 26.3); pyproject.toml:9-15, 78-84 (no packaging entry)
- **What:** :25 compares version strings with `==`; :30 uses dict key membership (`APP_VERSION in CHANGELOG`); CI's `vt(s) = tuple(int(x) for x in s.split("."))` (app.yml:85-86) is a hand-rolled dotted-int comparator: `vt("1.0.0a1")` → `int("0a1")` raises ValueError and would fail the CI quality job — whether such a string can ever reach these fields is UNVERIFIED (all version inputs are currently hard-coded constants). PEP 440 equivalence (1.0 == 1.0.0, epoch, post, dev, pre-release) is honored nowhere.
- **Evidence:** app.yml:85-86 read directly; .venv packaging/version.py exists; pyproject dependency lists contain no packaging.
- **Fix / opportunity:** compare with `packaging.version.Version` (already in .venv; adding it as a direct dependency needs owner sign-off per D-003, docs/decisions.md:13) or at least wrap vt() in try/except with a clear error.
- **Risk if ignored:** false pass/fail at version boundaries; unhandled crash in the CI identity step if a pre-release-style string ever appears.

### F3 · P2 · Changelog head freshness is not asserted; notes_for() fallback masks a stale head
- **Where:** tests/test_version_sync.py:29-31; src/core/changelog.py:16-18; src/core/changelog.py:5-13; src/core/constants.py:11; pyproject.toml:5
- **What:** the test asserts APP_VERSION is a CHANGELOG key (:30) and notes_for(APP_VERSION) is truthy (:31), but never asserts the changelog head (newest key) equals APP_VERSION or pyproject version. changelog.py:18 falls back to `next(iter(CHANGELOG.values()))` for any missing version, so notes_for can never be empty for a non-empty dict — the assertion passes even if the head is stale. CHANGELOG content is also never compared to version.json release_notes (version.json:6).
- **Evidence:** changelog.py:18 fallback; test has only the two assertions at :30-:31; dict literal at :5-13 has a single key "1.0.0" so ordering cannot be checked today.
- **Fix / opportunity:** add `assert max(CHANGELOG) == APP_VERSION == _pyproject()["project"]["version"]` and `assert notes_for(APP_VERSION) == CHANGELOG[APP_VERSION]`; optionally compare with feed release_notes when version.json exists.
- **Risk if ignored:** users see a stale "What's New" for the shipped build.

### F4 · P1 · flet-proot pin (pyproject.toml:52) is outside the identity chain; D-013 content is missing
- **Where:** pyproject.toml:52 (`dependencies = ["flet-proot==5.1.107.98"]` under [tool.flet.android]); docs/decisions.md:57 ("One-commit lock edit per D-013"); tests/test_version_sync.py (no mention of flet-proot); .github/workflows/app.yml:59-106 (no mention of flet-proot)
- **What:** D-013 is referenced but its decision block does not exist in docs/decisions.md — the file contains D-001…D-010, open decisions O-1…O-9, then D-015…D-017 (full read; repo-wide grep confirms D-013/D-014 occur only at :57 and :66). The flet-proot native payload pin is part of Android release identity, yet neither the test nor the CI identity step cross-checks it against any source of truth. What D-013 originally ruled (beyond the :57 summary) is UNVERIFIED; whether a canonical flet-proot pin source exists outside pyproject.toml is UNVERIFIED.
- **Evidence:** grep over docs/decisions.md shows only references at :57/:66, no decision blocks; pyproject.toml:52.
- **Fix / opportunity:** restore/document D-013 (and D-014, referenced as superseded at :66); add the flet-proot pin to the CI identity step or a test once a canonical source is identified.
- **Risk if ignored:** silent pin drift between pyproject.toml, uv.lock, and built APK/AAB payloads.

### F5 · P3 · Workflow-default assertion is an unanchored substring match
- **Where:** tests/test_version_sync.py:43-46; .github/workflows/app.yml:19-20, 33
- **What:** `assert f'default: "{APP_VERSION}"' in workflow` (:45) matches the literal string anywhere in app.yml — it cannot tell the workflow_dispatch input default (app.yml:20) from the env default (app.yml:33, `'1.0.0'`) or a comment. A drifted input default would still pass if the env default stayed correct.
- **Evidence:** app.yml:19-20 (`build_version` input, `default: "1.0.0"`), :33 (`BUILD_VERSION: ${{ inputs.build_version || '1.0.0' }}`).
- **Fix / opportunity:** narrow the assertion to the workflow_dispatch block (adjacent-line match on `build_version:`) or parse the YAML.
- **Risk if ignored:** low — defaults are controlled values; cosmetic robustness only.

## Identity-chain cross-check summary

| Link | Checked in test | Checked in CI (app.yml:59-106) | Status |
|---|---|---|---|
| pyproject [project].version vs APP_VERSION | :25 | :78-79 | linked |
| [tool.flet].build_number vs APP_BUILD_NUMBER | :26 | :82-83 | linked |
| APP_BUILD_NUMBER vs BUILD_NUMBER env | — | :80-81 | linked |
| version.json build_number <= APP_BUILD_NUMBER | :39 | :92-93 | linked |
| version.json version vs pyproject version | **absent** (:34-41) | :91-99 | MISSING in test (F1) |
| version.json release_notes vs changelog notes | **absent** (only len > 80 at :40) | — | MISSING (F1/F3) |
| changelog head == APP_VERSION | **absent** (:29-31) | — | MISSING (F3) |
| flet-proot pin (pyproject.toml:52) | **absent** | **absent** | MISSING (D-013 governs, content UNVERIFIED) (F4) |

## Verified-good list

- All four tests pass: `uv run pytest tests/test_version_sync.py -q` → 4 passed (no failures; current data all "1.0.0"/build 1).
- test_runtime_constants_match_pyproject (:23-26) exactly matches pyproject.toml:5 and :26 to src/core/constants.py:11-12, with int coercion on the build number.
- test_workflow_defaults_match (:43-46) matches the literal workflow_dispatch defaults at app.yml:20 and :23.
- test_feed_never_leads_the_shipped_build correctly skips when version.json is absent per house policy (:36-37).
- tomllib (stdlib, Python 3.14+), packaging 26.3 (.venv/.../site-packages/packaging/version.py), pytest 9.1.1 (.venv/.../site-packages/pytest) are all installed — no missing stdlib/dependency for any proposed fix.
- flet 1.0.4 installed in .venv (flet-1.0.4.dist-info); no ft.* API is exercised by this test, so no Flet/HALLUCINATION risk applies.

## Unverified

- The original D-013 ruling (flet-proot lock-edit workflow) — entry referenced at docs/decisions.md:57 but the decision block itself does not exist in the file.
- D-014 — referenced only as "superseded" at docs/decisions.md:66; no content present anywhere in the repo (repo-wide grep over *.md, *.py, *.yml, *.toml confirms).
- Whether a canonical flet-proot pin source exists outside pyproject.toml:52.
- Whether a pre-release-style version string can ever reach app.yml:85-86 `vt()` (all version inputs are currently hard-coded constants); the ValueError crash on `int("0a1")` is Python semantics, not an observed failure.
