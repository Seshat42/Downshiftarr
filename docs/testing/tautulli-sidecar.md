# Downshiftarr Tautulli Sidecar

Last reviewed: 2026-05-28

The local Tautulli sidecar is an isolated Docker test service for Downshiftarr only. It is not a shared host service and must not touch any existing project container, config, volume, library, or port.

## Isolation Rules

- Container name: `downshiftarr-tautulli`.
- Probe container name: `downshiftarr-loki-probe`.
- Required labels: `downshiftarr.project=Downshiftarr`, `downshiftarr.role=tautulli`, and `downshiftarr.managed=true`.
- Host binding: `127.0.0.1:18181`, or the first free port in `18182-18190`.
- Config path: ignored `artifacts/local-tautulli/config/`.
- Env file: ignored `Downshiftarr.test.env`.
- Default image: `linuxserver/tautulli:latest` from Docker Hub. Do not use `ghcr.io` as a default dependency.
- No restart policy is set by default.

The manager refuses to stop, start, or remove a container named `downshiftarr-tautulli` unless the required Downshiftarr labels are present.

## Commands

From Windows PowerShell:

```powershell
python -m scripts.testing.tautulli_manager probe-loki
python -m scripts.testing.tautulli_manager up --env-file Downshiftarr.test.env
python -m scripts.testing.tautulli_manager status
python -m scripts.testing.tautulli_manager down
python -m scripts.testing.tautulli_manager rm
```

`probe-loki` runs a temporary labeled container and verifies Docker can reach `http://host.docker.internal:32400/identity`. `up` refuses to start Tautulli if this probe fails.

## Configuration

`up` verifies Loki from the host, starts the sidecar if needed, waits for Tautulli to generate local config, then writes only sidecar-local settings:

- Loki PMS host inside Docker: `host.docker.internal`.
- Loki PMS port: `32400`.
- Loki machine identifier: `165cc0187d76937eb104da8d46437bf5443ec503`.
- Tautulli update checks disabled: `check_github=0` and `check_github_on_startup=0`.
- Tautulli API key copied into ignored `Downshiftarr.test.env` as both `DOWNSHIFTARR_TAUTULLI_APIKEY` and `TAUTULLI_APIKEY`.

Do not paste real tokens into docs, screenshots, shell history examples, or saved artifacts.
