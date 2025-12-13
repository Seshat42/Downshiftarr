#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Downshiftarr v0.7.1
By Seshat42

Plex 4K/HDR/DV transcode guard (fail-closed by default) with best-effort auto-downshift.

What it does
------------
Downshiftarr is meant to be called by a Tautulli "Script" notification agent.

When a client is VIDEO-transcoding a high-quality source (4K and/or HDR/DV), Downshiftarr will:

1) Identify the active Plex session (best-effort, with retries).
2) Confirm which version is *actually* being played using Plex session metadata (source-of-truth).
3) Attempt to switch the client to the best fallback version (typically <=1080p SDR).
4) If switching isn't possible (no session, no client, no fallback, or switch failure), enforce the policy
   by terminating the stream (configurable per failure case).

Important notes
---------------
- Tautulli placeholders like {stream_video_resolution} and {video_resolution} are treated as *hints* only.
  (stream_* is the output; video_* is usually the original file.)
  Once we can match a Plex session, Plex is the source-of-truth.
- Not every Plex client supports remote control equally well. This script tries multiple control strategies,
  then fails closed (terminate) if it cannot safely downshift.

Tautulli setup
--------------------------
Triggers:
- Playback Start
- Playback Resume
- Transcode Decision Change

Condition:
- Video Decision is Transcode

Arguments (flag mode; safest when values might be blank or include spaces):
- --rating-key={rating_key} --machine-id={machine_id} --username="{username}" --session-id={session_id} --user-id={user_id} --video-resolution={video_resolution} --stream-video-resolution={stream_video_resolution} --video-decision={video_decision} --video-dynamic-range={video_dynamic_range} --session-key={session_key}

Legacy Arguments (positional mode; simplest, but can fail):
- {rating_key} {machine_id} {username} {session_id} {user_id} {video_resolution} {video_decision} {video_dynamic_range}

Environment variables
---------------------
Tautulli will inject these automatically for script agents:
  PLEX_URL, PLEX_TOKEN, PLEX_USER_TOKEN, TAUTULLI_URL, TAUTULLI_APIKEY

Options are set in the .env file:
  - Place ./Downshiftarr.env next to this script

Policy knobs:
  MAX_ALLOWED_HEIGHT=2000                 # >=2000 treated as "4K-ish"
  PREFER_HEIGHTS=720,1080,576,480         # fallback preference order (kept v0.7.0 default)
  EXEMPT_USERS=user1,user2                # comma-separated Plex usernames

Fallback selection:
  FALLBACK_SDR_ONLY=1                    # v0.7.0 behavior (SDR-only fallbacks)
  ALLOW_HDR_FALLBACK=0                   # if no SDR fallback exists, allow HDR/DV fallbacks under MAX_ALLOWED_HEIGHT

Per-failure enforcement toggles (default = enabled):
  KILL_ON_PLEX_CONNECT_FAIL=1
  KILL_ON_SESSION_NOT_FOUND=1
  KILL_ON_CLIENT_NOT_FOUND=1
  KILL_ON_NO_FALLBACK_MEDIA=1
  KILL_ON_SWITCH_FAIL=1
  KILL_ON_UNEXPECTED_ERROR=1

Per-failure kill messages (optional; fall back to KILL_MESSAGE_DEFAULT):
  KILL_MESSAGE_DEFAULT=...
  KILL_MESSAGE_SESSION_NOT_FOUND=...
  KILL_MESSAGE_CLIENT_NOT_FOUND=...
  KILL_MESSAGE_NO_FALLBACK_MEDIA=...
  KILL_MESSAGE_SWITCH_FAIL=...
  KILL_MESSAGE_PLEX_CONNECT_FAIL=...
  KILL_MESSAGE_UNEXPECTED_ERROR=...

Logging:
  LOG_FILE=/path/to/downshiftarr.log
  LOG_LEVEL=INFO|DEBUG
  VERBOSE=0|1                            # if set, forces DEBUG
  LOG_TO_STDERR=1                        # Tautulli captures the output

Optional: "log into Tautulli" (via a Tautulli notification entry)
  TAUTULLI_LOG_NOTIFIER_ID=<id>          # create a notifier in Tautulli that does NOT run this script (avoid recursion)
  TAUTULLI_LOG_MIN_LEVEL=WARNING|INFO
  TAUTULLI_LOG_SUBJECT=Downshiftarr

Speed / retry tuning:
  SESSION_LOOKUP_RETRIES=4
  SESSION_LOOKUP_DELAY_S=0.25
  SEEK_DELAY_S=0.75
  SEEK_RETRIES=3
  SEEK_RETRY_DELAY_S=0.50
  HTTP_TIMEOUT_S=8

