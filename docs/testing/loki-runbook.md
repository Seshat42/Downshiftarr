# Loki Plex Integration Runbook

Last reviewed: 2026-05-28

Loki is the local Windows Plex server used for opt-in real integration tests. This lane is intentionally separate from deterministic WSL verification because WSL currently cannot reach Windows Plex at `127.0.0.1:32400`.

## Guardrails

- Only use `http://127.0.0.1:32400` or `http://localhost:32400`.
- The identity guard must pass before any library refresh or enforcement scenario.
- Never run this lane against Bragi, TooB, Plex relay, hosted Plex, or production servers.
- Use generated media only.
- Use a dedicated library such as `Downshiftarr Test Rig`.
- Set `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1` only when you intend to mutate the Loki test library or terminate Downshiftarr test sessions.

## Configure

From Windows PowerShell:

```powershell
Copy-Item .\Downshiftarr.test.env.example .\Downshiftarr.test.env
notepad .\Downshiftarr.test.env
```

Fill in local values:

```text
DOWNSHIFTARR_LOKI_PLEX_URL=http://127.0.0.1:32400
DOWNSHIFTARR_LOKI_EXPECTED_MACHINE_ID=165cc0187d76937eb104da8d46437bf5443ec503
DOWNSHIFTARR_LOKI_TEST_LIBRARY_NAME=Downshiftarr Test Rig
DOWNSHIFTARR_TEST_MEDIA_DIR=artifacts/plex-test-media
DOWNSHIFTARR_LOKI_PLEX_TOKEN=YOUR_PLEX_TOKEN_HERE
DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=0
```

`Downshiftarr.test.env` is ignored by Git. Do not paste real tokens into docs, screenshots, shell history examples, local support notes, or scan artifacts.

## Non-Destructive Proof

This verifies the local identity guard and generates media without refreshing a Plex library:

```powershell
.\scripts\testing\Invoke-LokiIntegration.ps1
```

Expected result:

- Loki identity is verified.
- Media appears under `artifacts/plex-test-media/`.
- JSON output reports `status` as `guard-and-media-only`.

## Library Refresh

Create a dedicated Plex movie library named `Downshiftarr Test Rig` that points at the generated media directory, or allow the runner to try to create it:

```powershell
.\scripts\testing\Invoke-LokiIntegration.ps1 -Destructive -CreateLibrary
```

The runner aborts unless:

- `DOWNSHIFTARR_LOKI_ALLOW_DESTRUCTIVE=1`
- `DOWNSHIFTARR_LOKI_PLEX_TOKEN` is present
- Loki identity matches the expected machine identifier
- The URL is loopback

## Browser Smoke

Browser smoke is optional. Install Playwright in the Windows Python environment if needed, then set:

```text
DOWNSHIFTARR_LOKI_BROWSER=1
DOWNSHIFTARR_LOKI_BROWSER_HEADLESS=1
```

Run:

```powershell
.\scripts\testing\Invoke-LokiIntegration.ps1 -Browser
```

The current smoke validates the local Plex identity page from Chromium. Playback-specific browser automation should only be added with local auth hygiene: no saved screenshots, traces, cookies, or tokens unless reviewed and scrubbed.

## Troubleshooting

- If WSL cannot reach Plex, use the PowerShell runner. This is expected for the current host.
- If the identity guard fails, stop. Verify you are not pointing at Bragi, TooB, relay, or another Plex host.
- If FFmpeg is missing, install it in the shell running the lane. WSL currently has FFmpeg; Windows has `C:\ffmpeg\bin`.
- If the Plex library is not found, create `Downshiftarr Test Rig` manually in Plex Web or pass `-CreateLibrary`.
- If a destructive run touches anything outside generated media, stop and treat it as a test-rig bug.
