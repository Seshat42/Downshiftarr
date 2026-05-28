from datetime import date

from scripts.testing import daily_release


def test_daily_tag_uses_new_york_calendar_date():
    assert daily_release.build_daily_tag(date(2026, 5, 28)) == "daily-2026-05-28"


def test_daily_release_skips_when_today_tag_exists():
    decision = daily_release.decide_release(
        tag="daily-2026-05-28",
        tag_exists=True,
        release_exists=False,
        previous_release_tag="daily-2026-05-27",
        commits_since_previous=3,
    )

    assert decision.should_release is False
    assert decision.reason == "daily tag or release already exists"


def test_daily_release_skips_when_no_commits_since_previous_release():
    decision = daily_release.decide_release(
        tag="daily-2026-05-28",
        tag_exists=False,
        release_exists=False,
        previous_release_tag="daily-2026-05-27",
        commits_since_previous=0,
    )

    assert decision.should_release is False
    assert decision.reason == "no commits since previous release"


def test_daily_release_allows_first_release_or_changed_main():
    first = daily_release.decide_release(
        tag="daily-2026-05-28",
        tag_exists=False,
        release_exists=False,
        previous_release_tag=None,
        commits_since_previous=0,
    )
    changed = daily_release.decide_release(
        tag="daily-2026-05-28",
        tag_exists=False,
        release_exists=False,
        previous_release_tag="daily-2026-05-27",
        commits_since_previous=1,
    )

    assert first.should_release is True
    assert first.reason == "first daily release"
    assert changed.should_release is True
    assert changed.reason == "main changed since previous release"


def test_latest_prior_release_ignores_current_tag_and_sorts_by_created_at():
    releases = [
        daily_release.ReleaseInfo("daily-2026-05-28", "2026-05-28T08:30:00Z"),
        daily_release.ReleaseInfo("v0.7.3b", "2025-12-13T08:57:37Z"),
        daily_release.ReleaseInfo("daily-2026-05-27", "2026-05-27T08:30:00Z"),
    ]

    assert daily_release.latest_prior_release(releases, "daily-2026-05-28").tag_name == "daily-2026-05-27"
