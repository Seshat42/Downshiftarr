import pytest

from tests.harness.client_profiles import CLIENT_PROFILES, REQUIRED_PROFILE_NAMES, video_capable_profiles

pytestmark = [pytest.mark.simulated]


def test_client_registry_covers_every_required_plex_client_family():
    names = {profile.name for profile in CLIENT_PROFILES}

    assert REQUIRED_PROFILE_NAMES <= names


def test_client_registry_uses_unique_machine_identifiers():
    machine_ids = [profile.machine_identifier for profile in CLIENT_PROFILES]

    assert len(machine_ids) == len(set(machine_ids))


def test_non_video_accessory_profiles_are_not_video_capable():
    accessories = {profile.name: profile for profile in CLIENT_PROFILES if profile.kind == "accessory"}

    assert {"android-auto", "amazon-alexa", "sonos", "caavo"} <= accessories.keys()
    assert all(not profile.video_capable for profile in accessories.values())


def test_video_capable_profiles_exclude_accessory_profiles():
    names = {profile.name for profile in video_capable_profiles()}

    assert "plex-web-chrome" in names
    assert "lg-smart-tv" in names
    assert "amazon-alexa" not in names
