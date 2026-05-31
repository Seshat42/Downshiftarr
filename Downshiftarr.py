#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Downshiftarr v0.7.2
By Seshat42

Plex 4K/HDR/DV transcode guard (fail-closed by default) with best-effort auto-downshift.

What it does
------------
Downshiftarr is meant to be called by a Tautulli "Script" notification agent.

When a client is VIDEO transcoding a high-quality source (4K and/or HDR/DV), Downshiftarr will:

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

Arguments (flag mode):
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
  PROTECTED_SOURCE_MIN_HEIGHT=1081        # actual height >=1081 is protected 4K-ish
  REMUX_1080_MIN_BITRATE_KBPS=25000       # bitrate threshold for 1080 remux-like waterfall
  PREFER_HEIGHTS=1080,720,576,480,360     # fallback preference order
  AUTO_WATERFALL_ON_CONTINUED_TRANSCODE=1 # continue stepping down if transcode persists
  WATERFALL_MIN_HEIGHT=360                # lowest automatic waterfall target
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

import json
import logging
import os
import re
import sys
import time
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
TELEMETRY_FILE = env_str("TELEMETRY_FILE", "")
TELEMETRY_ENABLED = env_bool("TELEMETRY_ENABLED", True)
ENFORCEMENT_MODE = env_str("ENFORCEMENT_MODE", "targeted").lower()
SHADOW_MODE = env_bool("SHADOW_MODE", ENFORCEMENT_MODE == "shadow")
# Disabled for the production policy selected for Bragi. Keep the parser and
# historical state helpers inert so older env files cannot influence fallback.
ADAPTIVE_LEARNING_CONFIGURED = env_bool("ADAPTIVE_LEARNING_ENABLED", False)
ADAPTIVE_LEARNING_ENABLED = False
ADAPTIVE_LEARNING_LOCKED_DISABLED = True
ADAPTIVE_LEARNING_FILE = env_str("ADAPTIVE_LEARNING_FILE", "")
ADAPTIVE_MIN_SAMPLES = env_int("ADAPTIVE_MIN_SAMPLES", 30) or 30
ADAPTIVE_CONFIDENCE_MIN = env_float("ADAPTIVE_CONFIDENCE_MIN", 0.95)
ADAPTIVE_MAX_P95_MS = env_float("ADAPTIVE_MAX_P95_MS", 75.0)
ADAPTIVE_RECENT_OUTCOME_LIMIT = env_int("ADAPTIVE_RECENT_OUTCOME_LIMIT", 30) or 30
ADAPTIVE_BLOCKING_OUTCOMES = {
    "abandonment",
    "boundary_ambiguous",
    "continued_transcode",
    "downshift_failed",
    "edition_mismatch",
    "playback_failure",
    "switch_failed",
    "version_mismatch",
}

# Tautulli "logging" (notification) configuration
TAUTULLI_LOG_NOTIFIER_ID = env_int("TAUTULLI_LOG_NOTIFIER_ID", None)
TAUTULLI_LOG_MIN_LEVEL = env_str("TAUTULLI_LOG_MIN_LEVEL", "WARNING").upper()
TAUTULLI_LOG_SUBJECT = env_str("TAUTULLI_LOG_SUBJECT", "Downshiftarr")

# Policy knobs
EXEMPT_USERS = env_csv_set("EXEMPT_USERS", "")

PROTECTED_SOURCE_MIN_HEIGHT = env_int("PROTECTED_SOURCE_MIN_HEIGHT", env_int("MAX_ALLOWED_HEIGHT", 1081) or 1081) or 1081
MAX_ALLOWED_HEIGHT = PROTECTED_SOURCE_MIN_HEIGHT  # Backward-compatible alias for older tests/config.
HARD_PROTECT_1080_HDR = env_bool("HARD_PROTECT_1080_HDR", False)
HARD_PROTECT_1080_REMUX = env_bool("HARD_PROTECT_1080_REMUX", False)
REMUX_1080_MIN_BITRATE_KBPS = env_int("REMUX_1080_MIN_BITRATE_KBPS", 25_000) or 25_000
PREFER_HEIGHTS = tuple(int(x) for x in env_str("PREFER_HEIGHTS", "1080,720,576,480,360").split(",") if x.strip().isdigit()) or (
    1080,
    720,
    576,
    480,
    360,
)

