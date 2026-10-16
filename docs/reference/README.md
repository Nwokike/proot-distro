# Reference library — proot-distro-flet

Context-preservation library (animepahe-tv convention). Each file is a distilled, source-verified study so the project can be resumed cold by a human or another agent.

**Reading order for a cold start:** [`../roadmap.md`](../roadmap.md) → this index → app files → dep files → [`../decisions.md`](../decisions.md) → [`../testing-findings.md`](../testing-findings.md).

All studies verified 2026-10-16 against installed source (`.venv/Lib/site-packages`) or the local repos — file:line refs are kept in the study summaries below; original swarms ran 17 sub-agents (6 repo studies + 11 dependency studies covering all 48 locked packages).

| File | Covers | Why it matters |
|---|---|---|
| [app-sherlock.md](app-sherlock.md) | Sherlock app (production standard) | The reference for how a new house app is shaped |
| [app-ddgs.md](app-ddgs.md) | DDGS app | Floor-pin style, honest-import test, version discipline |
| [app-collabshell.md](app-collabshell.md) | CollabShell app | Notebook I/O formats; the *only* shipped flet-terminal consumer; remote-PTY lesson; test template |
| [app-ffmpeg.md](app-ffmpeg.md) | FFmpeg Lite app | The two-artifact native-shipment shape we mirror; probe-gating |
| [app-data-formulator.md](app-data-formulator.md) | Data Formulator app | The cleanest sole-importer facade + constructor injection (zero patches) |
| [dep-flet.md](dep-flet.md) | flet 1.0.4 | Extension mechanism, lockstep reinstall danger, run transport |
| [dep-flet-terminal.md](dep-flet-terminal.md) | flet-terminal 0.3.9 wheel + trio comparison + refactor blueprint | M1's entire basis |
| [dep-flet-ads.md](dep-flet-ads.md) | flet-ads 1.0.4 (official) | Pair-bump rule; platform gating; UMP consent |
| [dep-proot-distro.md](dep-proot-distro.md) | proot-distro 5.10.0 wheel | Integration contract: env, surfaces, progress, failure modes |
| [dep-flet-cli.md](dep-flet-cli.md) | flet-cli 1.0.4 | Verified build flags; what does NOT exist |
| [dep-flet-build-host.md](dep-flet-build-host.md) | flet-desktop / flet-platform-assets / pillow | Build-host-only; icon pipeline |
| [dep-cookiecutter-stack.md](dep-cookiecutter-stack.md) | cookiecutter + 18 deps | Template mechanics + trust boundary |
| [dep-flet-runtime-utils.md](dep-flet-runtime-utils.md) | msgpack / oauthlib / repath / six | msgpack = wire protocol; the 1.2.3 pin trap |
| [dep-httpx-cluster.md](dep-httpx-cluster.md) | httpx / httpcore / h11 / anyio / idna / certifi / typing-extensions | Dormant unless OAuth; certifi trust-store note |
| [dep-test-and-lint-stack.md](dep-test-and-lint-stack.md) | pytest stack / ruff / watchdog | Config notes for CI parity |
| [../requests/proot-mobile-forge-request.md](../requests/proot-mobile-forge-request.md) | Filed package request | flet-dev/flet discussions #6979 |

**Private-phase note:** per the house extension standard, these docs live in-repo while the repo is private; review before any public release.
