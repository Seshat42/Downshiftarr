# Simulated Client Matrix

Last reviewed: 2026-05-28

The simulated rig models client diversity without requiring every physical device to be online. Profiles live in `tests/harness/client_profiles.py`; fake playback controls live in `tests/harness/fakes.py`.

## Profiles

| Profile | Product | Platform | Purpose |
|---|---|---|---|
| Plex Web | Plex Web | Chrome | Baseline browser client and easiest manual comparison target. |
| Roku | Plex for Roku | Roku | Common smart TV device with remote-control variation risk. |
| Apple TV | Plex for Apple TV | tvOS | Modern TV client with strong direct-play support. |
| Android TV / Fire TV | Plex for Android TV | Android | Common set-top and smart TV family. |
| Chromecast | Plex Chromecast | Chromecast | Receiver-style playback and control path. |
| Samsung Tizen | Plex for Samsung | Tizen | Smart TV platform with frequent codec capability differences. |
| LG webOS | Plex for LG | webOS | Smart TV platform with frequent transcode decision differences. |
| Xbox | Plex for Xbox | Xbox | Console profile. |
| PlayStation | Plex for PlayStation | PlayStation | Console profile. |
| iOS | Plex for iOS | iOS | Mobile profile. |
| Android Mobile | Plex for Android | Android | Mobile profile. |
| Plex HTPC | Plex HTPC | Windows | Desktop/theater profile. |
| Remote Relay | Plex Relay | Relay | NAT/relay-like remote-control risk profile. |
| Unknown | Unknown Plex Client | Unknown | Defensive fallback for incomplete Plex metadata. |

## Scenarios

Every profile should remain covered for:

- Session matching by `session_key`, `session_id`, rating key, username, and machine identifier where available.
- Client discovery through enumerated Plex clients.
- Direct play and direct stream no-op behavior.
- Protected video transcode enforcement.
- Missing client fail-closed behavior.
- `playMedia` failure and switch-failure termination.
- `seekTo` failure after successful `playMedia`.
- No compliant fallback media.
- Tautulli termination first, Plex termination fallback second.
- Plex token transport through `X-Plex-Token` headers.

Real devices can still reveal Plex-client quirks that a fake cannot model. When that happens, add the smallest deterministic simulated case first, then use Loki or a physical client to prove the real behavior.
