Information to explain how the "Plex Transcoder" file is to be used will be added soon.

The full solution is going to end up requiring use of the Plex Transcoder file. The reason is because the Plex devs have been destroying their app ecosystem with the new shitperience apps, as well as some of the smartTV apps can still misbehave.

# Downshiftarr

Downshiftarr is a **Plex 4K/HDR/DV transcode guard** designed to be run from a **Tautulli “Script” notification**.

When a client tries to **VIDEO transcode** a protected source (4K and/or HDR/DV), Downshiftarr will:

1. Find the active Plex session (best-effort, with short retries).
2. Determine what version is *actually being played* from Plex session metadata (the source of truth).
3. Attempt to **switch** the client to a compliant version (typically **≤1080p SDR**).
4. If switching can’t be done safely/reliably, it will **enforce** the policy by terminating the stream (configurable).

The script is built to be fast (early exits; minimal calls) and robust (multiple fallbacks; fail-closed by default).

---

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
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
- Looks up the **actual Plex session** and reads the selected media’s **height** and **dynamic range** from Plex.
- Classifies the source as “protected” if:
  - `height >= MAX_ALLOWED_HEIGHT` (default 2000 → catches 2160p), **or**
  - dynamic range is clearly not SDR (HDR / Dolby Vision / HLG, etc.).

If it’s protected **and** video is being transcoded:
- Pick the best fallback version under the threshold (and typically SDR).
- Remote-control the client via plexapi (`playMedia` + `seekTo` fallbacks).
- If downshift fails → terminate the session (Tautulli first; Plex fallback).

---

## Requirements

### Software
- **Plex Media Server** (reachable from where Tautulli runs)
- **Tautulli** with Script notifications enabled
- **Python 3** (3.8+ recommended)

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

## Installation

1) Put the script somewhere Tautulli can execute it, for example:
```bash
/opt/tautulli/scripts/Downshiftarr.py
```

2) Make it executable:
```bash
chmod +x /opt/tautulli/scripts/Downshiftarr.py
```

3) Create the configuration file next to the script:
```bash
/opt/tautulli/scripts/Downshiftarr.env
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
- **Settings → Notification Agents → Add a new notification agent → Script**

Configure:

**Script Folder**
- The directory containing `Downshiftarr.py` and `Downshiftarr.env`

**Script**
- `Downshiftarr.py`

### 2) Triggers
Enable these triggers:
- Playback Start
- Playback Resume
- Transcode Decision Change

### 3) Condition
Add a condition:
- **Video Decision** → **is** → **transcode**

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

A complete example file is included as `Downshiftarr.env`.

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
| `PREFER_HEIGHTS` | `1080,720,576,480` | Preferred fallback “version heights” in order |
| `EXEMPT_USERS` | blank | Comma-separated Plex usernames to skip |

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
| `KILL_ON_PLEX_CONNECT_FAIL` | `1` | Plex server can’t be reached / plexapi init fails |
| `KILL_ON_SESSION_NOT_FOUND` | `1` | Script can’t match a Plex session for the event |
| `KILL_ON_CLIENT_NOT_FOUND` | `1` | Session found but client can’t be controlled |
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
| `SESSION_LOOKUP_RETRIES` | `4` | Increase if Playback Start fires “too early” for your setup |
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

In Tautulli, you can usually see this output under the log entry for the Script agent (it’s typically under **Settings → Notifications → Logs/History**).

### Verbose logging
Turn on deep debug logging by setting either:
- `VERBOSE=1` **or**
- `LOG_LEVEL=DEBUG`

### Optional: log to Tautulli notification history via API
If you want Downshiftarr to create Tautulli notification entries via the `notify` API, set:
- `TAUTULLI_LOG_NOTIFIER_ID=<integer id>`
- `TAUTULLI_LOG_MIN_LEVEL=INFO` (or WARNING/ERROR)

**Warning:** do **not** point that notifier at Downshiftarr itself, or you’ll create a loop.

---

## Behavior details

### When it will intervene
Downshiftarr only acts when:
- The Tautulli event indicates **video transcoding**, and
- Plex session inspection identifies the *source* as “protected” (4K and/or HDR/DV).

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

### “It keeps killing streams even though I have a 1080p version”
Most common causes:
- The 1080p version is also HDR/DV, and you’re running `FALLBACK_SDR_ONLY=1`.
  - Fix: set `FALLBACK_SDR_ONLY=0` and `ALLOW_HDR_FALLBACK=1`, or add an SDR version.
- Plex session metadata doesn’t show all versions for the session object.
  - Downshiftarr already retries using full library metadata once, but you may have unusual library metadata. Make sure the Plex Web interface indicates the multiple versions under 1 entry.

### “It can’t find the session”
- Make sure you included `--session-key={session_key}` in arguments.
- Playback Start can fire before Plex has fully registered the session.
  - Increase `SESSION_LOOKUP_RETRIES` slightly (e.g., 6) while keeping delay small.
- Confirm `PLEX_URL` is correct **from inside the Tautulli environment** (container vs host address mismatch is common).

### “It can’t control the client”
- Some Plex clients are harder to remote-control (network/NAT/relay limitations).
- The script tries multiple client discovery strategies. If all fail, it enforces by termination (depending on your toggle).

### “Termination doesn’t work”
- Verify `TAUTULLI_URL` and `TAUTULLI_APIKEY` are correct and reachable.
- Check Tautulli API access from the environment running the script.
- If Tautulli termination fails, Plex termination may also fail depending on token scope/network.

### Turn on debug logs
Set:
```text
VERBOSE=1
```
Then reproduce the issue and inspect the log file.