Dependencies
------------
- python3
- plexapi
- requests
- (optional) python-dotenv
"""

from __future__ import annotations

import os
import sys
import time
import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

# -------------------------
# Options via .env loading
# -------------------------
SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None  # type: ignore

ENV_FILE = os.environ.get("ENV_FILE", "").strip()
if load_dotenv is not None:
    try:
        # User-specified env file wins.
        if ENV_FILE and Path(ENV_FILE).exists():
            load_dotenv(ENV_FILE)
        else:
            # Local default: ./Downshiftarr.env
            local_env = SCRIPT_DIR / "Downshiftarr.env"
            if local_env.exists():
                load_dotenv(str(local_env))
    except Exception:
        # Env loading is a convenience; never crash because of it.
        pass


# -------------------------
# Env helpers
# -------------------------
def env_str(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    return v.strip() if v is not None and str(v).strip() != "" else default


def env_int(name: str, default: Optional[int] = None) -> Optional[int]:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return int(str(v).strip())
    except Exception:
        return default


def env_float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(str(v).strip())
    except Exception:
        return default


def env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


def env_csv_set(name: str, default: str = "") -> Set[str]:
    raw = env_str(name, default)
    return {p.strip() for p in raw.split(",") if p.strip()}


# -------------------------
# Configuration
# -------------------------
PLEX_URL = env_str("PLEX_URL", "")
PLEX_TOKEN = env_str("PLEX_TOKEN", "")
PLEX_USER_TOKEN = env_str("PLEX_USER_TOKEN", "")

TAUTULLI_URL = env_str("TAUTULLI_URL", "")
TAUTULLI_APIKEY = env_str("TAUTULLI_APIKEY", "")

HTTP_TIMEOUT_S = env_float("HTTP_TIMEOUT_S", 8.0)

# Logging configuration
VERBOSE = env_bool("VERBOSE", False)
LOG_LEVEL = env_str("LOG_LEVEL", "DEBUG" if VERBOSE else "INFO").upper()
LOG_TO_STDERR = env_bool("LOG_TO_STDERR", True)

LOG_FILE = env_str("LOG_FILE", str(SCRIPT_DIR / "downshiftarr.log"))
LOG_MAX_BYTES = env_int("LOG_MAX_BYTES", 2_000_000) or 2_000_000
LOG_BACKUP_COUNT = env_int("LOG_BACKUP_COUNT", 5) or 5

# Tautulli "logging" (notification) configuration
TAUTULLI_LOG_NOTIFIER_ID = env_int("TAUTULLI_LOG_NOTIFIER_ID", None)
TAUTULLI_LOG_MIN_LEVEL = env_str("TAUTULLI_LOG_MIN_LEVEL", "WARNING").upper()
TAUTULLI_LOG_SUBJECT = env_str("TAUTULLI_LOG_SUBJECT", "Downshiftarr")

# Policy knobs
EXEMPT_USERS = env_csv_set("EXEMPT_USERS", "")

MAX_ALLOWED_HEIGHT = env_int("MAX_ALLOWED_HEIGHT", 2000) or 2000  # <2000 ~= avoid 2160p
# Keep v0.7.0 default ordering unless user overrides.
PREFER_HEIGHTS = tuple(
    int(x) for x in env_str("PREFER_HEIGHTS", "1080,720,576,480").split(",") if x.strip().isdigit()
) or (1080, 720, 576, 480)

FALLBACK_SDR_ONLY = env_bool("FALLBACK_SDR_ONLY", True)
ALLOW_HDR_FALLBACK = env_bool("ALLOW_HDR_FALLBACK", False)

# Session lookup tuning
SESSION_LOOKUP_RETRIES = env_int("SESSION_LOOKUP_RETRIES", 4) or 4
SESSION_LOOKUP_DELAY_S = env_float("SESSION_LOOKUP_DELAY_S", 0.25)

# Seek tuning after switch (some clients ignore offset in playMedia)
SEEK_DELAY_S = env_float("SEEK_DELAY_S", 0.75)
SEEK_RETRIES = env_int("SEEK_RETRIES", 3) or 3
SEEK_RETRY_DELAY_S = env_float("SEEK_RETRY_DELAY_S", 0.50)

# Per-failure enforcement toggles
KILL_ON_PLEX_CONNECT_FAIL = env_bool("KILL_ON_PLEX_CONNECT_FAIL", True)
KILL_ON_SESSION_NOT_FOUND = env_bool("KILL_ON_SESSION_NOT_FOUND", True)
KILL_ON_CLIENT_NOT_FOUND = env_bool("KILL_ON_CLIENT_NOT_FOUND", True)
KILL_ON_NO_FALLBACK_MEDIA = env_bool("KILL_ON_NO_FALLBACK_MEDIA", True)
KILL_ON_SWITCH_FAIL = env_bool("KILL_ON_SWITCH_FAIL", True)
KILL_ON_UNEXPECTED_ERROR = env_bool("KILL_ON_UNEXPECTED_ERROR", True)

# Kill messages
KILL_MESSAGE_DEFAULT = env_str(
    "KILL_MESSAGE_DEFAULT",
    "This 4K/HDR title cannot be transcoded. Please select the 1080p (or lower) version from the 3 dot menu.",
)

KILL_MESSAGE_SESSION_NOT_FOUND = env_str("KILL_MESSAGE_SESSION_NOT_FOUND", KILL_MESSAGE_DEFAULT)
KILL_MESSAGE_CLIENT_NOT_FOUND = env_str("KILL_MESSAGE_CLIENT_NOT_FOUND", KILL_MESSAGE_DEFAULT)
KILL_MESSAGE_NO_FALLBACK_MEDIA = env_str("KILL_MESSAGE_NO_FALLBACK_MEDIA", KILL_MESSAGE_DEFAULT)
KILL_MESSAGE_SWITCH_FAIL = env_str("KILL_MESSAGE_SWITCH_FAIL", KILL_MESSAGE_DEFAULT)
KILL_MESSAGE_PLEX_CONNECT_FAIL = env_str("KILL_MESSAGE_PLEX_CONNECT_FAIL", KILL_MESSAGE_DEFAULT)
KILL_MESSAGE_UNEXPECTED_ERROR = env_str("KILL_MESSAGE_UNEXPECTED_ERROR", KILL_MESSAGE_DEFAULT)

# Decisions that are considered "not transcoding video" for enforcement purposes.
# (Tautulli/Plex may use different casing/spaces; we normalize.)
ALLOW_VIDEO_DECISIONS = {
    "direct play", "directplay", "direct_play",
    "direct stream", "directstream", "direct_stream",
    "copy",
}

# Shared HTTP sessions (keeps things snappy across multiple requests in a single run).
TAU_HTTP = requests.Session()
PLEX_HTTP = requests.Session()

# Track the actual Plex token used (useful for direct API fallback).
PLEX_EFFECTIVE_TOKEN: Optional[str] = None


# -------------------------
# Logging setup
# -------------------------
def setup_logger() -> logging.Logger:
    logger = logging.getLogger("downshiftarr")
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Avoid duplicate handlers if script is imported/reloaded.
    if logger.handlers:
        return logger

    # File logging
    try:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    except Exception:
        pass

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # Stderr logging (helps Tautulli display script output)
    if LOG_TO_STDERR:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger


log = setup_logger()


def level_value(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


def should_tautulli_notify(level_name: str) -> bool:
    if TAUTULLI_LOG_NOTIFIER_ID is None:
        return False
    return level_value(level_name) >= level_value(TAUTULLI_LOG_MIN_LEVEL)


# -------------------------
# Data models
# -------------------------
@dataclass
class InputEvent:
    rating_key: Optional[str] = None
    machine_id: Optional[str] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    session_key: Optional[str] = None
    user_id: Optional[str] = None
    video_decision: Optional[str] = None
    # Hints from Tautulli (not trusted as source-of-truth)
    video_resolution: Optional[str] = None
    stream_video_resolution: Optional[str] = None
    video_dynamic_range: Optional[str] = None
    # Optional: name of the trigger/action (if you pass it)
    action: Optional[str] = None


@dataclass
class SessionContext:
    session_item: Any
    session_key: Optional[str]
    session_id: Optional[str]
    username: Optional[str]
    machine_id: Optional[str]
    player_title: Optional[str]
    player_product: Optional[str]
    player_address: Optional[str]
    player_port: Optional[str]
    view_offset_ms: int


# -------------------------
# Tautulli API helpers
# -------------------------
def tautulli_api_call(cmd: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Call Tautulli API v2 (best-effort).
    """
    if not TAUTULLI_URL or not TAUTULLI_APIKEY:
        return None

    api_url = f"{TAUTULLI_URL.rstrip('/')}/api/v2"
    full_params: Dict[str, Any] = {"apikey": TAUTULLI_APIKEY, "cmd": cmd}
    full_params.update(params)

    try:
        r = TAU_HTTP.get(api_url, params=full_params, timeout=HTTP_TIMEOUT_S)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.debug("Tautulli API call failed cmd=%s err=%s", cmd, e)
        return None


