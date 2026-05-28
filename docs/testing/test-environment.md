# Downshiftarr Test Environment

Last reviewed: 2026-05-28

Downshiftarr uses a layered test rig so most behavior is proven deterministically in WSL while real Plex proof remains local, explicit, and guarded.

## Layers

1. Unit tests
   - Fast tests for helpers, parsing, classification, media-height handling, token transport, and argument normalization.
   - Run in WSL and CI.

2. Simulated integration tests
   - Fake Plex sessions, fake Tautulli-shaped events, fake client controls, and representative client profiles.
   - Covers session matching, client discovery, fallback selection, remote-control failure, seek failure, termination fallback, and shim behavior.
   - Run in WSL and CI.

3. Generated-media tests
   - `scripts/testing/generate_media.py` creates synthetic fixtures with FFmpeg under `artifacts/plex-test-media/` by default.
   - Fixtures include 480p SDR, 720p SDR, 1080p SDR, 2160p SDR, 2160p HDR10-like, audio-only-invalid, and malformed metadata.
   - Tests validate width, height, stream presence, manifest entries, and HDR-like metadata with FFprobe.

4. Real Loki Plex integration
   - `scripts/testing/loki_guard.py` validates the Windows loopback Plex identity before any real-server path.
   - `scripts/testing/run_loki_matrix.py` generates media and optionally refreshes a dedicated Loki Plex test library.
   - `scripts/testing/Invoke-LokiIntegration.ps1` is the Windows-side runner because WSL cannot currently reach Windows Plex at `127.0.0.1:32400`.

5. Optional browser smoke
   - `scripts/testing/loki_browser_smoke.py` verifies the local Plex identity from a browser context when Playwright is installed and explicitly enabled.
   - It is disabled by default and should not save authenticated screenshots, traces, or logs without review.

## Pytest Markers

- `unit`: fast pure unit tests with no external services.
- `simulated`: deterministic fake Plex/Tautulli/client tests.
- `media`: generated-media tests that require FFmpeg and FFprobe.
- `loki`: opt-in tests that contact the local Loki Plex server.
- `browser`: opt-in browser smoke tests against local Plex Web.
- `destructive`: opt-in tests allowed to mutate the local Loki Plex test library or terminate test sessions.
- `slow`: intentionally slower tests excluded from tight loops unless selected.

CI runs:

```bash
uv run pytest -m "not loki and not browser and not destructive"
```

Local WSL lanes:

```bash
uv sync --all-groups --python 3.12
uv run pytest -m "not loki and not browser and not destructive"
uv run pytest -m simulated
uv run pytest -m media
```

## Local Files

Tracked examples:

- `Downshiftarr.env.example`: runtime deployment configuration.
- `Downshiftarr.test.env.example`: local test-rig configuration.

Ignored local files and outputs:

- `Downshiftarr.env`
- `Downshiftarr.test.env`
- `artifacts/plex-test-media/`
- runtime logs, security scan outputs, Playwright reports, and pytest caches.

## Safety Rules

- Never scrape, infer, log, screenshot, or commit real Plex tokens.
- Do not run destructive tests unless `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1` is set in a local ignored env file.
- Do not use a non-loopback Plex URL for Loki tests.
- Do not point the real-server lane at Bragi, TooB, relay, hosted, or production Plex instances.
- Generated media is disposable and should live in a dedicated Plex library such as `Downshiftarr Test Rig`.
