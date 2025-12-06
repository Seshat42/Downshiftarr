#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Author: Seshat42
Version: 0.0.2

Plex transcode guard with waterfall auto-switch (plexapi) + Tautulli fallback.

"""

from __future__ import annotations
import argparse
import logging
import sys
import time
from typing import Optional, Tuple, List, Dict

import requests
from plexapi.server import PlexServer

# =======================
# USER CONFIG – EDIT THIS
# =======================
PLEX_URL = ""
PLEX_TOKEN = ""

TAUTULLI_URL = ""
TAUTULLI_APIKEY = ""

# Users to skip entirely (exact username matches, case-sensitive)
EXEMPT_USERS = {"Debug User"}

# Show this if we must terminate a 4K transcode and there's no lower version:
KILL_MESSAGE = "This title cannot be streamed in 4K/HDR/DV via the current device. Please select a 1080p (or lower) version via the 3 dot menu."

ENFORCE_DIRECT_2160 = True
ENFORCE_DIRECT_1080 = True
ENFORCE_DIRECT_720  = False
BLOCK_HDR_TRANSCODING = True
RUNG_ORDER = [2160, 1440, 1080, 720, 576, 480, 360, 240]

ALLOW_ON_DIRECT_STATES = {
    "directplay", "direct play", "direct_play",
    "directstream", "direct stream", "direct_stream",
    "copy"
}

def is_direct(decision: str) -> bool:
    return (decision or "").strip().lower() in ALLOW_ON_DIRECT_STATES

# ==============
# Logging (stdout)
# ==============
log = logging.getLogger("plex_transcode_guard")
if not log.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    log.addHandler(h)
log.setLevel(logging.INFO)

# ==========
# Utilities
# ==========

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Plex transcode guard with waterfall switch")
    p.add_argument("rating_key")
    p.add_argument("client_machine_id")  # {machine_id}
    p.add_argument("username")
    p.add_argument("session_id")
    p.add_argument("user_id")
    p.add_argument("source_resolution")   # e.g. "4k", "2160p", "1080p"
    p.add_argument("video_decision")      # e.g. "transcode", "copy"
    p.add_argument("video_dynamic_range", nargs="?")  # "SDR", "HDR", "Dolby Vision"
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()

def connect_plex() -> PlexServer:
    if not PLEX_URL or not PLEX_TOKEN:
        log.error("Configure PLEX_URL and PLEX_TOKEN at the top of the script.")
        sys.exit(1)
    return PlexServer(PLEX_URL, PLEX_TOKEN)

def require_direct_for_height(h: Optional[int]) -> bool:
    if h is None: return False
    if h >= 2160: return True
    if h >= 1080: return ENFORCE_DIRECT_1080
    if h >= 720: return ENFORCE_DIRECT_720
    return False

def parse_height_from_source(res: str) -> Optional[int]:
    s = (res or "").lower().replace("p", "")
    digits = "".join(c for c in s if c.isdigit())
    if not digits: return None
    try: return int(digits)
    except: return None

def looks_4k_from_str(res: str) -> bool:
    r = (res or "").lower()
    return "2160" in r or "4k" in r

def get_session_and_player(plex: PlexServer, session_id: str, rating_key: str, username: str, machine_id: str):
    """
    Retry logic + Fuzzy Fallback + DEBUG LOGGING
    """
    attempts = 4
    for i in range(attempts):
        try:
            sessions = plex.sessions()
        except Exception as e:
            log.warning("Failed to query plex sessions: %s", e)
            sessions = []

        log.info("DEBUG: Attempt %s/%s - Found %d sessions on Plex.", i+1, attempts, len(sessions))

        for s in sessions:
            try:
                # Gather Session Data
                s_key = getattr(s, "sessionKey", None)
                
                # --- FIX: Safe extraction of Session ID ---
                raw_session = getattr(s, "session", None)
                s_id = None
                if raw_session:
                    if hasattr(raw_session, "get"): # It's a dict
                        s_id = raw_session.get("id")
                    else: # It's an object
                        s_id = getattr(raw_session, "id", None)
                # ------------------------------------------

                s_users = [u.lower() for u in getattr(s, "usernames", [])]
                s_player = getattr(s, "players", [None])[0]
                s_machine = getattr(s_player, "machineIdentifier", "")
                s_rating = getattr(s, "ratingKey", "")

                # Debug Print for EVERY session found
                log.info(
                    " >> CANDIDATE: User=%s | Machine=%s | SessID=%s | Key=%s | RatingKey=%s",
                    s_users, s_machine, s_id, s_key, s_rating
                )

                # 1. Match by Session ID (Exact)
                is_id_match = (str(s_id) == session_id) or (str(s_key) == session_id)

                # 2. Match by User + Machine ID (Fuzzy Fallback)
                # We allow 'machine_id' to be IN 's_machine' or vice versa to catch suffix mismatches
                user_match = username.lower() in s_users
                machine_match = (machine_id in s_machine) or (s_machine in machine_id)
                is_fallback_match = user_match and machine_match

                if is_id_match or is_fallback_match:
                    if str(s_rating) == str(rating_key):
                        log.info("MATCH FOUND! (Method: %s)", "ID" if is_id_match else "Fallback")
                        return s, s, s_player
                    else:
                        # Session found, but RatingKey mismatch (old item?)
                        log.info("Session matched but RatingKey diff (%s vs %s). Re-fetching item...", s_rating, rating_key)
                        try:
                            vid_obj = plex.fetchItem(int(rating_key))
                            return vid_obj, s, s_player
                        except:
                            pass
            except Exception as e:
                log.error("Error checking session candidate: %s", e)
                continue
        
        if i < attempts - 1:
            time.sleep(2.0)
    
    return None, None, None

def current_height_and_dr(vid_obj) -> Tuple[Optional[int], Optional[str]]:
    height = None
    dr = None
    try:
        for m in getattr(vid_obj, "media", []) or []:
            h = getattr(m, "videoResolution", None)
            if h:
                try:
                    height_candidate = int(str(h).replace("p", "").replace("k", "").strip())
                    if height is None or height_candidate > height:
                        height = height_candidate
                except: pass
            for part in getattr(m, "parts", []) or []:
                dr = dr or getattr(part, "videoDynamicRange", None)
    except: pass
    return height, dr

def pick_next_rung(cur_height: int, prefer_sdr: bool) -> Optional[int]:
    order = [h for h in RUNG_ORDER if h != 2160]
    if prefer_sdr: return cur_height if cur_height != 2160 else 1080
    for h in order:
        if h < cur_height: return h
    return None

def find_media_index_for_height(video_obj, target_height: int, prefer_sdr: bool) -> Optional[int]:
    try:
        best_idx = None
        for idx, m in enumerate(getattr(video_obj, "media", []) or []):
            try:
                h = getattr(m, "videoResolution", None)
                if not h: continue
                try: hh = int(str(h).replace("p", "").replace("k", "").strip())
                except: continue
                if hh != target_height: continue
                if prefer_sdr:
                    any_hdr = False
                    for part in getattr(m, "parts", []) or []:
                        dr = getattr(part, "videoDynamicRange", "") or ""
                        if dr and dr.upper() != "SDR":
                            any_hdr = True
                            break
                    if any_hdr: continue
                best_idx = idx
                break
            except: continue
        return best_idx
    except Exception as e:
        log.warning("Failed to choose media index: %s", e)
        return None

def tautulli_terminate(session_id: str, message: str) -> None:
    if not TAUTULLI_URL or not TAUTULLI_APIKEY: return
    try:
        params = {"apikey": TAUTULLI_APIKEY, "cmd": "terminate_session", "session_id": session_id, "message": message}
        requests.get(f"{TAUTULLI_URL.rstrip('/')}/api/v2", params=params, timeout=10)
        log.info("Tautulli terminate_session sent.")
    except Exception as e:
        log.warning("Failed to call Tautulli terminate_session: %s", e)

def main() -> int:
    args = parse_args()
    log.info("Trigger: user=%s session=%s rating_key=%s decision=%s src_res=%s",
             args.username, args.session_id, args.rating_key, args.video_decision, args.source_resolution)

    if is_direct(args.video_decision):
        log.info("Already direct. No action.")
        return 0

    if args.username in EXEMPT_USERS:
        log.info("User %s is exempt.", args.username)
        return 0

    plex = connect_plex()
    video_obj, session_obj, client = get_session_and_player(
        plex, args.session_id, args.rating_key, args.username, args.client_machine_id
    )

    if not video_obj or not client:
        log.warning("Unable to locate active session/player after retries.")
        return 0

    cur_height, cur_dr = current_height_and_dr(video_obj)
    if cur_height is None: cur_height = parse_height_from_source(args.source_resolution)
    
    cur_is_4k = (cur_height is not None and cur_height >= 2160) or looks_4k_from_str(args.source_resolution)
    dr_flag = (args.video_dynamic_range or cur_dr or "SDR").upper()
    is_hdr_like = dr_flag != "SDR"

    enforce = require_direct_for_height(cur_height) or (BLOCK_HDR_TRANSCODING and is_hdr_like)
    if cur_is_4k: enforce = True

    if not enforce:
        log.info("Not enforcing (height=%s, DR=%s).", cur_height, dr_flag)
        return 0

    prefer_sdr = is_hdr_like and (cur_height or 0) < 2160
    target_height = pick_next_rung(cur_height or 2160, prefer_sdr=prefer_sdr)
    
    if target_height is None:
        log.info("No lower rung available. Waterfall end.")
        return 0

    target_index = find_media_index_for_height(video_obj, target_height, prefer_sdr=prefer_sdr)
    if target_index is None:
        log.info("No media at %sp (SDR=%s).", target_height, prefer_sdr)
        if cur_is_4k: tautulli_terminate(args.session_id, KILL_MESSAGE)
        return 0

    try:
        offset_ms = getattr(video_obj, "viewOffset", None) or 0
        client.playMedia(video_obj, offset=offset_ms, mediaIndex=target_index)
        log.info("SWITCH SENT: mediaIndex=%s to client=%s", target_index, getattr(client, "title", client))
    except Exception as e:
        log.warning("Switch failed: %s", e)
        if cur_is_4k: tautulli_terminate(args.session_id, KILL_MESSAGE)

    return 0

if __name__ == "__main__":
    sys.exit(main())
