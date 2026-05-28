from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace


@dataclass(frozen=True)
class ClientProfile:
    name: str
    product: str
    platform: str
    machine_identifier: str
    player: SimpleNamespace
    kind: str = "video"
    video_capable: bool = True


def _player(name: str, product: str, platform: str, machine_identifier: str) -> SimpleNamespace:
    return SimpleNamespace(
        title=name,
        product=product,
        platform=platform,
        machineIdentifier=machine_identifier,
        clientIdentifier=machine_identifier,
        address="127.0.0.1",
        port="32433",
    )


def _profile(
    name: str, product: str, platform: str, title: str | None = None, kind: str = "video", video_capable: bool = True
) -> ClientProfile:
    machine_identifier = f"client-{name}"
    return ClientProfile(
        name=name,
        product=product,
        platform=platform,
        machine_identifier=machine_identifier,
        player=_player(title or product, product, platform, machine_identifier),
        kind=kind,
        video_capable=video_capable,
    )


REQUIRED_PROFILE_NAMES = {
    "plex-web-chrome",
    "plex-web-edge",
    "plex-web-firefox",
    "plex-web-safari",
    "plex-windows",
    "plex-macos",
    "plex-linux",
    "plex-htpc",
    "plex-media-player",
    "android-mobile",
    "ios",
    "ipados",
    "android-tv",
    "google-tv",
    "nvidia-shield",
    "amazon-fire-tv",
    "apple-tv",
    "chromecast",
    "roku",
    "roku-tv",
    "lg-smart-tv",
    "samsung-smart-tv",
    "hisense-smart-tv",
    "vidaa-smart-tv",
    "vizio-smart-tv",
    "xbox",
    "playstation",
    "android-auto",
    "amazon-alexa",
    "sonos",
    "caavo",
    "remote-relay",
    "unknown",
}


CLIENT_PROFILES: tuple[ClientProfile, ...] = (
    _profile("plex-web-chrome", "Plex Web", "Chrome", "Plex Web Chrome"),
    _profile("plex-web-edge", "Plex Web", "Edge", "Plex Web Edge"),
    _profile("plex-web-firefox", "Plex Web", "Firefox", "Plex Web Firefox"),
    _profile("plex-web-safari", "Plex Web", "Safari", "Plex Web Safari"),
    _profile("plex-windows", "Plex for Windows", "Windows"),
    _profile("plex-macos", "Plex for macOS", "macOS"),
    _profile("plex-linux", "Plex for Linux", "Linux"),
    _profile("plex-htpc", "Plex HTPC", "Windows"),
    _profile("plex-media-player", "Plex Media Player", "Windows"),
    _profile("android-mobile", "Plex for Android", "Android", "Android Phone"),
    _profile("ios", "Plex for iOS", "iOS", "iPhone"),
    _profile("ipados", "Plex for iOS", "iPadOS", "iPad"),
    _profile("android-tv", "Plex for Android TV", "Android"),
    _profile("google-tv", "Plex for Android TV", "Google TV"),
    _profile("nvidia-shield", "Plex for Android TV", "NVIDIA SHIELD"),
    _profile("amazon-fire-tv", "Plex for Android TV", "Fire TV"),
    _profile("apple-tv", "Plex for Apple TV", "tvOS", "Apple TV"),
    _profile("chromecast", "Plex Chromecast", "Chromecast"),
    _profile("roku", "Plex for Roku", "Roku", "Living Room Roku"),
    _profile("roku-tv", "Plex for Roku", "Roku TV"),
    _profile("lg-smart-tv", "Plex for LG", "webOS", "LG TV"),
    _profile("samsung-smart-tv", "Plex for Samsung", "Tizen", "Samsung TV"),
    _profile("hisense-smart-tv", "Plex for Smart TVs", "VIDAA", "Hisense TV"),
    _profile("vidaa-smart-tv", "Plex for Smart TVs", "VIDAA", "VIDAA TV"),
    _profile("vizio-smart-tv", "Plex for Smart TVs", "Vizio", "Vizio TV"),
    _profile("xbox", "Plex for Xbox", "Xbox"),
    _profile("playstation", "Plex for PlayStation", "PlayStation"),
    _profile("android-auto", "Plex for Android Auto", "Android Auto", kind="accessory", video_capable=False),
    _profile("amazon-alexa", "Plex for Alexa", "Alexa", kind="accessory", video_capable=False),
    _profile("sonos", "Plex for Sonos", "Sonos", kind="accessory", video_capable=False),
    _profile("caavo", "Plex for Caavo", "Caavo", kind="accessory", video_capable=False),
    _profile("remote-relay", "Plex Relay", "Relay", "Remote Relay"),
    _profile("unknown", "Unknown Plex Client", "Unknown", "Unknown Client"),
)


def video_capable_profiles() -> tuple[ClientProfile, ...]:
    return tuple(profile for profile in CLIENT_PROFILES if profile.video_capable)