FALLBACK_SDR_ONLY = env_bool("FALLBACK_SDR_ONLY", True)
ALLOW_HDR_FALLBACK = env_bool("ALLOW_HDR_FALLBACK", False)
AUTO_WATERFALL_ON_CONTINUED_TRANSCODE = env_bool("AUTO_WATERFALL_ON_CONTINUED_TRANSCODE", True)
WATERFALL_MIN_HEIGHT = env_int("WATERFALL_MIN_HEIGHT", 360) or 360
FOUR_K_TRANSCODE_ALLOWED = env_bool("FOUR_K_TRANSCODE_ALLOWED", False)

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
    "This protected version is still being prepared. Please retry shortly.",
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
    "direct play",
    "directplay",
    "direct_play",
    "direct stream",
    "directstream",
    "direct_stream",
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


def safe_client_family(*values: object) -> str:
    raw = " ".join(str(v or "") for v in values).lower()
    if "roku" in raw:
        return "roku"
    if "fire" in raw:
        return "fire_tv"
    if "shield" in raw:
        return "nvidia_shield"
    if "android tv" in raw or "google tv" in raw:
        return "android_tv"
    if "android" in raw:
        return "android"
    if "ipad" in raw or "ipados" in raw:
        return "ipados"
    if "iphone" in raw or "ios" in raw:
        return "ios"
    if "apple tv" in raw or "tvos" in raw:
        return "apple_tv"
    if "chromecast" in raw:
        return "chromecast"
    if "samsung" in raw or "tizen" in raw:
        return "samsung_tv"
    if "lg" in raw or "webos" in raw:
        return "lg_tv"
    if "xbox" in raw:
        return "xbox"
    if "playstation" in raw or "ps5" in raw or "ps4" in raw:
        return "playstation"
    if "relay" in raw:
        return "relay"
    if "web" in raw or "chrome" in raw or "firefox" in raw or "safari" in raw or "edge" in raw:
        return "plex_web"
    if "htpc" in raw or "desktop" in raw:
        return "desktop"
    if "windows" in raw or "macos" in raw or "linux" in raw:
        return "desktop"
    if "vizio" in raw or "vidaa" in raw or "hisense" in raw or "smart tv" in raw:
        return "smart_tv"
    return "unknown"


def _empty_telemetry() -> Dict[str, Any]:
    return {
        "version": 1,
        "outcomes": {},
        "client_families": {},
        "latency_ms": {"count": 0, "sum": 0.0, "max": 0.0, "samples": []},
        "latency_by_client_family": {},
    }


def _increment_telemetry_counter(root: Dict[str, Any], section: str, key: str) -> None:
    safe_key = re.sub(r"[^a-z0-9_.-]+", "_", str(key).lower()).strip("_") or "unknown"
    bucket = root.setdefault(section, {})
    row = bucket.setdefault(safe_key, {"count": 0})
    row["count"] = int(row.get("count", 0)) + 1


def _record_latency(bucket: Dict[str, Any], value: float) -> None:
    safe_value = round(max(0.0, float(value)), 3)
    bucket["count"] = int(bucket.get("count", 0)) + 1
    bucket["sum"] = round(float(bucket.get("sum", 0.0)) + safe_value, 3)
    bucket["max"] = round(max(float(bucket.get("max", 0.0)), safe_value), 3)
    samples = bucket.setdefault("samples", [])
    if isinstance(samples, list):
        samples.append(safe_value)
        del samples[:-256]
        ordered = sorted(float(v) for v in samples)
        idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999)))
        bucket["p95"] = round(ordered[idx], 3)


