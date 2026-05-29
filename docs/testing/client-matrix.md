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

## Emulator Lab

The emulator lab is a tiered proof, not a claim that every vendor ships a fully automatable Plex app surface.

- Android mobile, Android tablet, Android TV, and Google TV use the official Android SDK command-line tools and Android Emulator when present. The local detector is `python scripts/testing/emulator_lab.py`.
- Samsung Tizen TV and LG webOS TV coverage is tracked separately because the official vendor emulators require their own IDE/tooling and do not provide the same proof as a retail Plex app on hardware.
- iOS, iPadOS, and tvOS simulators require macOS/Xcode, so this Windows/WSL host records them as unsupported by host and relies on physical Apple proof plus synthetic/HLS canaries.
- Roku and console Plex proof requires physical devices for retail-app behavior; this pass uses deterministic synthetic coverage and records that limitation.

Current local lab policy:

- Real Android AVD targets should cover `android_mobile`, `android_tablet`, `android_tv`, and `google_tv` when the portable lab under ignored `emulator-lab/` is present.
- Synthetic video profiles remain mandatory for Plex Web, desktop/HTPC, Roku, Fire TV, Android TV, Google TV, Nvidia Shield, Apple TV, iOS/iPadOS, Android, Chromecast, Samsung/LG smart TVs, consoles, relay-like, and unknown clients.
- Any client defect discovered on hardware should become a small deterministic fixture before it is treated as fixed.
