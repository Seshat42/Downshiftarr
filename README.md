NOTE: This software was originally written by hand via a human, it is now developed with AI assistance.

# Downshiftarr

Downshiftarr is a **Plex 4K/HDR/DV transcode guard** designed to be run from a **Tautulli â€œScriptâ€ notification**.

It can be deployed in two ways:

1) **Downshiftarr.py only** (works anywhere you can run Tautulli script notifications)
   - This is the right choice for restricted environments where you *donâ€™t* have Docker / root access and therefore *cannot* replace the Plex transcoder binary.

2) **Full enforcement (recommended): â€œPlex Transcoderâ€ shim + Downshiftarr.py**
   - The **Plex Transcoder shim** is the **first line of defense**. It runs at the exact moment Plex spawns a transcode job and can **swap the input file** to a compliant version *before the first segment is created*.
   - **Downshiftarr.py** remains the **second line of defense** (Tautulli-driven session enforcement, client switching, termination). Even with the shim installed, **Downshiftarr.py is still required for best results / full compliance**.

Why two layers? Plex clients (especially some smart TV apps) can be....creatively non-compliant. The shim prevents expensive 4K/HDR transcodes from even starting, while Downshiftarr.py handles session-level reality (whatâ€™s actually being played, what the client will accept, and how to terminate if needed).


---

## Contents