def tautulli_notify(level_name: str, subject: str, body: str) -> None:
    """
    Send a Tautulli notification (optional).

    This does NOT write into the main Tautulli application log, but it does create a notification entry
    (visible in Tautulli notification logs/history for that notifier).
    """
    if TAUTULLI_LOG_NOTIFIER_ID is None:
        return
    if not should_tautulli_notify(level_name):
        return

    payload = {
        "notifier_id": TAUTULLI_LOG_NOTIFIER_ID,
        "subject": subject,
        "body": body,
    }
    tautulli_api_call("notify", payload)


def terminate_via_tautulli(session_key: Optional[str], session_id: Optional[str], message: str) -> bool:
    """
    Terminate via Tautulli (preferred when available).
    """
    if not TAUTULLI_URL or not TAUTULLI_APIKEY:
        return False

    params: Dict[str, Any] = {"message": message}
    if session_key:
        params["session_key"] = session_key
    elif session_id:
        params["session_id"] = session_id
    else:
        return False

    data = tautulli_api_call("terminate_session", params)
    ok = bool(data and data.get("response", {}).get("result") == "success")
    if ok:
        log.info("Tautulli terminate_session sent successfully.")
    else:
        log.warning("Tautulli terminate_session returned non-success: %s", data)
    return ok


# -------------------------
# Plex helpers
# -------------------------
def connect_plex():
    """
    Connect to Plex using plexapi.

    Prefer admin PLEX_TOKEN. If missing, fall back to PLEX_USER_TOKEN (less ideal, but better than nothing).
    """
    global PLEX_EFFECTIVE_TOKEN
    token = PLEX_TOKEN or PLEX_USER_TOKEN
    if not PLEX_URL or not token:
        raise RuntimeError("PLEX_URL and PLEX_TOKEN (or PLEX_USER_TOKEN) must be available.")

    PLEX_EFFECTIVE_TOKEN = token

    try:
        from plexapi.server import PlexServer  # type: ignore
        return PlexServer(PLEX_URL, token, session=PLEX_HTTP, timeout=int(HTTP_TIMEOUT_S))
    except Exception as e:
        raise RuntimeError(f"Failed to import/connect plexapi: {e}")


