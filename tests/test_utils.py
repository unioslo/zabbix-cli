from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Tuple

import pytest
from freezegun import freeze_time
from zabbix_cli.utils import convert_duration
from zabbix_cli.utils.utils import convert_time_to_interval
from zabbix_cli.utils.utils import convert_timestamp
from zabbix_cli.utils.utils import convert_timestamp_interval


@pytest.mark.parametrize(
    "input,expect",
    [
        (
            "1 hour",
            timedelta(hours=1),
        ),
        (
            "1 hour 30 minutes",
            timedelta(hours=1, minutes=30),
        ),
        (
            "1 hour 30 minutes 30 seconds",
            timedelta(hours=1, minutes=30, seconds=30),
        ),
        (
            "1 day 1 hour 30 minutes 30 seconds",
            timedelta(days=1, hours=1, minutes=30, seconds=30),
        ),
        (
            "2 hours 30 seconds",
            timedelta(hours=2, seconds=30),
        ),
        (
            "2h30s",
            timedelta(hours=2, seconds=30),
        ),
        (
            "2 hours 30 minutes 30 seconds",
            timedelta(hours=2, minutes=30, seconds=30),
        ),
        (
            "2 hour 30 minute 30 second",
            timedelta(hours=2, minutes=30, seconds=30),
        ),
        (
            "2h30m30s",
            timedelta(hours=2, minutes=30, seconds=30),
        ),
        (
            "9030s",
            timedelta(seconds=9030),
        ),
        (
            "9030",
            timedelta(seconds=9030),
        ),
        (
            "0",
            timedelta(seconds=0),
        ),
        (
            "0d0h0m0s",
            timedelta(days=0, hours=0, minutes=0, seconds=0),
        ),
    ],
)
def test_convert_duration(input: str, expect: timedelta) -> None:
    assert convert_duration(input) == expect
    assert convert_duration(input).total_seconds() == expect.total_seconds()


@pytest.mark.parametrize(
    "input, expect",
    [
        pytest.param(
            "2016-11-21T22:00 to 2016-11-21T23:00",
            (datetime(2016, 11, 21, 22, 0, 0), datetime(2016, 11, 21, 23, 0, 0)),
            id="Legacy format",  #  (ISO w/o timezone and seconds)
        ),
        pytest.param(
            "2016-11-21T22:00:00 to 2016-11-21T23:00:00",
            (datetime(2016, 11, 21, 22, 0, 0), datetime(2016, 11, 21, 23, 0, 0)),
            id="ISO w/o timezone",
        ),
        pytest.param(
            "2016-11-21 22:00:00 to 2016-11-21 23:00:00",
            (datetime(2016, 11, 21, 22, 0, 0), datetime(2016, 11, 21, 23, 0, 0)),
            id="ISO w/o timezone (space-separated)",
        ),
    ],
)
def test_convert_timestamp_interval(
    input: str, expect: Tuple[datetime, datetime]
) -> None:
    assert convert_timestamp_interval(input) == expect
    # TODO: test with mix of formats. e.g. "2016-11-21T22:00 to 2016-11-21 23:00:00"


@pytest.mark.parametrize(
    "input,expect",
    [
        pytest.param(
            "2016-11-21T22:00",
            datetime(2016, 11, 21, 22, 0, 0),
            id="Legacy",
        ),
        pytest.param(
            "2016-11-21T22:00:00",
            datetime(2016, 11, 21, 22, 0, 0),
            id="ISO w/o timezone",
        ),
        pytest.param(
            "2016-11-21 22:00:00",
            datetime(2016, 11, 21, 22, 0, 0),
            id="ISO w/o timezone (space-separated)",
        ),
    ],
)
def test_convert_timestamp(input: str, expect: datetime) -> None:
    assert convert_timestamp(input) == expect


@pytest.mark.parametrize(
    "input,expect_duration",
    [
        pytest.param(
            "2016-11-21T22:00 to 2016-11-21T23:00",
            timedelta(hours=1),
            id="Range: Legacy",
        ),
        pytest.param(
            "2016-11-21T22:00:00 to 2016-11-21T23:00:00",
            timedelta(hours=1),
            id="Range: ISO w/o timezone",
        ),
        pytest.param(
            "2016-11-21 22:00:00 to 2016-11-21 23:00:00",
            timedelta(hours=1),
            id="Range: ISO w/o timezone (space-separated)",
        ),
        pytest.param(
            "1 hour",
            timedelta(hours=1),
            id="Duration: 1h (long form)",
        ),
        pytest.param(
            "1 day 1 hour 30 minutes 30 seconds",
            timedelta(days=1, hours=1, minutes=30, seconds=30),
            id="Duration: 1d1h30m30s (long form)",
        ),
        pytest.param(
            "1h",
            timedelta(hours=1),
            id="Duration: 1h (short form)",
        ),
        pytest.param(
            "1d1h30m30s",
            timedelta(days=1, hours=1, minutes=30, seconds=30),
            id="Duration: 1d1h30m30s (short form)",
        ),
    ],
)
@freeze_time("2016-11-21 22:00:00")
def test_convert_time_to_interval(input: str, expect_duration: timedelta) -> None:
    start, end = convert_time_to_interval(input)
    assert start == datetime(2016, 11, 21, 22, 0, 0)
    assert end == start + expect_duration