- [How it works](#how-it-works)
- [Plex Transcoder shim](#plex-transcoder-shim)
- [Requirements](#requirements)
- [Development setup](#development-setup)
- [Installation](#installation)
- [Tautulli setup](#tautulli-setup)
- [Configuration](#configuration)
- [Logging](#logging)
- [Behavior details](#behavior-details)
- [Troubleshooting](#troubleshooting)

---

## How it works

Downshiftarr:

- Uses the Tautulli event as the **trigger** (and as identifiers: rating key, session id/key, machine id, username).
- Looks up the **actual Plex session** and reads the selected mediaâ€™s **height** and **dynamic range** from Plex.
- Classifies the source as â€œprotectedâ€ if:
  - `height >= MAX_ALLOWED_HEIGHT` (default 2000 â†’ catches 2160p), **or**
  - dynamic range is clearly not SDR (HDR / Dolby Vision / HLG, etc.).

If itâ€™s protected **and** video is being transcoded:
- Pick the best fallback version under the threshold (and typically SDR).
- Remote-control the client via plexapi (`playMedia` + `seekTo` fallbacks).
- If the client keeps transcoding after the first switch, keep stepping down through lower available versions by default, down to 360p when present.
- If downshift fails â†’ terminate the session (Tautulli first; Plex fallback).

Downshiftarr only downshifts across Plex **Versions** of the same release. It must not cross Plex Editions such as theatrical, director's cut, 3D, or special-edition releases. If edition metadata or `{edition-...}` file naming indicates that two files are different editions, Downshiftarr treats them as separate release surfaces and passes through rather than swapping to the wrong cut.

The optional **Plex Transcoder shim** runs *before* Downshiftarr.py ever gets an event:

- Plex spawns `Plex Transcoder` â†’ the shim executes.
- The shim detects whether the transcode input is â€œprotectedâ€ (4K-ish and/or HDR/DV).
- If protected, it tries to **waterfall** to a compliant sibling version (e.g. 1080p SDR).
- If an already downshifted SDR version is still being transcoded, it can continue the waterfall to 720p, 576p, 480p, and 360p versions.
- If no safe sibling is available, it can **fail-closed** immediately so the protected transcode never starts.

Think of it like the movie theater ticket window (shim) + the usher who tears your ticket stub (Downshiftarr.py).

---

## Plex Transcoder shim

**`Plex Transcoder`** (note the space) is a Python shim intended to replace the real Plex binary on Linux.

### What the shim does

- Acts as the **first line of defense** against 4K/HDR/DV video transcodes.
- Runs **synchronously** at transcode spawn time.
- Uses Plexâ€™s local API to locate the media item and its available versions.
- If the source is â€œprotectedâ€, it swaps the transcoderâ€™s `-i <input file>` to a compliant sibling version.
- Optionally rewrites HDR tone-mapping filters when swapping to SDR to avoid wasted CPU and potential SDR color damage.

### Important constraints

- The shim does **not** know session/user/client context the way Downshiftarr.py does.
- The shim should be treated as a **pre-flight guard**, not the whole enforcement system.
- For best results **use the shim *and* Downshiftarr.py together**.

### Installation (Linux / Docker)

This is an advanced install. Rollback plan is provided below.

1) **Locate** your Plex transcoder binary.
   - Common location on Linux: `/usr/lib/plexmediaserver/Plex Transcoder`

2) **Stop Plex Media Server**.

3) **Divert the real transcoder** and preserve it under an explicit name:

```bash
sudo dpkg-divert --package downshiftarr --rename \
  --divert "/usr/lib/plexmediaserver/Plex Transcoder.downshiftarr-real" \
  "/usr/lib/plexmediaserver/Plex Transcoder"
```

4) **Copy this repoâ€™s shim into place** as the new `Plex Transcoder` and make it executable:

```bash
sudo install -m 0755 "/path/to/Downshiftarr/Plex Transcoder" "/usr/lib/plexmediaserver/Plex Transcoder"
sudo chmod 0755 "/usr/lib/plexmediaserver/Plex Transcoder.downshiftarr-real"
```

5) **Ensure `/usr/bin/python3` exists in the environment where Plex runs.**
   - The Linux shim uses an absolute `/usr/bin/python3` shebang so confined Plex services do not depend on `PATH` or `/usr/bin/env` lookup.
   - If Plex runs in Docker, Python must exist **inside the container** at that path or the shim must be installed with an equivalent reviewed wrapper.

6) **Configure the shim** with an external JSON file and point Plex at it through `DOWNSHIFTARR_SHIM_CONFIG`.

7) **Start Plex Media Server**.

### Rollback

If anything goes sideways:

```bash
cd /usr/lib/plexmediaserver
sudo rm -f "Plex Transcoder"
sudo dpkg-divert --package downshiftarr --rename --remove "Plex Transcoder"
```

### Shim configuration

Production shim configuration should be external JSON. Set `DOWNSHIFTARR_SHIM_CONFIG`
to the JSON file path before Plex launches the shim. Bragi stores this under
`/etc/downshiftarr/plex-transcoder-shim.json` so the installed shim binary stays
immutable and reviewable.

Example:

```json
{
  "REAL_TRANSCODER_PATH": "/usr/lib/plexmediaserver/Plex Transcoder.downshiftarr-real",
  "PLEX_URL": "http://10.67.0.2:32400",
  "PLEX_TOKEN_FILE": "/etc/downshiftarr/plex-shim-token",
  "PLEX_HTTP_TIMEOUT_S": 0.35,
  "LOG_FILE": "/var/log/downshiftarr/plex-transcoder-shim.log",
  "CACHE_FILE": "/var/lib/downshiftarr/plex-transcoder-cache.json",
  "KILL_TRANSCODE_IF_NO_FALLBACK": true,
  "KILL_TRANSCODE_IF_UNSURE": false,
  "AUTO_WATERFALL_ON_CONTINUED_TRANSCODE": true,
  "WATERFALL_MIN_HEIGHT": 360
}
```

Key settings youâ€™ll care about first:

- `PLEX_URL` â€“ usually `http://127.0.0.1:32400` inside the Plex container/host.
- `PLEX_TOKEN_FILE` â€“ optional absolute path to a root-owned token file readable by the Plex service user. This is preferred when Plex does not provide `X_PLEX_TOKEN` to spawned transcodes because it keeps the token out of argv, examples, and process environment. The file must be regular, non-symlinked, not group/other writable, not other-readable, and owned by root or the Plex service user.
- `PLEX_TOKEN` is deliberately not accepted in the JSON file. Leave the shim binary token-free and provide tokens through `PLEX_TOKEN_FILE` or, when Plex supplies one, `X_PLEX_TOKEN`/`PLEX_TOKEN`/`PLEX_USER_TOKEN` process environment.
- `VERSION_INDEX_FILE` â€“ optional precomputed Plex version index. When present, the shim checks it before live Plex search/section scans so first-segment decisions stay fast.
- `ENABLE_SECTION_SCAN_FALLBACK` â€“ default `True`; if Plex search returns no file-name results, the shim tries the matching library section by location and exact `Part` path. This keeps version lookup working for libraries whose search index hides version filenames.
- `MAX_ALLOWED_HEIGHT` â€“ default `2000` (treats ~2160p as protected).
- `MAX_FALLBACK_HEIGHT` â€“ default `1080`.
- `PREFER_HEIGHTS` â€“ default `(1080, 720, 576, 480, 360)`.
- `FALLBACK_SDR_ONLY` â€“ default `True` (recommended).
- `KILL_TRANSCODE_IF_NO_FALLBACK` â€“ default `True` (strict compliance).
- `KILL_TRANSCODE_IF_UNSURE` â€“ default `True` (strict compliance).
- `AUTO_WATERFALL_ON_CONTINUED_TRANSCODE` â€“ default `True`; keeps stepping down when a lower version may avoid continued transcode pressure.
- `WATERFALL_MIN_HEIGHT` â€“ default `360`.

There are additional options for:

- stream layout safety checks (`REQUIRE_STREAM_INDEX_COMPATIBILITY`)
- caching (`ENABLE_CACHE`, `CACHE_TTL_S`)
- performance tweaks (`STRIP_HDR_TONEMAP_FILTERS`, `REMOVE_BITRATE_LIMITS`)

Keep these values aligned with `Downshiftarr.env` so both layers agree on what to enforce.

Security note: Plex API calls in both `Downshiftarr.py` and the shim send `X-Plex-Token` as an HTTP header, not as a URL query parameter.

---

## Requirements

### Software
- **Plex Media Server** (reachable from where Tautulli runs)
- **Tautulli** with Script notifications enabled
- **Python 3** (3.10+ recommended)

### Python packages
- `plexapi`
- `requests`
- `python-dotenv`

Install packages:
```bash
python3 -m pip install --upgrade plexapi requests python-dotenv
```

### Network requirements
- The host/container running the script must be able to reach:
  - `PLEX_URL` (Plex server)
  - `TAUTULLI_URL` (Tautulli API)

---

## Development setup

The repository is maintained WSL-first. From the project root:

```bash
python scripts/testing/verify_local.py
```

GitHub is used only as remote Git storage. Real Plex/Tautulli/Loki proof remains local and WSL/Windows guarded.

Optional local extra hygiene can be run with:

```bash
python scripts/testing/verify_local.py --ci
```

Testing docs:

- `docs/testing/test-environment.md` describes the layered rig and marker policy.
- `docs/testing/client-matrix.md` lists simulated Plex client profiles and scenarios.
- `docs/testing/loki-runbook.md` covers the opt-in Windows Loki Plex integration lane.
- `docs/testing/tautulli-sidecar.md` covers the isolated local Tautulli Docker sidecar.
- `docs/testing/hardening-test-environment.md` covers manual fuzz, property-based, monkey, chaos, mutation, and boundary setup.
- `docs/testing/hardening-initial-runs.md` is the durable checklist of first hardening commands to run after setup.

Hardening setup can be verified without launching campaigns:

```bash
python scripts/testing/verify_hardening_setup.py
python scripts/testing/list_hardening_runs.py --check
```

Real Plex tests are local-only and guarded. Copy `Downshiftarr.test.env.example` to `Downshiftarr.test.env`, fill in local Loki values, and run the Windows wrapper only when you intentionally want real-server proof:

```powershell
.\scripts\testing\Invoke-LokiIntegration.ps1
.\scripts\testing\Invoke-LokiIntegration.ps1 -SetupTautulli
.\scripts\testing\Invoke-LokiIntegration.ps1 -Destructive
```

---

## Installation

1) Put the script somewhere Tautulli can execute it, for example:
```bash
/opt/tautulli/scripts/Downshiftarr.py
```

2) Make it executable:
```bash
chmod +x /opt/tautulli/scripts/Downshiftarr.py
```

3) Create the configuration file next to the script from the tracked example:
```bash
cp /opt/tautulli/scripts/Downshiftarr.env.example /opt/tautulli/scripts/Downshiftarr.env
```