def normalize_decision(dec: Optional[str]) -> str:
    return (dec or "").strip().lower()


def is_video_transcoding(video_decision: Optional[str]) -> bool:
    """
    True when the event indicates video is transcoding.
    We treat "direct play/stream/copy" as allowed states.
    """
    d = normalize_decision(video_decision)
    return "transcode" in d and d not in ALLOW_VIDEO_DECISIONS


def safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(str(x))
    except Exception:
        return None


def parse_resolution_hint(res: Optional[str]) -> Optional[int]:
    """
    Convert common resolution strings ("4k", "2160", "1080", "720") into an approximate height.
    """
    if not res:
        return None
    s = str(res).strip().lower()
    if s in ("4k", "uhd") or "2160" in s:
        return 2160
    if "1080" in s:
        return 1080
    if "720" in s:
        return 720
    if "576" in s:
        return 576
    if "480" in s:
        return 480
    # Sometimes it is already a number.
    try:
        n = int(s)
        if n > 0:
            return n
    except Exception:
        pass
    return None


def media_height(media_obj) -> Optional[int]:
    """
    Best-effort height for a Media object.
    Plex can expose this as 'height', 'videoHeight', or only via stream metadata.
    """
    for attr in ("height", "videoHeight"):
        h = safe_int(getattr(media_obj, attr, None))
        if h:
            return h

    # Try resolution string attribute (varies by object shape)
    for attr in ("videoResolution", "resolution"):
        v = getattr(media_obj, attr, None)
        h = parse_resolution_hint(v)
        if h:
            return h

    # Try streams (heavier; may require that parts/streams are populated)
    try:
        for part in getattr(media_obj, "parts", []) or []:
            for stream in getattr(part, "streams", []) or []:
                if safe_int(getattr(stream, "streamType", None)) == 1:  # video
                    h = safe_int(getattr(stream, "height", None))
                    if h:
                        return h
    except Exception:
        pass

    return None


def media_dynamic_range(media_obj) -> str:
    """
    Best-effort dynamic range string.
    Prefer explicit Media.videoDynamicRange when present; fall back to stream hints.
    """
    for attr in ("videoDynamicRange", "dynamicRange", "videoDynamicRangeType"):
        v = getattr(media_obj, attr, None)
        if v:
            return str(v).upper().strip()

    # Stream inspection fallback
    try:
        for part in getattr(media_obj, "parts", []) or []:
            for stream in getattr(part, "streams", []) or []:
                if safe_int(getattr(stream, "streamType", None)) != 1:
                    continue
                # Dolby Vision flags can show up a few different ways.
                for a in ("DOVIPresent", "doviPresent", "dolbyVision"):
                    v = getattr(stream, a, None)
                    if str(v).lower() in ("1", "true", "yes"):
                        return "DOLBY VISION"
                # HDR hints can show up in colorSpace/transfer/etc.
                for a in ("colorSpace", "colorTransfer", "colorPrimaries", "hdr"):
                    v = getattr(stream, a, None)
                    if v and any(k in str(v).upper() for k in ("HDR", "DOVI", "DV", "DOLBY")):
                        return "HDR"
    except Exception:
        pass

    return "UNKNOWN"


def classify_dynamic_range(dr: str) -> str:
    s = (dr or "").upper().strip()
    if not s or s in ("UNKNOWN", "NONE"):
        return "UNKNOWN"
    if "SDR" in s:
        return "SDR"
    if "DOVI" in s or "DOLBY" in s or "VISION" in s or s == "DV":
        return "DOLBY VISION"
    if "HDR" in s or "HLG" in s:
        return "HDR"
    # Any other non-empty value is treated as "not SDR".
    return "HDR"


def is_high_quality(height: Optional[int], dyn_range: str) -> bool:
    """
    A "high quality" source is:
    - 4K-ish by height threshold, OR
    - anything clearly not SDR (HDR / DV / HLG / etc)
    """
    if height is not None and height >= MAX_ALLOWED_HEIGHT:
        return True
    drc = classify_dynamic_range(dyn_range)
    if drc not in ("SDR", "UNKNOWN"):
        return True
    return False


def fetch_library_item(plex, rating_key: str):
    """
    Fetch full library metadata for a rating_key (for version list).
    """
    try:
        return plex.fetchItem(int(rating_key))
    except Exception:
        pass
    return plex.fetchItem(f"/library/metadata/{rating_key}")


def current_media_identity(item) -> Tuple[Optional[str], Optional[int], str]:
    """
    Determine the *currently selected* Media: (media_id, height, dynamic_range)
    """
    try:
        media_list = getattr(item, "media", []) or []
        for m in media_list:
            if getattr(m, "selected", False):
                mid = getattr(m, "id", None)
                return (str(mid) if mid is not None else None, media_height(m), media_dynamic_range(m))
        if media_list:
            m0 = media_list[0]
            return (str(getattr(m0, "id", None)), media_height(m0), media_dynamic_range(m0))
    except Exception:
        pass
    return (None, None, "UNKNOWN")


