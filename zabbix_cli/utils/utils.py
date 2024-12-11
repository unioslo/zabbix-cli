"""Uncategorized utility functions.

Some stemming from Zabbix-cli v2, while others relate to converting
values and flags from the Zabbix API."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Final
from typing import NamedTuple
from typing import Optional
from typing import Union

from zabbix_cli.exceptions import ZabbixCLIError


# NOTE: consider setting with_code to False by default...
# The only downside is possibly breaking backwards compatibility
def _format_code(
    code: Union[str, int, None], status_map: dict[Any, str], with_code: bool = True
) -> str:
    status = status_map.get(code, "Unknown")
    if with_code and code is not None:
        status += f" ({code})"
    return status


# LEGACY: Kept for backwards compatibility in JSON output
# zabbix_cli.pyzabbix.enums.MaintenanceStatus has different string values
# than the ones used in Zabbix-cli v2. This function is used to map the
# the API values to the old string values when serializing to JSON.
# Should be removed when we drop support for legacy JSON output.
def get_maintenance_status(code: Optional[str], with_code: bool = False) -> str:
    """Get maintenance status from code."""
    maintenance_status = {"0": "No maintenance", "1": "In progress"}
    return _format_code(code, maintenance_status, with_code=with_code)


# LEGACY: Kept for backwards compatibility in JSON output
def get_monitoring_status(code: Optional[str], with_code: bool = False) -> str:
    """Get monitoring status from code."""
    monitoring_status = {"0": "Monitored", "1": "Not monitored"}
    return _format_code(code, monitoring_status, with_code=with_code)


def get_maintenance_active_days(schedule: int | None) -> list[str]:
    """Get maintenance day of week from code."""
    if schedule is None:
        return []
    days = {
        0b0000001: "Monday",
        0b0000010: "Tuesday",
        0b0000100: "Wednesday",
        0b0001000: "Thursday",
        0b0010000: "Friday",
        0b0100000: "Saturday",
        0b1000000: "Sunday",
    }
    # Bitwise AND schedule with each DoW's bit mask
    # If the result is non-zero, the DoW is active
    active_days: list[str] = []
    for n, dow in days.items():
        if schedule & n:
            active_days.append(dow)
    return active_days


def get_maintenance_active_months(schedule: int | None) -> list[str]:
    if schedule is None:
        return []
    months = {
        0b000000000001: "January",
        0b000000000010: "February",
        0b000000000100: "March",
        0b000000001000: "April",
        0b000000010000: "May",
        0b000000100000: "June",
        0b000001000000: "July",
        0b000010000000: "August",
        0b000100000000: "September",
        0b001000000000: "October",
        0b010000000000: "November",
        0b100000000000: "December",
    }
    # Bitwise AND schedule with each month's bit mask
    # If the result is non-zero, the month is active
    active_months: list[str] = []
    for n, month in months.items():
        if schedule & n:
            active_months.append(month)
    return active_months


# NOTE: we could turn these into str Enums or Literals,
# so that it's easier to type check the values
ACKNOWLEDGE_ACTION_BITMASK: Final[dict[str, int]] = {
    "close": 0b000000001,
    "acknowledge": 0b000000010,
    "message": 0b000000100,
    "change_severity": 0b000001000,
    "unacknowledge": 0b000010000,
    "suppress": 0b000100000,
    "unsuppress": 0b001000000,
    "change_to_cause": 0b010000000,
    "change_to_symptom": 0b100000000,
}


def get_acknowledge_action_value(
    close: bool = False,
    acknowledge: bool = False,
    message: bool = False,
    change_severity: bool = False,
    unacknowledge: bool = False,
    suppress: bool = False,
    unsuppress: bool = False,
    change_to_cause: bool = False,
    change_to_symptom: bool = False,
) -> int:
    value = 0
    if close:
        value += ACKNOWLEDGE_ACTION_BITMASK["close"]
    if acknowledge:
        value += ACKNOWLEDGE_ACTION_BITMASK["acknowledge"]
    if message:
        value += ACKNOWLEDGE_ACTION_BITMASK["message"]
    if change_severity:
        value += ACKNOWLEDGE_ACTION_BITMASK["change_severity"]
    if unacknowledge:
        value += ACKNOWLEDGE_ACTION_BITMASK["unacknowledge"]
    if suppress:
        value += ACKNOWLEDGE_ACTION_BITMASK["suppress"]
    if unsuppress:
        value += ACKNOWLEDGE_ACTION_BITMASK["unsuppress"]
    if change_to_cause:
        value += ACKNOWLEDGE_ACTION_BITMASK["change_to_cause"]
    if change_to_symptom:
        value += ACKNOWLEDGE_ACTION_BITMASK["change_to_symptom"]
    return value


def get_acknowledge_actions(code: int) -> list[str]:
    """Get acknowledge actions from code.

    See: https://www.zabbix.com/documentation/current/en/manual/api/reference/event/acknowledge (action parameter)
    """
    # Create reverse lookup for action bitmask
    acknowledge_actions = {v: k for k, v in ACKNOWLEDGE_ACTION_BITMASK.items()}
    active_action: list[str] = []
    for n, action in acknowledge_actions.items():
        if code & n:
            active_action.append(action)
    return active_action


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile regex pattern."""
    try:
        p = re.compile(pattern)
    except re.error as e:
        raise ZabbixCLIError(f"Invalid regex pattern: {pattern}") from e
    return p