def record_telemetry(
    outcome: str,
    ev: Optional["InputEvent"] = None,
    ctx: Optional["SessionContext"] = None,
    *,
    latency_ms: Optional[float] = None,
) -> None:
    if not (TELEMETRY_ENABLED and TELEMETRY_FILE):
        return
    try:
        path = Path(TELEMETRY_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("version") != 1:
                data = _empty_telemetry()
        except Exception:
            data = _empty_telemetry()

        _increment_telemetry_counter(data, "outcomes", outcome)
        family = safe_client_family(
            getattr(ctx, "player_product", None),
            getattr(ctx, "player_title", None),
            getattr(ev, "video_decision", None),
        )
        _increment_telemetry_counter(data, "client_families", family)
        if latency_ms is not None:
            _record_latency(data.setdefault("latency_ms", {"count": 0, "sum": 0.0, "max": 0.0, "samples": []}), latency_ms)
            by_family = data.setdefault("latency_by_client_family", {})
            _record_latency(by_family.setdefault(family, {"count": 0, "sum": 0.0, "max": 0.0, "samples": []}), latency_ms)

        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        log.debug("Telemetry write failed", exc_info=True)


def sanitized_event_context(ev: Optional["InputEvent"] = None, ctx: Optional["SessionContext"] = None) -> str:
    parts: List[str] = []
    if ev:
        if ev.action:
            parts.append(f"action={re.sub(r'[^a-z0-9_.-]+', '_', ev.action.lower()).strip('_') or 'unknown'}")
        if ev.video_decision:
            parts.append(f"decision={re.sub(r'[^a-z0-9_.-]+', '_', ev.video_decision.lower()).strip('_') or 'unknown'}")
        if ev.video_dynamic_range:
            parts.append(f"dynamic_range={classify_dynamic_range(ev.video_dynamic_range)}")
        if ev.video_resolution or ev.stream_video_resolution:
            parts.append(
                "source_hint=%s stream_hint=%s"
                % (parse_resolution_hint(ev.video_resolution), parse_resolution_hint(ev.stream_video_resolution))
            )
    if ctx:
        parts.append(f"client_family={safe_client_family(ctx.player_product, ctx.player_title)}")
    return " ".join(parts) if parts else "context=none"


def _empty_learning_state() -> Dict[str, Any]:
    return {"version": 1, "client_families": {}}


def adaptive_learning_active() -> bool:
    return ADAPTIVE_LEARNING_ENABLED and not ADAPTIVE_LEARNING_LOCKED_DISABLED


def load_adaptive_learning() -> Dict[str, Any]:
    if not (adaptive_learning_active() and ADAPTIVE_LEARNING_FILE):
        return _empty_learning_state()
    try:
        data = json.loads(Path(ADAPTIVE_LEARNING_FILE).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            return _empty_learning_state()
        families = data.get("client_families")
        if not isinstance(families, dict):
            return _empty_learning_state()
        return data
    except Exception:
        return _empty_learning_state()


def save_adaptive_learning(data: Dict[str, Any]) -> None:
    if not (adaptive_learning_active() and ADAPTIVE_LEARNING_FILE):
        return
    try:
        path = Path(ADAPTIVE_LEARNING_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        log.debug("Adaptive learning write failed", exc_info=True)


def adaptive_candidate_key(source_height: Optional[int], source_dr: str, target_height: Optional[int], target_dr: str) -> str:
    source = source_height if source_height is not None else "unknown"
    target = target_height if target_height is not None else "unknown"
    return f"{source}_{classify_dynamic_range(source_dr)}_to_{target}_{classify_dynamic_range(target_dr)}"


def adaptive_record_candidate(
    family: str,
    source_height: Optional[int],
    source_dr: str,
    target_height: Optional[int],
    target_dr: str,
    outcome: str,
    *,
    latency_ms: Optional[float] = None,
) -> None:
    if not adaptive_learning_active():
        return
    safe_outcome = re.sub(r"[^a-z0-9_.-]+", "_", str(outcome).lower()).strip("_") or "unknown"
    data = load_adaptive_learning()
    family_row = data.setdefault("client_families", {}).setdefault(family or "unknown", {"candidates": {}})
    candidates = family_row.setdefault("candidates", {})
    key = adaptive_candidate_key(source_height, source_dr, target_height, target_dr)
    row = candidates.setdefault(
        key,
        {
            "source_height": source_height,
            "source_dynamic_range": classify_dynamic_range(source_dr),
            "target_height": target_height,
            "target_dynamic_range": classify_dynamic_range(target_dr),
        },
    )
    row[safe_outcome] = int(row.get(safe_outcome, 0)) + 1
    recent = row.setdefault("recent_outcomes", [])
    if isinstance(recent, list):
        recent.append(safe_outcome)
        del recent[:-ADAPTIVE_RECENT_OUTCOME_LIMIT]
    if latency_ms is not None:
        _record_latency(row.setdefault("latency_ms", {"count": 0, "sum": 0.0, "max": 0.0, "samples": []}), latency_ms)
    save_adaptive_learning(data)


def adaptive_preferred_height(family: str, source_height: Optional[int], source_dr: str) -> Optional[int]:
    family = safe_client_family(family)
    if not (adaptive_learning_active() and source_height is not None):
        return None
    if family == "unknown":
        return None
    source_drc = classify_dynamic_range(source_dr)
    data = load_adaptive_learning()
    candidates = data.get("client_families", {}).get(family or "unknown", {}).get("candidates", {})
    best: Optional[Tuple[float, int, int]] = None
    for row in candidates.values():
        try:
            if int(row.get("source_height")) != int(source_height):
                continue
            if str(row.get("source_dynamic_range", "")).upper() != source_drc:
                continue
            target_height = int(row.get("target_height"))
            if target_height >= int(source_height) or target_height < WATERFALL_MIN_HEIGHT:
                continue
            attempts = int(row.get("downshift_sent", 0)) + int(row.get("shadow_candidates", 0))
            successes = int(row.get("success", 0))
            continued = int(row.get("continued_transcode", 0))
            abandoned = int(row.get("abandonment", 0))
            other_failures = sum(
                int(row.get(name, 0)) for name in ADAPTIVE_BLOCKING_OUTCOMES if name not in {"continued_transcode", "abandonment"}
            )
            observed = successes + continued + abandoned + other_failures
            samples = observed if observed > 0 else attempts
            if samples < ADAPTIVE_MIN_SAMPLES:
                continue
            confidence = max(0.0, successes / max(1, observed)) if observed > 0 else 0.0
            if confidence < ADAPTIVE_CONFIDENCE_MIN:
                continue
            recent = row.get("recent_outcomes", [])
            if isinstance(recent, list) and any(str(v) in ADAPTIVE_BLOCKING_OUTCOMES for v in recent[-ADAPTIVE_RECENT_OUTCOME_LIMIT:]):
                continue
            if any(int(row.get(name, 0)) > 0 for name in ("boundary_ambiguous", "edition_mismatch", "version_mismatch")):
                continue
            latency = row.get("latency_ms", {})
            p95 = None
            if isinstance(latency, dict):
                try:
                    p95 = float(latency.get("p95"))
                except (TypeError, ValueError):
                    samples_list = latency.get("samples")
                    if isinstance(samples_list, list) and samples_list:
                        ordered = sorted(float(v) for v in samples_list)
                        idx = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.95 + 0.999999)))
                        p95 = ordered[idx]
            if p95 is None or p95 >= ADAPTIVE_MAX_P95_MS:
                continue
            candidate = (confidence, samples, target_height)
            if best is None or candidate > best:
                best = candidate
        except Exception:
            continue
    return best[2] if best is not None else None