def pick_best_fallback_media_index(
    item,
    current_media_id: Optional[str],
    current_height: Optional[int],
    current_dr: str,
) -> Optional[int]:
    """
    Choose the best fallback media index.

    Default v0.7.0 behavior: SDR-only and < MAX_ALLOWED_HEIGHT.

    Eligibility:
      - Exclude the currently selected media
      - Exclude >= MAX_ALLOWED_HEIGHT (avoid 4K-ish)
      - Prefer *lower* height than the current stream, BUT allow equal height if we improve to SDR
        (e.g., 1080 HDR -> 1080 SDR)
      - If ALLOW_HDR_FALLBACK is enabled and SDR-only finds nothing, allow HDR/DV candidates
        under MAX_ALLOWED_HEIGHT (still a useful resolution downshift for many clients).

    Ranking:
      - Prefer heights in PREFER_HEIGHTS (user-configurable)
      - Otherwise prefer higher height under MAX_ALLOWED_HEIGHT
    """
    def candidate_score(h: int) -> Tuple[int, int]:
        if h in PREFER_HEIGHTS:
            pref_rank = PREFER_HEIGHTS.index(h)
        else:
            # After preferred heights, pick the biggest under the max.
            pref_rank = len(PREFER_HEIGHTS) + (MAX_ALLOWED_HEIGHT - h)
        return (pref_rank, -h)

    cur_drc = classify_dynamic_range(current_dr)

    media_list = getattr(item, "media", []) or []
    if not media_list:
        return None

    # Two-pass selection:
    #   pass 1: SDR-only (preferred)
    #   pass 2: allow HDR/DV (optional)
    passes: List[Tuple[str, bool]] = []
    if FALLBACK_SDR_ONLY:
        # Strict mode (v0.7.0): only consider SDR candidates.
        passes = [("SDR_ONLY", True)]
    else:
        if ALLOW_HDR_FALLBACK:
            # Prefer SDR if possible, but allow HDR/DV if no SDR fallback exists.
            passes = [("SDR_PREFERRED", True), ("ALLOW_HDR", False)]
        else:
            # Looser mode: allow HDR/DV candidates immediately (still under MAX_ALLOWED_HEIGHT).
            passes = [("ALLOW_HDR_ONLY", False)]

    for pass_name, sdr_only in passes:
        candidates: List[Tuple[int, int, str, Tuple[int, int]]] = []
        for idx, m in enumerate(media_list):
            mid = str(getattr(m, "id", "") or "")
            if current_media_id and mid == current_media_id:
                continue

            h = media_height(m)
            if h is None or h >= MAX_ALLOWED_HEIGHT:
                continue

            dr = media_dynamic_range(m).upper().strip()
            drc = classify_dynamic_range(dr)

            if sdr_only and drc != "SDR":
                continue

            # Accept only "downshifts" in resolution, except allow equal height when improving HDR->SDR.
            acceptable = False
            if current_height is not None:
                if h < current_height:
                    acceptable = True
                elif cur_drc != "SDR" and drc == "SDR" and h <= current_height:
                    acceptable = True
            else:
                # If current height is unknown, any < MAX_ALLOWED_HEIGHT is a reasonable candidate.
                acceptable = True

            if not acceptable:
                continue

            candidates.append((idx, h, dr, candidate_score(h)))

        if candidates:
            candidates.sort(key=lambda t: t[3])
            log.debug("Fallback selection pass=%s candidates=%s", pass_name, [(c[0], c[1], c[2]) for c in candidates[:5]])
            return candidates[0][0]

    return None


def find_session(plex, ev: InputEvent) -> Optional[SessionContext]:
    """
    Best-effort session lookup with retries.

    Matching preference:
      1) session_key (fast/unique)
      2) session_id (Tautulli {session_id})
      3) rating_key + username
      4) rating_key + machine_id

    Returns SessionContext or None.
    """
    last_err: Optional[Exception] = None

    for attempt in range(1, SESSION_LOOKUP_RETRIES + 1):
        try:
            sessions = plex.sessions()
            best_score: Optional[int] = None
            best_payload: Optional[Tuple[Any, str, str, str, str, Optional[str], Optional[str], Optional[str], Optional[str]]] = None

            for s in sessions:
                rk = str(getattr(s, "ratingKey", "") or "")
                sk = str(getattr(s, "sessionKey", "") or "")
                sid = str(getattr(getattr(s, "session", None), "id", "") or getattr(s, "sessionId", "") or "")

                # username heuristics
                uname = ""
                u = getattr(s, "user", None)
                for attr in ("title", "username", "name"):
                    if u is not None and getattr(u, attr, None):
                        uname = str(getattr(u, attr))
                        break
                if not uname:
                    uname = str(getattr(s, "username", "") or "")

                # player heuristics
                player = getattr(s, "player", None)
                mid = ""
                ptitle = None
                pproduct = None
                paddr = None
                pport = None
                if player is not None:
                    for attr in ("machineIdentifier", "clientIdentifier"):
                        if getattr(player, attr, None):
                            mid = str(getattr(player, attr))
                            break
                    ptitle = getattr(player, "title", None) or getattr(player, "name", None)
                    pproduct = getattr(player, "product", None)
                    paddr = getattr(player, "address", None)
                    pport = getattr(player, "port", None)

                # scoring: lower is better
                score = 1000
                if ev.session_key and sk and ev.session_key == sk:
                    score = min(score, 0)
                if ev.session_id and sid and ev.session_id == sid:
                    score = min(score, 1)
                if ev.rating_key and rk and ev.rating_key == rk and ev.username and uname and ev.username == uname:
                    score = min(score, 5)
                if ev.rating_key and rk and ev.rating_key == rk and ev.machine_id and mid and ev.machine_id == mid:
                    score = min(score, 10)

                if score < 1000:
                    if best_score is None or score < best_score:
                        best_score = score
                        best_payload = (s, sk, sid, uname, mid, str(ptitle) if ptitle is not None else None,
                                        str(pproduct) if pproduct is not None else None,
                                        str(paddr) if paddr is not None else None,
                                        str(pport) if pport is not None else None)

            if best_payload is not None:
                s, sk, sid, uname, mid, ptitle, pproduct, paddr, pport = best_payload
                view_offset = safe_int(getattr(s, "viewOffset", 0)) or 0
                return SessionContext(
                    session_item=s,
                    session_key=sk or None,
                    session_id=sid or None,
                    username=uname or None,
                    machine_id=mid or None,
                    player_title=ptitle,
                    player_product=pproduct,
                    player_address=paddr,
                    player_port=pport,
                    view_offset_ms=view_offset,
                )

        except Exception as e:
            last_err = e

        if attempt < SESSION_LOOKUP_RETRIES:
            time.sleep(SESSION_LOOKUP_DELAY_S)

    if last_err:
        log.warning("Session lookup failed after %s attempts: %s", SESSION_LOOKUP_RETRIES, last_err)
    return None