4) Protect the env file (recommended because it contains tokens):
```bash
chmod 600 /opt/tautulli/scripts/Downshiftarr.env
```

5) Confirm Tautulli can run Python + your dependencies:
- If Tautulli is running in Docker, you must install Python and packages **inside that container** (or run Tautulli on the host).
- Make sure the script path and env file path are inside a volume mounted into the container.

---

## Tautulli setup

### 1) Create a Script notification

In Tautulli:
- **Settings â†’ Notification Agents â†’ Add a new notification agent â†’ Script**

Configure:

**Script Folder**
- The directory containing `Downshiftarr.py` and your local `Downshiftarr.env`

**Script**
- `Downshiftarr.py`

### 2) Triggers
Enable these triggers:
- Playback Start
- Playback Resume
- Transcode Decision Change

### 3) Condition
Add a condition:
- **Video Decision** â†’ **is** â†’ **transcode**

This prevents Downshiftarr from being called for every direct play and keeps enforcement fast.

### 4) Arguments

Paste this as the Arguments string for **each of the triggers**:

```text
--rating-key={rating_key} --machine-id={machine_id} --username="{username}" --session-id={session_id} --session-key={session_key} --user-id={user_id} --video-decision={video_decision} --video-resolution={video_resolution} --stream-video-resolution={stream_video_resolution} --video-dynamic-range={video_dynamic_range}
```