def record_adaptive_observation_from_event(ev: "InputEvent") -> bool:
    """Record a sanitized aggregate outcome event and return True if handled.

    This supports Tautulli outcome hooks without touching Plex. It intentionally
    accepts only coarse client-family/media-risk fields and rejects identifiers.
    """
    if not ev.adaptive_outcome:
        return False
    outcome = re.sub(r"[^a-z0-9_.-]+", "_", ev.adaptive_outcome.lower()).strip("_")
    if outcome not in {"success", "continued_transcode", "abandonment", "playback_failure", "downshift_failed"}:
        log_event("WARNING", f"Unsupported adaptive outcome ignored: {outcome}", ev=ev)
        return True
    family = safe_client_family(ev.client_family or "")
    if family == "unknown":
        log_event("WARNING", "Adaptive outcome ignored for unknown client family.", ev=ev)
        return True
    source_height = parse_resolution_hint(ev.video_resolution or ev.stream_video_resolution)
    target_height = parse_resolution_hint(ev.target_video_resolution)
    if source_height is None or target_height is None:
        log_event("WARNING", "Adaptive outcome ignored because source/target height is missing.", ev=ev)
        return True
    latency_ms = ev.decision_latency_ms
    if latency_ms is not None:
        latency_ms = max(0.0, min(float(latency_ms), 10_000.0))
    adaptive_record_candidate(
        family,
        source_height,
        ev.video_dynamic_range or "UNKNOWN",
        target_height,
        ev.target_video_dynamic_range or "UNKNOWN",
        outcome,
        latency_ms=latency_ms,
    )
    record_telemetry(outcome, ev, None, latency_ms=latency_ms)
    return True


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
    # Optional sanitized adaptive-outcome ingestion. This path is intended for
    # Tautulli Playback Stop/Decision Change hooks after a prior shadow/write
    # decision and must not carry raw session/user/device identifiers.
    adaptive_outcome: Optional[str] = None
    client_family: Optional[str] = None
    target_video_resolution: Optional[str] = None
    target_video_dynamic_range: Optional[str] = None
    decision_latency_ms: Optional[float] = None


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


