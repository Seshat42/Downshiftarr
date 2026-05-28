# Simulated Client Matrix

Last reviewed: 2026-05-28

The simulated rig models client diversity without requiring every physical device to be online. Profiles live in `tests/harness/client_profiles.py`; fake playback controls live in `tests/harness/fakes.py`.

## Profiles

| Profile | Product | Platform | Purpose |
|---|---|---|---|
| Plex Web browsers | Plex Web | Chrome, Edge, Firefox, Safari | Browser family coverage and easiest real Plex Web comparison target. |
| Desktop apps | Plex for Windows/macOS/Linux | Windows, macOS, Linux | Native desktop app coverage separate from browser and HTPC. |
| Theater apps | Plex HTPC, Plex Media Player | Windows | Desktop/theater playback profile. |
| Mobile/tablet | Plex for Android, Plex for iOS | Android, iOS, iPadOS | Phone and tablet client coverage. |
| Android TV family | Plex for Android TV | Android TV, Google TV, NVIDIA SHIELD, Fire TV | Set-top and smart TV family variants. |
| Apple TV | Plex for Apple TV | tvOS | Modern TV client with strong direct-play support. |
| Chromecast | Plex Chromecast | Chromecast | Receiver-style playback and control path. |
| Roku family | Plex for Roku | Roku, Roku TV | Common TV devices with remote-control variation risk. |
| Smart TVs | Plex for LG/Samsung/Smart TVs | webOS, Tizen, Hisense, VIDAA, Vizio | TV platforms with frequent codec capability differences. |
| Consoles | Plex for Xbox/PlayStation | Xbox, PlayStation | Game console playback families. |
| Accessories | Plex for Android Auto/Alexa/Sonos/Caavo | Android Auto, Alexa, Sonos, Caavo | Non-video/control-only surfaces that must not trigger unsafe video enforcement. |
| Remote Relay | Plex Relay | Relay | NAT/relay-like remote-control risk profile. |
| Unknown | Unknown Plex Client | Unknown | Defensive fallback for incomplete or new Plex metadata. |

## Scenarios

Every video-capable profile should remain covered for:

- Session matching by `session_key`, `session_id`, rating key, username, and machine identifier where available.
- Client discovery through enumerated Plex clients and player-title fallback.
- Direct play and direct stream no-op behavior.
- Protected video transcode enforcement.
- Missing client fail-closed behavior.
- `playMedia` failure and switch-failure termination.
- `seekTo` failure after successful `playMedia`.
- Stale session lookup retry.
- No compliant fallback media.
- Tautulli termination first, Plex termination fallback second.
- Plex token transport through `X-Plex-Token` headers.

Accessory profiles are kept in the registry but must no-op unless Plex/Tautulli presents an actual video transcode session.

Real devices can still reveal Plex-client quirks that a fake cannot model. When that happens, add the smallest deterministic simulated case first, then use Loki or a physical client to prove the real behavior.
