# Swarm brief — shared rules for every audit agent

You are one specialist in a large audit swarm. You have exactly ONE job. Do not audit another package or file.

## Ground truth
- The installed environment is the source of truth: `.venv/lib/python3.14/site-packages/` (Linux, Python 3.14.9).
- Existing dependency API studies: `docs/dependency-studies/<package>.md`. They were verified against `.venv` on 2026-10-16. Do NOT re-document the whole package; use the study as prior knowledge and **spot-check every API you rely on** against the installed source with `file:line`.
- App code: `src/`. The app is Flet 1.0.4, state-driven: `@ft.observable AppState` → `@ft.component` views → controller methods. Imperative widget mutation is forbidden (see D-015 in `docs/decisions.md`).
- House standards: `docs/reference/house-ui-design.md`, `docs/reference/app-*.md`, `docs/reference/dep-*.md`.
- The goal is not "more dependencies". It is **using capabilities we already ship** instead of hand-rolling them, and finding real bugs. Do not propose new packages (the dependency set is frozen by D-003).

## Non-negotiable rules
1. **Do not modify application code, tests, pyproject, or docs outside your own report file.** You are read-only except for writing your one report.
2. **Evidence or it did not happen.** Every defect or opportunity must cite `file:line` from the app and `file:line` from `.venv` (or a runnable command whose output you paste). No guesses. If you could not verify something, label it `UNVERIFIED`.
3. **Check the Flet API.** Every `ft.*`, `@ft.component`, observable, service, event, and property claim must be verified against the installed `flet` source. Flag anything that does not exist or has different semantics as `HALLUCINATION`.
4. **Respect the declared architecture.** One upstream importer per service; no monkeypatches; no vendoring; no forks. Prefer public APIs and constructor injection.
5. Check the actual installed version, not the docs' version. Notable drift: `flet-terminal` study is 0.3.9, installed is **0.4.0**; `msgpack` is locked at **1.2.3** while Android wheels are documented as 1.1.x. Verify before asserting.

## Report contract
Write exactly one Markdown file at the path assigned in your prompt. Use this shape:

```markdown
# <assignment> — audit

**Verdict:** PERFECT | IMPROVE | BUG | HALLUCINATION | MIXED
**Confidence:** high | medium | low
**Scope:** <files read> · **Date:** 2026-10-20

## What it does / how the app uses it
<short, concrete>

## Findings
### F1 · <severity P0/P1/P2/P3> · <title>
- **Where:** `src/...:line` (and `.venv/...:line` for API claims)
- **What:** <observed behavior vs expected>
- **Evidence:** <quote or command output>
- **Fix / opportunity:** <specific, minimal, architecture-respecting>
- **Risk if ignored:** <user-visible impact>

## Missed capabilities (dependency audits only)
<capability in the dependency the app does not use · API location · proposed integration point · value vs cost>

## Verified-good list
<things you checked that are correct, so the synthesis does not re-open them>

## Unverified
<anything you could not prove>
```

Severity: P0 = crash/data loss/build break; P1 = user-visible broken behavior or security/compliance; P2 = correctness/robustness/UX defect; P3 = polish/opportunity.

Return to the orchestrator only: verdict, finding count by severity, and the single most important finding. Keep it under 12 lines.