def media_file_path(media_obj) -> str:
    try:
        for part in getattr(media_obj, "parts", []) or []:
            path = str(getattr(part, "file", "") or "").strip()
            if path:
                return path
    except Exception:
        pass
    return ""


def media_bitrate_kbps(media_obj) -> Optional[int]:
    for attr in ("bitrate", "videoBitrate", "videoBitrateKbps"):
        value = safe_int(getattr(media_obj, attr, None))
        if value:
            return value
    try:
        for part in getattr(media_obj, "parts", []) or []:
            value = safe_int(getattr(part, "bitrate", None))
            if value:
                return value
    except Exception:
        pass
    return None


def file_path_looks_remux(file_path: str) -> bool:
    name = os.path.basename(str(file_path or "")).lower()
    return bool(re.search(r"(?<![a-z0-9])remux(?![a-z0-9])", name))


def media_audio_risk(media_obj) -> int:
    """Lower is better. Prefer broadly compatible audio for client UX."""
    risk = 0
    try:
        for part in getattr(media_obj, "parts", []) or []:
            for stream in getattr(part, "streams", []) or []:
                if safe_int(getattr(stream, "streamType", None)) != 2:
                    continue
                codec = str(getattr(stream, "codec", "") or getattr(stream, "audioCodec", "") or "").lower()
                channels = safe_int(getattr(stream, "channels", None)) or 0
                if codec in {"truehd", "dts", "dca", "dtsma", "flac"}:
                    risk += 4
                elif codec in {"eac3", "ac3"}:
                    risk += 1
                elif codec and codec not in {"aac", "mp3", "opus"}:
                    risk += 2
                if channels > 6:
                    risk += 2
                elif channels > 2:
                    risk += 1
    except Exception:
        return 3
    return risk


def media_subtitle_risk(media_obj) -> int:
    """Lower is better. Image/forced subtitles can trigger burn-in."""
    risk = 0
    try:
        for part in getattr(media_obj, "parts", []) or []:
            for stream in getattr(part, "streams", []) or []:
                if safe_int(getattr(stream, "streamType", None)) != 3:
                    continue
                codec = str(getattr(stream, "codec", "") or "").lower()
                forced = str(getattr(stream, "forced", "") or "").lower() in {"1", "true", "yes"}
                if codec in {"pgs", "vobsub", "dvd_subtitle"}:
                    risk += 3
                if forced:
                    risk += 1
    except Exception:
        return 2
    return risk


_EDITION_TOKEN_RE = re.compile(r"\{edition-([^{}]+)\}", re.IGNORECASE)