**Notes**
- The quotes around `{username}` are intentional. If usernames can contain spaces, this avoids splitting the value.

---

## Configuration

Downshiftarr loads configuration from:
- `Downshiftarr.env` in the same directory as the script (recommended), or
- normal environment variables (OS / container / service manager)

A complete example file is included as `Downshiftarr.env.example`.

### Required settings

| Key | Example | What it does |
|---|---|---|
| `PLEX_URL` | `http://127.0.0.1:32400` | Plex Media Server URL |
| `PLEX_TOKEN` | `xxxxxxxx` | Plex token used for session inspection + client control |
| `TAUTULLI_URL` | `http://127.0.0.1:8181` | Tautulli URL |
| `TAUTULLI_APIKEY` | `yyyyyyyy` | Tautulli API key |

### Policy knobs

| Key | Default | Meaning |
|---|---:|---|
| `MAX_ALLOWED_HEIGHT` | `2000` | Height threshold; `>=` is treated as 4K-ish |
| `PREFER_HEIGHTS` | `1080,720,576,480,360` | Preferred fallback â€œversion heightsâ€ in order |
| `EXEMPT_USERS` | blank | Comma-separated Plex usernames to skip |
| `AUTO_WATERFALL_ON_CONTINUED_TRANSCODE` | `1` | Continue downshifting lower versions when the client still video-transcodes |
| `WATERFALL_MIN_HEIGHT` | `360` | Lowest height the waterfall should try |

### Fallback selection

| Key | Default | Meaning |
|---|---:|---|
| `FALLBACK_SDR_ONLY` | `1` | Only switch to SDR versions (strict) |
| `ALLOW_HDR_FALLBACK` | `0` | When SDR-only is disabled, allow HDR/DV fallback under max height |

**Typical choices**
- Strict enforcement (most common):
  - `FALLBACK_SDR_ONLY=1`
- More permissive (avoid killing when only HDR 1080 exists):
  - `FALLBACK_SDR_ONLY=0`
  - `ALLOW_HDR_FALLBACK=1`

### Per-failure enforcement toggles

Each toggle controls whether Downshiftarr terminates the stream if that failure occurs.

| Key | Default | When it triggers |
|---|---:|---|
| `KILL_ON_PLEX_CONNECT_FAIL` | `1` | Plex server canâ€™t be reached / plexapi init fails |
| `KILL_ON_SESSION_NOT_FOUND` | `1` | Script canâ€™t match a Plex session for the event |
| `KILL_ON_CLIENT_NOT_FOUND` | `1` | Session found but client canâ€™t be controlled |
| `KILL_ON_NO_FALLBACK_MEDIA` | `1` | No compliant version exists under the policy |
| `KILL_ON_SWITCH_FAIL` | `1` | Switch command throws or seek fails catastrophically |
| `KILL_ON_UNEXPECTED_ERROR` | `1` | Any uncaught exception causes enforcement attempt |

### Kill messages

| Key | Default | Purpose |
|---|---|---|
| `KILL_MESSAGE_DEFAULT` | (built-in) | Used when no scenario-specific message is set |
| `KILL_MESSAGE_*` | blank | If blank, falls back to default |

Tip: leave most of these blank and only override the ones you care about.

### Speed / retry tuning

