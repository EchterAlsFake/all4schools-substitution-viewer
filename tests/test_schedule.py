from __future__ import annotations

from datetime import datetime

from backend.app import seconds_until_sync_window
from backend.upstream import BERLIN


def berlin_time(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 8, 24, hour, minute, tzinfo=BERLIN)


def test_sync_is_allowed_from_six_until_before_twenty_two():
    assert seconds_until_sync_window(berlin_time(6)) == 0
    assert seconds_until_sync_window(berlin_time(21, 59)) == 0


def test_sync_waits_until_six_during_quiet_hours():
    assert seconds_until_sync_window(berlin_time(5, 30)) == 30 * 60
    assert seconds_until_sync_window(berlin_time(22)) == 8 * 60 * 60
    assert seconds_until_sync_window(berlin_time(23, 30)) == 6.5 * 60 * 60


def test_quiet_period_respects_daylight_saving_changes():
    before_spring_change = datetime(2026, 3, 28, 22, tzinfo=BERLIN)
    before_autumn_change = datetime(2026, 10, 24, 22, tzinfo=BERLIN)

    assert seconds_until_sync_window(before_spring_change) == 7 * 60 * 60
    assert seconds_until_sync_window(before_autumn_change) == 9 * 60 * 60