def normalize_edition_key(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def edition_key_from_path(path: Optional[str]) -> str:
    if not path:
        return ""
    match = _EDITION_TOKEN_RE.search(str(path))
    if not match:
        return ""
    return normalize_edition_key(match.group(1))


def media_edition_key(media_obj) -> str:
    """Return a conservative Plex Edition key for a media version."""
    for attr in ("editionTitle", "edition", "editionName", "editionDisplayTitle"):
        value = getattr(media_obj, attr, None)
        key = normalize_edition_key(value)
        if key:
            return key
    try:
        for part in getattr(media_obj, "parts", []) or []:
            key = edition_key_from_path(getattr(part, "file", None))
            if key:
                return key
    except Exception:
        pass
    return ""


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


def is_protected_source_height(height: Optional[int]) -> bool:
    return height is not None and height >= MAX_ALLOWED_HEIGHT


def is_1080_remux_like(height: Optional[int], file_path: str = "", bitrate_kbps: Optional[int] = None) -> bool:
    if height != 1080:
        return False
    if file_path_looks_remux(file_path):
        return True
    return bitrate_kbps is not None and bitrate_kbps >= REMUX_1080_MIN_BITRATE_KBPS


def is_hard_protected_source(height: Optional[int], dyn_range: str, file_path: str = "", bitrate_kbps: Optional[int] = None) -> bool:
    if is_protected_source_height(height):
        return True
    if HARD_PROTECT_1080_HDR and height == 1080 and classify_dynamic_range(dyn_range) not in ("SDR", "UNKNOWN"):
        return True
    if HARD_PROTECT_1080_REMUX and is_1080_remux_like(height, file_path, bitrate_kbps):
        return True
    return False


def is_high_quality(height: Optional[int], dyn_range: str) -> bool:
    """
    A "high quality" source is:
    - protected 4K-ish by height threshold, OR
    - optionally hard-protected 1080 HDR/DV, OR
    - anything clearly not SDR (HDR / DV / HLG / etc) for waterfall action
    """
    if is_hard_protected_source(height, dyn_range):
        return True
    drc = classify_dynamic_range(dyn_range)
    if drc not in ("SDR", "UNKNOWN"):
        return True
    return False


def should_waterfall_continued_transcode(height: Optional[int], dyn_range: str) -> bool:
    """
    True when the stream is already on an unprotected version but still transcoding,
    so another lower available version may be a better client fit.
    """
    if not AUTO_WATERFALL_ON_CONTINUED_TRANSCODE:
        return False
    if height is None or height <= WATERFALL_MIN_HEIGHT:
        return False
    if is_hard_protected_source(height, dyn_range):
        return False
    return True


def fetch_library_item(plex, rating_key: str):
    """
    Fetch full library metadata for a rating_key (for version list).
    """
    return plex.fetchItem(f"/library/metadata/{rating_key}")


def session_rating_key(ctx: SessionContext) -> Optional[str]:
    value = getattr(ctx.session_item, "ratingKey", None)
    if value is None:
        return None
    value_s = str(value).strip()
    return value_s or None


def current_media_identity(item) -> Tuple[Optional[str], Optional[int], str, str]:
    """
    Determine the *currently selected* Media: (media_id, height, dynamic_range, file_path)
    """
    try:
        media_list = getattr(item, "media", []) or []
        for m in media_list:
            if getattr(m, "selected", False):
                mid = getattr(m, "id", None)
                return (str(mid) if mid is not None else None, media_height(m), media_dynamic_range(m), media_file_path(m))
        if media_list:
            m0 = media_list[0]
            return (str(getattr(m0, "id", None)), media_height(m0), media_dynamic_range(m0), media_file_path(m0))
    except Exception:
        pass
    return (None, None, "UNKNOWN", "")


def current_media_bitrate_kbps(item) -> Optional[int]:
    try:
        media_list = getattr(item, "media", []) or []
        for m in media_list:
            if getattr(m, "selected", False):
                return media_bitrate_kbps(m)
        if media_list:
            return media_bitrate_kbps(media_list[0])
    except Exception:
        pass
    return None


def pick_best_fallback_media_index(
    item,
    current_media_id: Optional[str],
    current_height: Optional[int],
    current_dr: str,
    preferred_height: Optional[int] = None,
) -> Optional[int]:
    """
    Choose the best fallback media index.

    Default behavior: SDR-only and < MAX_ALLOWED_HEIGHT.

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

    def candidate_score(media_obj, h: int) -> Tuple[int, int, int, int]:
        if preferred_height is not None and h == preferred_height:
            return (-1, media_audio_risk(media_obj), media_subtitle_risk(media_obj), -h)
        if h in PREFER_HEIGHTS:
            pref_rank = PREFER_HEIGHTS.index(h)
        else:
            # After preferred heights, pick the biggest under the max.
            pref_rank = len(PREFER_HEIGHTS) + (MAX_ALLOWED_HEIGHT - h)
        return (pref_rank, media_audio_risk(media_obj), media_subtitle_risk(media_obj), -h)

    cur_drc = classify_dynamic_range(current_dr)

    media_list = getattr(item, "media", []) or []
    if not media_list:
        return None
    current_edition = ""
    for m in media_list:
        mid = str(getattr(m, "id", "") or "")
        if (current_media_id and mid == current_media_id) or getattr(m, "selected", False):
            current_edition = media_edition_key(m)
            break

    # Two-pass selection:
    #   pass 1: SDR-only (preferred)
    #   pass 2: allow HDR/DV (optional)
    passes: List[Tuple[str, bool]] = []
    if FALLBACK_SDR_ONLY:
        # Strict mode: only consider SDR candidates.
        passes = [("SDR_ONLY", True)]
    else:
        if ALLOW_HDR_FALLBACK:
            # Prefer SDR if possible, but allow HDR/DV if no SDR fallback exists.
            passes = [("SDR_PREFERRED", True), ("ALLOW_HDR", False)]
        else:
            # Loose mode: allow HDR/DV candidates immediately (still under MAX_ALLOWED_HEIGHT).
            passes = [("ALLOW_HDR_ONLY", False)]

    for pass_name, sdr_only in passes:
        candidates: List[Tuple[int, int, str, Tuple[int, int, int, int]]] = []
        for idx, m in enumerate(media_list):
            mid = str(getattr(m, "id", "") or "")
            if current_media_id and mid == current_media_id:
                continue
            if media_edition_key(m) != current_edition:
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

            candidates.append((idx, h, dr, candidate_score(m, h)))

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
                        best_payload = (
                            s,
                            sk,
                            sid,
                            uname,
                            mid,
                            str(ptitle) if ptitle is not None else None,
                            str(pproduct) if pproduct is not None else None,
                            str(paddr) if paddr is not None else None,
                            str(pport) if pport is not None else None,
                        )
                    if best_score == 0:
                        break

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
                resolved = str(getattr(c, "machineIdentifier", "") or getattr(c, "clientIdentifier", "") or "")
                if target_ids and resolved and resolved not in target_ids:
                    log.warning("Player title lookup returned mismatched client identifier; refusing remote control.")
                    return None, None
                return c, resolved or (ctx.machine_id or "")
        except Exception:
            pass

    # 3) Proxy only PlexClient with just the identifier (no direct connection required)
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
      2) direct call to /status/sessions/terminate?sessionId=...&reason=... (token in header)

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
        params = {"sessionId": sid, "reason": reason}
        headers = {"X-Plex-Token": PLEX_EFFECTIVE_TOKEN}
        r = PLEX_HTTP.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT_S)
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
            elif key in ("adaptive_outcome", "adaptiveoutcome", "outcome"):
                ev.adaptive_outcome = val
            elif key in ("client_family", "clientfamily"):
                ev.client_family = val
            elif key in ("target_video_resolution", "targetvideoresolution", "target_resolution", "targetresolution"):
                ev.target_video_resolution = val
            elif key in (
                "target_video_dynamic_range",
                "targetvideodynamicrange",
                "target_dynamic_range",
                "targetdynamicrange",
            ):
                ev.target_video_dynamic_range = val
            elif key in ("decision_latency_ms", "decisionlatencyms"):
                try:
                    ev.decision_latency_ms = float(val) if val is not None else None
                except (TypeError, ValueError):
                    ev.decision_latency_ms = None

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
        parts.append(sanitized_event_context(ev, ctx))
        tautulli_notify(level_name, TAUTULLI_LOG_SUBJECT, " | ".join(parts))


def main(argv: List[str]) -> int:
    start_ts = time.monotonic()
    ev = parse_args(argv)

    log.info("Trigger: %s", sanitized_event_context(ev, None))

    if record_adaptive_observation_from_event(ev):
        return 0

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
    cur_mid, cur_h, cur_dr, cur_path = current_media_identity(ctx.session_item)
    cur_bitrate = current_media_bitrate_kbps(ctx.session_item)
    log.debug("Current media: id=%s height=%s dyn_range=%s", cur_mid, cur_h, cur_dr)

    remux_waterfall = is_1080_remux_like(cur_h, cur_path, cur_bitrate)
    protected_source = is_high_quality(cur_h, cur_dr) or remux_waterfall
    four_k_transcode_blocked = is_protected_source_height(cur_h) and not FOUR_K_TRANSCODE_ALLOWED
    continued_waterfall = should_waterfall_continued_transcode(cur_h, cur_dr) or remux_waterfall
    client_family = safe_client_family(ctx.player_product, ctx.player_title, ev.video_decision)

    # If the current source isn't protected and waterfall is not useful, policy doesn't apply.
    if not protected_source and not continued_waterfall:
        log_event("DEBUG", "Current source not high-quality (h=%s, dr=%s). No action." % (cur_h, cur_dr), ev=ev, ctx=ctx)
        return 0

    # Choose a fallback. The active session is useful for matching/continuity,
    # but fallback choices must use current Plex library metadata.
    item_for_versions = None
    matched_session_rating_key = session_rating_key(ctx)
    authoritative_rating_key = matched_session_rating_key or ev.rating_key
    if ev.rating_key and matched_session_rating_key and ev.rating_key != matched_session_rating_key:
        log_event("WARNING", "Tautulli event rating key mismatched matched Plex session; using session authority.", ev=ev, ctx=ctx)
    if authoritative_rating_key:
        try:
            item_for_versions = fetch_library_item(plex, authoritative_rating_key)
        except Exception as e:
            log_event("WARNING", "Unable to fetch authoritative library metadata for fallback selection: %s" % e, ev=ev, ctx=ctx)
            if four_k_transcode_blocked:
                terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_NO_FALLBACK_MEDIA)
            return 0
    else:
        log_event("WARNING", "Unable to determine authoritative rating key for fallback selection.", ev=ev, ctx=ctx)
        if four_k_transcode_blocked:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_NO_FALLBACK_MEDIA)
        return 0
    preferred_height = adaptive_preferred_height(client_family, cur_h, cur_dr)
    target_idx = pick_best_fallback_media_index(item_for_versions, cur_mid, cur_h, cur_dr, preferred_height=preferred_height)

    if target_idx is None:
        log_event("WARNING", "No suitable fallback media found (per policy/config).", ev=ev, ctx=ctx)
        if four_k_transcode_blocked:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_NO_FALLBACK_MEDIA)
        return 0
    target_media = (getattr(item_for_versions, "media", []) or [None])[target_idx]
    target_h = media_height(target_media) if target_media is not None else None
    target_dr = media_dynamic_range(target_media) if target_media is not None else "UNKNOWN"

    if SHADOW_MODE and not four_k_transcode_blocked:
        elapsed_ms = (time.monotonic() - start_ts) * 1000.0
        adaptive_record_candidate(
            client_family,
            cur_h,
            cur_dr,
            target_h,
            target_dr,
            "shadow_candidates",
            latency_ms=elapsed_ms,
        )
        record_telemetry("shadow_downshift_candidate", ev, ctx, latency_ms=elapsed_ms)
        log_event(
            "INFO",
            "%s shadow candidate: mediaIndex=%s offset_ms=%s"
            % (
                "Waterfall downshift" if continued_waterfall and not protected_source else "Downshift",
                target_idx,
                ctx.view_offset_ms or 0,
            ),
            ev=ev,
            ctx=ctx,
        )
        return 0
    if SHADOW_MODE and four_k_transcode_blocked:
        log_event("WARNING", "Shadow mode overridden because 4K transcode is not allowed.", ev=ev, ctx=ctx)

    # Find controllable client
    client, identifier_used = find_client(plex, ctx, ev.machine_id)
    if not client:
        log_event("ERROR", "Unable to find a controllable Plex client for this session.", ev=ev, ctx=ctx)
        if four_k_transcode_blocked or KILL_ON_CLIENT_NOT_FOUND:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_CLIENT_NOT_FOUND)
        return 0

    # Switch attempt
    try:
        view_offset = ctx.view_offset_ms or 0

        log_event(
            "INFO",
            "%s: mediaIndex=%s offset_ms=%s via_client_id=%s"
            % (
                "Waterfall downshift" if continued_waterfall and not protected_source else "Downshifting",
                target_idx,
                view_offset,
                identifier_used,
            ),
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

        elapsed_ms = (time.monotonic() - start_ts) * 1000.0
        record_telemetry("downshift_sent", ev, ctx, latency_ms=elapsed_ms)
        adaptive_record_candidate(client_family, cur_h, cur_dr, target_h, target_dr, "downshift_sent", latency_ms=elapsed_ms)
        log_event("INFO", "Downshift command sent successfully.", ev=ev, ctx=ctx)
        return 0

    except Exception as e:
        elapsed_ms = (time.monotonic() - start_ts) * 1000.0
        record_telemetry("downshift_failed", ev, ctx, latency_ms=elapsed_ms)
        adaptive_record_candidate(client_family, cur_h, cur_dr, target_h, target_dr, "downshift_failed", latency_ms=elapsed_ms)
        log_event("ERROR", "Downshift failed: %s" % e, ev=ev, ctx=ctx)
        if four_k_transcode_blocked or KILL_ON_SWITCH_FAIL:
            terminate_best_effort(plex, ev, ctx, KILL_MESSAGE_SWITCH_FAIL)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SystemExit:
        raise
    except Exception as e:
        # Absolute last-ditch safety net.
        #
        # If something blows up outside the normal control flow, we still try to enforce the policy.
        # We intentionally "fail closed" here: if the event looks like a protected transcode and KILL_ON_UNEXPECTED_ERROR is enabled, we attempt termination via every available path.
        try:
            ev = parse_args(sys.argv)
        except Exception:
            ev = None

        log_event("CRITICAL", "Unexpected error: %s" % e, ev=ev, ctx=None)

        if KILL_ON_UNEXPECTED_ERROR and ev is not None:
            try:
                # No Plex handle in this context; terminate_best_effort will try Tautulli first, then fall back to any direct Plex termination paths it can.
                terminate_best_effort(None, ev, None, KILL_MESSAGE_UNEXPECTED_ERROR)
            except Exception:
                pass

        sys.exit(1)