def find_client(plex, ctx: SessionContext, fallback_machine_id: Optional[str]):
    """
    Locate a controllable PlexClient instance.

    Strategy order:
      1) Match by machineIdentifier/clientIdentifier in plex.clients()
      2) Try plex.client(<player title>) as a name lookup
      3) Build a "proxy-only" PlexClient using identifier and proxyThroughServer()
      4) Direct connect using player address/port (best-effort; can fail on NAT/relay)

    Returns (client_obj, identifier_used) or (None, None)
    """
    target_ids: List[str] = []
    if ctx.machine_id:
        target_ids.append(str(ctx.machine_id))
    if fallback_machine_id and str(fallback_machine_id) not in target_ids:
        target_ids.append(str(fallback_machine_id))

    # 1) Enumerate known clients
    clients = []
    try:
        clients = plex.clients()
    except Exception as e:
        log.debug("Unable to enumerate Plex clients: %s", e)

    for tid in target_ids:
        for c in clients:
            for attr in ("machineIdentifier", "clientIdentifier"):
                if getattr(c, attr, None) and str(getattr(c, attr)) == tid:
                    return c, tid

    # 2) Name lookup by player title (sometimes works when identifiers don't)
    if ctx.player_title:
        try:
            c = plex.client(ctx.player_title)
            if c:
                return c, str(getattr(c, "machineIdentifier", "") or ctx.machine_id or "")
        except Exception:
            pass

    # 3) Proxy-only PlexClient with just the identifier (no direct connection required)
    try:
        from plexapi.client import PlexClient  # type: ignore
        for tid in target_ids:
            try:
                pc = PlexClient(server=plex, identifier=tid, connect=False, timeout=int(HTTP_TIMEOUT_S))
                # PlexClient.sendCommand uses .machineIdentifier; ensure it's set.
                pc.machineIdentifier = tid  # type: ignore
                pc.title = getattr(pc, "title", None) or "proxy:%s" % tid  # type: ignore
                pc.proxyThroughServer(True, server=plex)  # route commands via Plex server
                return pc, tid
            except Exception:
                continue
    except Exception as e:
        log.debug("PlexClient proxy fallback unavailable: %s", e)

    # 4) Direct connect by address/port (optional; can fail on NAT/relay)
    if ctx.player_address and ctx.player_port and target_ids:
        try:
            from plexapi.client import PlexClient  # type: ignore
            baseurl = "http://%s:%s" % (ctx.player_address, ctx.player_port)
            for tid in target_ids:
                try:
                    pc = PlexClient(server=plex, baseurl=baseurl, identifier=tid, connect=True, timeout=int(HTTP_TIMEOUT_S))
                    return pc, tid
                except Exception:
                    continue
        except Exception:
            pass

    return None, None


def plex_terminate_session(session_item: Optional[Any], session_id: Optional[str], reason: str) -> bool:
    """
    Terminate a session via Plex as a fallback (when Tautulli is unavailable or fails).

    We try two approaches:
      1) session_item.stop(reason=...) (plexapi convenience)
      2) direct call to /status/sessions/terminate?sessionId=...&reason=...&X-Plex-Token=...

    This is best-effort and will not throw.
    """
    # 1) plexapi stop()
    if session_item is not None:
        try:
            stop_fn = getattr(session_item, "stop", None)
            if callable(stop_fn):
                stop_fn(reason=reason)
                return True
        except Exception as e:
            log.debug("Plex session.stop() failed: %s", e)

    # 2) Direct API call
    if not PLEX_URL or not PLEX_EFFECTIVE_TOKEN or not session_id:
        return False

    try:
        # Some platforms have weird sessionId strings; keep it as-is unless it's obviously polluted.
        sid = str(session_id).strip()
        if "token=" in sid:
            sid = sid.split("token=", 1)[-1].strip()

        url = "%s/status/sessions/terminate" % PLEX_URL.rstrip("/")
        params = {"sessionId": sid, "reason": reason, "X-Plex-Token": PLEX_EFFECTIVE_TOKEN}
        r = PLEX_HTTP.get(url, params=params, timeout=HTTP_TIMEOUT_S)
        # Plex often returns 200 with an empty body on success.
        if 200 <= r.status_code < 300:
            return True
    except Exception as e:
        log.debug("Direct Plex terminate call failed: %s", e)

    return False


