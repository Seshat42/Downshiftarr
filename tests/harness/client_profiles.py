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


CLIENT_PROFILES: tuple[ClientProfile, ...] = (
    ClientProfile("plex-web", "Plex Web", "Chrome", "client-plex-web", _player("Plex Web Chrome", "Plex Web", "Chrome", "client-plex-web")),
    ClientProfile("roku", "Plex for Roku", "Roku", "client-roku", _player("Living Room Roku", "Plex for Roku", "Roku", "client-roku")),
    ClientProfile(
        "apple-tv", "Plex for Apple TV", "tvOS", "client-apple-tv", _player("Apple TV", "Plex for Apple TV", "tvOS", "client-apple-tv")
    ),
    ClientProfile(
        "android-tv",
        "Plex for Android TV",
        "Android",
        "client-android-tv",
        _player("Android TV", "Plex for Android TV", "Android", "client-android-tv"),
    ),
    ClientProfile(
        "chromecast",
        "Plex Chromecast",
        "Chromecast",
        "client-chromecast",
        _player("Chromecast", "Plex Chromecast", "Chromecast", "client-chromecast"),
    ),
    ClientProfile(
        "samsung-tizen", "Plex for Samsung", "Tizen", "client-samsung", _player("Samsung TV", "Plex for Samsung", "Tizen", "client-samsung")
    ),
    ClientProfile("lg-webos", "Plex for LG", "webOS", "client-lg", _player("LG TV", "Plex for LG", "webOS", "client-lg")),
    ClientProfile("xbox", "Plex for Xbox", "Xbox", "client-xbox", _player("Xbox", "Plex for Xbox", "Xbox", "client-xbox")),
    ClientProfile(
        "playstation",
        "Plex for PlayStation",
        "PlayStation",
        "client-playstation",
        _player("PlayStation", "Plex for PlayStation", "PlayStation", "client-playstation"),
    ),
    ClientProfile("ios", "Plex for iOS", "iOS", "client-ios", _player("iPhone", "Plex for iOS", "iOS", "client-ios")),
    ClientProfile(
        "android-mobile",
        "Plex for Android",
        "Android",
        "client-android-mobile",
        _player("Android Phone", "Plex for Android", "Android", "client-android-mobile"),
    ),
    ClientProfile("plex-htpc", "Plex HTPC", "Windows", "client-htpc", _player("Plex HTPC", "Plex HTPC", "Windows", "client-htpc")),
    ClientProfile("remote-relay", "Plex Relay", "Relay", "client-relay", _player("Remote Relay", "Plex Relay", "Relay", "client-relay")),
    ClientProfile(
        "unknown",
        "Unknown Plex Client",
        "Unknown",
        "client-unknown",
        _player("Unknown Client", "Unknown Plex Client", "Unknown", "client-unknown"),
    ),
)