class TimeUnit(NamedTuple):
    """Time value."""

    unit: str
    tokens: Iterable[str]
    value: int
    """The value of the time unit in seconds."""


# NOTE: PLURAL TOKEN MUST BE LISTED FIRST
TIME_VALUE_DAY = TimeUnit("D", ["days", "day"], value=60 * 60 * 24)
TIME_VALUE_HOUR = TimeUnit("H", ["hours", "hour"], value=60 * 60)
TIME_VALUE_MINUTE = TimeUnit("M", ["minutes", "minute"], value=60)
TIME_VALUE_SECOND = TimeUnit("S", ["seconds", "second"], value=1)
TIME_VALUES = [
    TIME_VALUE_DAY,
    TIME_VALUE_HOUR,
    TIME_VALUE_MINUTE,
    TIME_VALUE_SECOND,
]


def convert_time_to_interval(time: str) -> tuple[datetime, datetime]:
    """Convert time to an interval of datetimes.

    `time` is a string that specifies a duration of time in
    one of the following formats:

    - `1d1h30m30s`
    - `1 day 1 hour 30 minutes 30 seconds`

    Any combination of the above is also valid, e.g.:

    - `1d1h30m`
    - `2 days 30 minutes`
    - `1 hour`

    The `time` string can also be a timestamp interval in the following format:

    - `2016-11-21T22:00 to 2016-11-21T23:00`

    """
    # Use a very simple heuristic to to determine if we have an interval:
    if " to " in time:
        return convert_timestamp_interval(time)
    # Fall back on parsing duration beginning from now:
    duration = convert_duration(time)
    start = datetime.now()
    end = start + duration
    return start, end


def convert_timestamp(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        pass

    formats = [
        "%Y-%m-%dT%H:%M",  # Legacy format (no seconds)
        "%Y-%m-%dT%H:%M:%S",  # with T separator
        "%Y-%m-%d %H:%M:%S",  # without T separator
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            pass
    raise ZabbixCLIError(f"Invalid timestamp: {ts}")


def convert_timestamp_interval(time: str) -> tuple[datetime, datetime]:
    """Convert timestamp interval to seconds.

    `time` is a string that specifies a timestamp interval in
    the following format:

    - `2016-11-21T22:00 to 2016-11-21T23:00`

    """
    start, sep, end = time.partition(" to ")
    if not sep:
        raise ZabbixCLIError(f"Invalid timestamp interval: {time}")
    return convert_timestamp(start), convert_timestamp(end)


def convert_duration(time: str) -> timedelta:
    """Convert duration to timedelta.

    `time` is a string that specifies a duration of time in
    one of the following formats:

    - `1d1h30m30s`
    - `1 day 1 hour 30 minutes 30 seconds`

    Any combination of the above is also valid, e.g.:

    - `1d1h30m`
    - `2 days 30 minutes`
    - `1 hour`
    """

    def try_convert_int(s: str) -> int:
        if not s:
            return 0
        try:
            return int(s)
        except ValueError:
            raise ZabbixCLIError(f"Invalid time value: {s}")

    time = time.replace(" ", "")
    for time_value in TIME_VALUES:
        # First replace full words (days, hours, minutes, seconds)
        for token in time_value.tokens:
            time = time.replace(token, time_value.unit)
        # Then replace abbreviations (d, h, m, s) with uppercase
    time = time.upper()

    # NOTE: this is very inelegant. The swapping of variables when
    # partitioning is particularly ugly.
    days, sep, rest = time.partition(TIME_VALUE_DAY.unit)
    if not sep:
        days, rest = rest, days
    hours, sep, rest = rest.partition(TIME_VALUE_HOUR.unit)
    if not sep:
        hours, rest = rest, hours
    minutes, sep, rest = rest.partition(TIME_VALUE_MINUTE.unit)
    if not sep:
        minutes, rest = rest, minutes
    seconds, sep, rest = rest.partition(TIME_VALUE_SECOND.unit)
    if rest:
        raise ZabbixCLIError(f"Invalid time value: {time}")

    td = timedelta(
        days=try_convert_int(days),
        hours=try_convert_int(hours),
        minutes=try_convert_int(minutes),
        seconds=try_convert_int(seconds),
    )
    return td


def convert_seconds_to_duration(seconds: int) -> str:
    """Convert seconds to duration string."""
    days, seconds = divmod(seconds, 60 * 60 * 24)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)

    duration = ""
    if days:
        duration += f"{days}d"
    if hours:
        duration += f"{hours}h"
    if minutes:
        duration += f"{minutes}m"
    if seconds:
        duration += f"{seconds}s"

    return duration