def terminate_best_effort(plex, ev: InputEvent, ctx: Optional[SessionContext], message: str) -> bool:
    """
    Terminate using every available method, in the fastest / most reliable order.
    """
    session_key = (ctx.session_key if ctx else None) or ev.session_key
    session_id = (ctx.session_id if ctx else None) or ev.session_id

    # 1) Preferred: Tautulli terminate_session
    if terminate_via_tautulli(session_key, session_id, message):
        return True

    # 2) Fallback: Plex termination
    session_item = ctx.session_item if ctx else None
    if plex_terminate_session(session_item, session_id, message):
        log.info("Plex termination fallback succeeded.")
        return True

    log.warning("All termination methods failed.")
    return False


# -------------------------
# Argument parsing
# -------------------------
def parse_args(argv: List[str]) -> InputEvent:
    """
    Supports two modes:
    1) Flag mode with --key=value or --key value (recommended; safe if values are blank)
    2) Legacy positional mode:

       {rating_key} {machine_id} {username} {session_id} {user_id} {resolution_hint} {video_decision} {video_dynamic_range}

    In positional mode the "resolution_hint" is not assumed to be source vs stream; it is treated as a hint only.
    """
    ev = InputEvent()

    # Flag mode if any arg starts with --
    if any(a.startswith("--") for a in argv[1:]):
        # Simple parser: --k=v or --k v
        i = 1
        while i < len(argv):
            a = argv[i]
            if not a.startswith("--"):
                i += 1
                continue

            key = a.lstrip("-")
            val: Optional[str] = None
            if "=" in key:
                key, val = key.split("=", 1)
            else:
                # --key value
                if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                    val = argv[i + 1]
                    i += 1

            key = key.replace("-", "_").strip().lower()
            if val is not None:
                val = str(val).strip()
                if val == "":
                    val = None

            # Map keys to fields (support common variants)
            if key in ("rating_key", "ratingkey"):
                ev.rating_key = val
            elif key in ("machine_id", "machineidentifier", "client_machine_id", "client_id"):
                ev.machine_id = val
            elif key in ("username", "user"):
                ev.username = val
            elif key in ("session_id", "sessionid"):
                ev.session_id = val
            elif key in ("session_key", "sessionkey"):
                ev.session_key = val
            elif key in ("user_id", "userid"):
                ev.user_id = val
            elif key in ("video_decision", "videodecision"):
                ev.video_decision = val
            elif key in ("video_resolution", "videoresolution"):
                ev.video_resolution = val
            elif key in ("stream_video_resolution", "streamvideoresolution"):
                ev.stream_video_resolution = val
            elif key in ("video_dynamic_range", "videodynamicrange", "dynamic_range", "dynamicrange"):
                ev.video_dynamic_range = val
            elif key in ("action", "trigger", "event"):
                ev.action = val

            i += 1

        return ev

    # Legacy positional mode
    if len(argv) < 8:
        raise SystemExit(
            "Usage (positional): script.py {rating_key} {machine_id} {username} {session_id} {user_id} "
            "{resolution_hint} {video_decision} {video_dynamic_range}"
        )

    ev.rating_key = argv[1]
    ev.machine_id = argv[2]
    ev.username = argv[3]
    ev.session_id = argv[4]
    ev.user_id = argv[5]
    resolution_hint = argv[6]
    ev.video_decision = argv[7]
    ev.video_dynamic_range = argv[8] if len(argv) > 8 else None

    # In legacy mode we store the provided resolution hint in stream_video_resolution (historical behavior),
    # but it's treated only as a hint.
    ev.stream_video_resolution = resolution_hint
    return ev


# -------------------------
# Main logic
# -------------------------
def log_event(level_name: str, msg: str, ev: Optional[InputEvent] = None, ctx: Optional[SessionContext] = None) -> None:
    """
    Single place to log to file/stderr and optionally to Tautulli via notify().
    """
    log.log(level_value(level_name), msg)

    # Keep notifications concise; only send important ones.
    if should_tautulli_notify(level_name):
        parts = [msg]
        if ev:
            parts.append("user=%s rating_key=%s session_id=%s decision=%s" % (ev.username, ev.rating_key, ev.session_id, ev.video_decision))
        if ctx:
            parts.append("client=%s offset_ms=%s" % (ctx.player_title or ctx.machine_id, ctx.view_offset_ms))
        tautulli_notify(level_name, TAUTULLI_LOG_SUBJECT, " | ".join(parts))