| Key | Default | Notes |
|---|---:|---|
| `SESSION_LOOKUP_RETRIES` | `4` | Increase if Playback Start fires â€œtoo earlyâ€ for your setup |
| `SESSION_LOOKUP_DELAY_S` | `0.25` | Keep small for minimal delay |
| `SEEK_DELAY_S` | `0.75` | Time to wait before seeking after playMedia |
| `SEEK_RETRIES` | `3` | Seek retries for clients that ignore offset |
| `SEEK_RETRY_DELAY_S` | `0.50` | Delay between seek attempts |
| `HTTP_TIMEOUT_S` | `8` | HTTP timeout for Plex/Tautulli calls |

---

## Logging

Downshiftarr logs in two ways:

### 1) Rotating log file
Configured by:
- `LOG_FILE`
- `LOG_MAX_BYTES`
- `LOG_BACKUP_COUNT`

### 2) Tautulli captures script output (stderr)
Downshiftarr writes logs to stderr when:
- `LOG_TO_STDERR=1`

In Tautulli, you can usually see this output under the log entry for the Script agent (itâ€™s typically under **Settings â†’ Notifications â†’ Logs/History**).

### Verbose logging
Turn on deep debug logging by setting either:
- `VERBOSE=1` **or**
- `LOG_LEVEL=DEBUG`

### Optional: log to Tautulli notification history via API
If you want Downshiftarr to create Tautulli notification entries via the `notify` API, set:
- `TAUTULLI_LOG_NOTIFIER_ID=<integer id>`
- `TAUTULLI_LOG_MIN_LEVEL=INFO` (or WARNING/ERROR)

**Warning:** do **not** point that notifier at Downshiftarr itself, or youâ€™ll create a loop.

---

## Behavior details

### When it will intervene
Downshiftarr only acts when:
- The Tautulli event indicates **video transcoding**, and
- Plex session inspection identifies the *source* as â€œprotectedâ€ (4K and/or HDR/DV).

### When it will NOT intervene
- User is in `EXEMPT_USERS`
- Decision is not video transcoding
- Source is not detected as protected

### Fallback selection logic (high level)
- Ignore the currently selected version.
- Only consider versions with `height < MAX_ALLOWED_HEIGHT`.
- Prefer the heights in `PREFER_HEIGHTS` (in order).
- In strict mode (`FALLBACK_SDR_ONLY=1`), only consider SDR candidates.
- If no candidate exists, enforce (terminate) depending on kill toggle.

### Termination order
If enforcement is required, Downshiftarr attempts:
1) `terminate_session` via Tautulli API (preferred)
2) Plex termination fallbacks (best-effort)

---

## Troubleshooting

### â€œIt keeps killing streams even though I have a 1080p versionâ€
Most common causes:
- The 1080p version is also HDR/DV, and youâ€™re running `FALLBACK_SDR_ONLY=1`.
  - Fix: set `FALLBACK_SDR_ONLY=0` and `ALLOW_HDR_FALLBACK=1`, or add an SDR version.
- Plex session metadata doesnâ€™t show all versions for the session object.
  - Downshiftarr already retries using full library metadata once, but you may have unusual library metadata. Make sure the Plex Web interface indicates the multiple versions under 1 entry.

### â€œIt canâ€™t find the sessionâ€
- Make sure you included `--session-key={session_key}` in arguments.
- Playback Start can fire before Plex has fully registered the session.
  - Increase `SESSION_LOOKUP_RETRIES` slightly (e.g., 6) while keeping delay small.
- Confirm `PLEX_URL` is correct **from inside the Tautulli environment** (container vs host address mismatch is common).

### â€œIt canâ€™t control the clientâ€
- Some Plex clients are harder to remote-control (network/NAT/relay limitations).
- The script tries multiple client discovery strategies. If all fail, it enforces by termination (depending on your toggle).

### â€œTermination doesnâ€™t workâ€
- Verify `TAUTULLI_URL` and `TAUTULLI_APIKEY` are correct and reachable.
- Check Tautulli API access from the environment running the script.
- If Tautulli termination fails, Plex termination may also fail depending on token scope/network.

### Turn on debug logs
Set:
```text
VERBOSE=1
```
- Then reproduce the issue and inspect the log file.
- Record the reproduction details, sanitized logs, and local verification output for the maintainer/operator.
