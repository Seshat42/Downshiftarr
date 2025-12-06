## Full rebuild was done to this repo

For the moment I have removed the "allow 4k transcoding if no lower versions available", it will return.

Information to explain how the "Plex Transcoder" file is to ne used will ne added soon.

# Downshiftarr

**Downshiftarr** is a Tautulli script that strictly enforces Plex transcoding policies. It protects your server resources by preventing 4K transcoding and automatically "downshifting" clients to a lower quality version (e.g., 1080p, 720p) if one exists.

Unlike simple "Kill Stream" scripts, Downshiftarr attempts to **fix the problem first** by seamlessly switching the user to a version that their client can handle.

>This all happens seamlessly, the user does not do anything different, just press play like they always have, there is no extra lag etc.

---

## Table of Contents

1. [Logic & Policy](#logic--policy)
2. [Configuration](#configuration)
3. [Installation & Setup](#installation--setup)
4. [Tautulli Setup](#tautulli-setup)
5. [Troubleshooting](#troubleshooting)

---

## Logic & Policy

When a user triggers a transcode, Downshiftarr executes the following logic:

1.  **Exemption Check:** Checks if the user is in the `EXEMPT_USERS` list. If so, allows everything.
2.  **Direct Play Check:** If the decision is `Direct Play` or `Direct Stream`, the script exits immediately (playback allowed).
3.  **4K Guard (The "Hard" Block):**
    * If the content is **4K (>= 2160p)** and is transcoding:
    * The script searches for a non-4K version (1080p, 720p, SD).
    * **If found:** It commands the client to switch to that version immediately (preserving playback offset).
    * **If NOT found:** It kills the stream.
4.  **Standard Waterfall (1080p/720p Enforcement):**
    * If the content is **1080p** or **720p** and `ENFORCE_DIRECT_1080` is True:
    * It steps down one "rung" (e.g., looks for 720p if 1080p is transcoding).
    * It continues checking lower rungs (576p, 480p) until a match is found.
    * If a lower version is found, it switches the user.
    * If *no* lower version is found, it allows the stream to continue.

---

## Configuration

Open `downshiftarr.py` and edit the **USER CONFIG** section at the top.

### Connection Settings

* PLEX_URL = "http://localhost:32400"
* PLEX_TOKEN = "YOUR_TOKEN"
* TAUTULLI_URL = "http://localhost:8181"
* TAUTULLI_APIKEY = "YOUR_API_KEY"

### Policy Settings

| Variable | Default | Description |
|---|---|---|
| EXEMPT_USERS | {"Debug User"} | A set of exact usernames (case-sensitive) that are allowed to transcode anything. |
| ALLOW_4K_TRANSCODE_IF_NO_FALLBACK | False | *True:* If a user plays 4K, and you don't have a lower quality version, let them transcode the 4K file. *False:* If you don't have a lower quality version, Kill the stream. |
| ENFORCE_DIRECT_2160 | True | 4K is always enforced. This flag is mostly informational but keeps the logic consistent. |
| ENFORCE_DIRECT_1080 | True | True: If a 1080p file transcodes, try to switch them to 720p/SD. |
| ENFORCE_DIRECT_720 | False | True: If a 720p file transcodes, try to switch them to SD. |
| BLOCK_HDR_TRANSCODING | True | If True, treats HDR/DoVi transcoding as a violation even if the resolution is okay. It will prefer an SDR version if available. |
| KILL_MESSAGE | String | The message displayed to the user if the stream is terminated. |

## Installation & Setup

1. **Requirements**
   * Python 3
   * Plex Media Server
   * Tautulli
   * Python libraries `plexapi` and `requests`
2. **Download**
   * Clone this repo or download `downshiftarr.py` and `requirements.txt`
3. **Configure**
   * Open `downshiftarr.py` and set your connection values: `PLEX_URL`, `PLEX_TOKEN`, `TAUTULLI_URL`, and `TAUTULLI_APIKEY`.
   * Adjust policy flags as needed (see [Configuration](#configuration)).
4. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

5. **Verify with a dry run (you dont need to do this)**
   * From the command line, run with placeholder values to confirm wiring:

     ```bash
     python3 downshiftarr.py RATING_KEY MACHINE_ID USERNAME SESSION_ID USER_ID "4k" "transcode" "HDR" --dry-run
     ```
   * After the run (or any Tautulli-triggered execution), check the **Tautulli notification logs** to confirm the script executed and review decision details.

### Tautulli Setup

You must configure Tautulli to pass the specific arguments the script expects.
 * In Tautulli, go to Settings -> Notification Agents.
 * Add a new Script notification.
 * Configuration Tab:
   * Script Folder: Select the folder containing downshiftarr.py.
   * Script File: Select downshiftarr.py.
 * Triggers Tab:
   * [x] Playback Start
   * [x] Playback Resume
   * [x] Transcode Decision Change
 * Conditions Tab:
   * Condition 1: `Video Decision | is | transcode`
 * Arguments Tab:
   * Playback Start: Paste the arguments below exactly.
   * Playback Resume: Paste the arguments below exactly.
   * Transcode Decision Change: Paste the arguments below exactly.
  * Arguments String:

`{rating_key} {machine_id} {username} {session_id} {user_id} {video_resolution} {video_decision} {video_dynamic_range}`

>Note: The order of these arguments is critical. Do not change the order.

## Troubleshooting

>If you have located an issue or bug, please submit it as an Issue here on GitHub and I will address it.

* Q: I have a 1080p file, but it's transcoding and not killing the stream?

A: This is intended behavior. If ENFORCE_DIRECT_1080 is True, it tries to find a lower version (720p, etc). If you don't have a lower version, the script allows the 1080p transcode to continue so the user can watch their movie. We only "Kill" on 4K because 4K transcoding destroys server performance, whereas 1080p is usually manageable.

* Q: How do I test this without kicking my users?

A: You can add all of your other users to the exempt user list and then test it yourself or you run the script manually from the command line with the --dry-run flag to see what it would do:
python3 downshiftarr.py [rating_key] [machine_id] [username] [session_id] [user_id] "4k" "transcode" "HDR" --dry-run

* Q: How do I check the logs?

A: The script outputs detailed logs to the Tautulli notification logs. Check there to see "Waterfall candidates" and decision logic.