def main(argv: List[str]) -> int:
    ev = parse_args(argv)

    log.info(
        "Trigger: action=%s user=%s rating_key=%s session_id=%s session_key=%s machine_id=%s video_decision=%s "
        "video_resolution=%s stream_video_resolution=%s video_dynamic_range=%s",
        ev.action, ev.username, ev.rating_key, ev.session_id, ev.session_key, ev.machine_id, ev.video_decision,
        ev.video_resolution, ev.stream_video_resolution, ev.video_dynamic_range,
    )

    # User exemptions
    if ev.username and ev.username in EXEMPT_USERS:
        log_event("INFO", "User %s is exempt. Exiting." % ev.username, ev=ev)
        return 0

    # Only act on video transcodes
    if not is_video_transcoding(ev.video_decision):
        log_event("DEBUG", "Decision=%r is not a video transcode. No action." % (ev.video_decision,), ev=ev)
        return 0

    # Connect to Plex
    plex = None
    try:
        plex = connect_plex()
    except Exception as e:
        log_event("ERROR", "Plex connect failed: %s" % e, ev=ev)
        if KILL_ON_PLEX_CONNECT_FAIL:
            terminate_best_effort(plex, ev, None, KILL_MESSAGE_PLEX_CONNECT_FAIL)
        return 0

    # Find active session
    ctx = find_session(plex, ev)
    if ctx is None:
        # Without a session we cannot safely downshift. Fail-closed if configured.
        log_event("WARNING", "Unable to match Plex session for this event.", ev=ev)
        if KILL_ON_SESSION_NOT_FOUND:
            terminate_best_effort(plex, ev, None, KILL_MESSAGE_SESSION_NOT_FOUND)
        return 0

    # Confirm current media identity (source-of-truth)
    cur_mid, cur_h, cur_dr = current_media_identity(ctx.session_item)
    cur_drc = classify_dynamic_range(cur_dr)
    log.debug("Current media: id=%s height=%s dyn_range=%s", cur_mid, cur_h, cur_dr)

    # If the current source isn't high-quality, policy doesn't apply (you're just transcoding normal stuff).
    if not is_high_quality(cur_h, cur_dr):
        log_event("DEBUG", "Current source not high-quality (h=%s, dr=%s). No action." % (cur_h, cur_dr), ev=ev, ctx=ctx)
        return 0

    # If we're already on a non-4K SDR version, don't thrash.
    if cur_h is not None and cur_h < MAX_ALLOWED_HEIGHT and cur_drc == "SDR":
        log_event("DEBUG", "Already on <4K SDR. No further action.", ev=ev, ctx=ctx)
        return 0

    # Choose a fallback
    item_for_versions = ctx.session_item
    target_idx = pick_best_fallback_media_index(item_for_versions, cur_mid, cur_h, cur_dr)

    # If session metadata didn't expose all versions, retry using full library metadata once.
    if target_idx is None and ev.rating_key:
        try:
            item_for_versions = fetch_library_item(plex, ev.rating_key)
            target_idx = pick_best_fallback_media_index(item_for_versions, cur_mid, cur_h, cur_dr)
        except Exception as e:
            log_event("WARNING", "Unable to fetch library item for fallback selection: %s" % e, ev=ev, ctx=ctx)
            if KILL_ON_NO_FALLBACK_MEDIA:
                terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_NO_FALLBACK_MEDIA)
            return 0

    if target_idx is None:
        log_event("WARNING", "No suitable fallback media found (per policy/config).", ev=ev, ctx=ctx)
        if KILL_ON_NO_FALLBACK_MEDIA:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_NO_FALLBACK_MEDIA)
        return 0

    # Find controllable client
    client, identifier_used = find_client(plex, ctx, ev.machine_id)
    if not client:
        log_event("ERROR", "Unable to find a controllable Plex client for this session.", ev=ev, ctx=ctx)
        if KILL_ON_CLIENT_NOT_FOUND:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_CLIENT_NOT_FOUND)
        return 0

    # Switch attempt
    try:
        view_offset = ctx.view_offset_ms or 0

        log_event(
            "INFO",
            "Downshifting: mediaIndex=%s offset_ms=%s via_client_id=%s" % (target_idx, view_offset, identifier_used),
            ev=ev,
            ctx=ctx,
        )

        # PlexAPI builds a playQueue and issues playback/playMedia with mediaIndex and offset.
        client.playMedia(item_for_versions, offset=view_offset, mediaIndex=target_idx, partIndex=0)

        # Some clients ignore offset in playMedia; follow up with seekTo.
        if view_offset > 0:
            time.sleep(SEEK_DELAY_S)
            for attempt in range(1, SEEK_RETRIES + 1):
                try:
                    client.seekTo(view_offset)
                    break
                except Exception as e:
                    log.debug("seekTo attempt %s failed: %s", attempt, e)
                    time.sleep(SEEK_RETRY_DELAY_S)

        log_event("INFO", "Downshift command sent successfully.", ev=ev, ctx=ctx)
        return 0

    except Exception as e:
        log_event("ERROR", "Downshift failed: %s" % e, ev=ev, ctx=ctx)
        if KILL_ON_SWITCH_FAIL:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_SWITCH_FAIL)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SystemExit:
        raise
    except Exception as e:
        # Absolute last-ditch safety net.
        log_event("CRITICAL", "Unexpected error: %s" % e, ev=None, ctx=None)
        sys.exit(1)
