# Python dependencies and how to update them

The Flet family is pinned as **one coordinated set**: every extension declares
an exact `flet==X`, so a range in `pyproject.toml` can resolve a different core
and fail the build (or worse, the device). Move all of them in one commit.

## Runtime set

| Package | Pin | Why |
|---|---|---|
| `flet` | exact | UI framework |
| `flet-ads` | exact, same as flet | banner/interstitial/consent |
| `flet-notifications` | exact, same as flet | foreground service + notifications |
| `flet-webview` | exact, same as flet | (kept for platforms without the noVNC viewer) |
| `flet-audio-recorder` | exact, same as flet | RECORD_AUDIO grant |
| `flet-terminal` | its own version (`0.4.2`) | terminal widget; depends on bare flet |
| `proot-distro` | `>=5.10.3` | container engine (pure Python orchestrator) |
| `aiohttp` | `>=3.14` | display stream server (has Android wheels) |
| `httpx` | `>=0.28.1` | release-feed check |

Everything else (anyio, httpcore, h11, certifi, idna, msgpack, repath, six,
yarl, multidict, frozenlist, propcache, attrs, aiosignal, aiohappyeyeballs,
oauthlib, tzdata, …) is a transitive of the above. The full resolved graph is
`uv.lock`; the license/provenance table is generated into
`THIRD-PARTY-SOURCES.md`.

## Update procedure

1. Edit the pin(s) in `pyproject.toml` — **all Flet packages together**.
2. `uv lock` (or `uv lock --upgrade-package <name>`), then `uv sync`.
3. Bump `README.md`'s Flet badge if the family version changed.
4. Run the gates:
   ```sh
   uv run ruff check src tests scripts
   uv run ruff format --check src tests scripts
   uv run python -m pytest -q -m "not live"
   uv run python tests/check_flet_api.py
   ```
5. `tests/test_imports_vs_deps.py` enforces that `src/` only imports declared
   dependencies; `tests/test_version_sync.py` enforces the app version identity.
6. Ship: commit, delete + re-push the `v*` tag (CI builds the wheels and APKs).

## Rules learned the hard way

- Never add a Python package that has native code without checking for an
  Android wheel on `pypi.flet.dev`/PyPI.
- `flet-desktop`, `flet-cli`, `pytest`, `ruff` are dev-only; a guard test
  forbids importing them from `src/`.
- `jnius` is provided by the Flet/Chaquopy runtime and is **not** a uv
  dependency.
- `certifi` is transitive but functionally required (OCI TLS via
  `SSL_CERT_FILE`).
