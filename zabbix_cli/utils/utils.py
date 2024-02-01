# TODO: move into pyzabbix module
"""Utility functions."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Final
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple
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


def get_ack_status(code: Optional[int]) -> str:
    """Get ack status from code."""
    ack_status = {0: "No", 1: "Yes"}
    return _format_code(code, ack_status, with_code=False)


def get_event_status(code: Optional[int]) -> str:
    """Get event status from code."""
    event_status = {0: "OK", 1: "Problem"}
    return _format_code(code, event_status, with_code=False)


def get_trigger_severity(code: int | None) -> str:
    """Get trigger severity from code."""
    trigger_severity = {
        0: "Not classified",
        1: "Information",
        2: "Warning",
        3: "Average",
        4: "High",
        5: "Disaster",
    }
    return _format_code(code, trigger_severity, with_code=False)


def get_trigger_status(code):
    """Get trigger status from code."""
    trigger_status = {0: "Enable", 1: "Disable"}

    if code in trigger_status:
        return trigger_status[code] + " (" + str(code) + ")"

    return f"Unknown ({str(code)})"


def get_maintenance_status(code: Optional[str]) -> str:
    """Get maintenance status from code."""
    # TODO: can we change the type of the code to int?
    maintenance_status = {"0": "No maintenance", "1": "In progress"}
    return _format_code(code, maintenance_status)


def get_monitoring_status(code: Optional[str]) -> str:
    """Get monitoring status from code."""
    monitoring_status = {"0": "Monitored", "1": "Not monitored"}
    return _format_code(code, monitoring_status)


def get_zabbix_agent_status(code: Optional[str]) -> str:
    """Get zabbix agent status from code."""
    zabbix_agent_status = {"1": "Available", "2": "Unavailable"}
    return _format_code(code, zabbix_agent_status)


def get_gui_access(code: int) -> str:
    """Get GUI access from code."""
    gui_access = {0: "System default", 1: "Internal", 2: "LDAP", 3: "Disable"}
    return _format_code(code, gui_access)


def get_usergroup_status(code: int) -> str:
    """Get usergroup status from code."""
    usergroup_status = {0: "Enable", 1: "Disable"}
    return _format_code(code, usergroup_status)


def get_hostgroup_flag(code: int) -> str:
    """Get hostgroup flag from code."""
    hostgroup_flag = {0: "Plain", 4: "Discover"}

    if code in hostgroup_flag:
        return hostgroup_flag[code] + " (" + str(code) + ")"

    return f"Unknown ({str(code)})"


def get_hostgroup_type(code: int) -> str:
    """Get hostgroup type from code."""
    hostgroup_type = {0: "Not internal", 1: "Internal"}

    if code in hostgroup_type:
        return hostgroup_type[code] + " (" + str(code) + ")"

    return f"Unknown ({str(code)})"


def get_user_type(code: int | None) -> str:
    """Get user type from code."""
    user_type = {1: "User", 2: "Admin", 3: "Super admin", 4: "Guest"}
    return _format_code(code, user_type)


def get_maintenance_type(code: int | None) -> str:
    """Get maintenance type from code."""
    maintenance_type = {0: "With DC", 1: "Without DC"}
    return _format_code(code, maintenance_type, with_code=False)


def get_maintenance_period_type(code: int | None) -> str:
    """Get maintenance period type from code."""
    maintenance_period_type = {0: "One time", 2: "Daily", 3: "Weekly", 4: "Monthly"}
    return _format_code(code, maintenance_period_type, with_code=False)


def get_maintenance_every_type(code: int | None) -> str:
    """Get maintenance every week type from code."""
    maintenance_every_type = {
        1: "First week",
        2: "Second week",
        3: "Third week",
        4: "Fourth week",
        5: "Last week",
    }
    return _format_code(code, maintenance_every_type, with_code=False)


def get_maintenance_active_days(schedule: int | None) -> List[str]:
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
    active_days = []
    for n, dow in days.items():
        if schedule & n:
            active_days.append(dow)
    return active_days


def get_maintenance_active_months(schedule: int | None) -> List[str]:
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
    active_months = []
    for n, month in months.items():
        if schedule & n:
            active_months.append(month)
    return active_months


# NOTE: we could turn these into str Enums or Literals,
# so that it's easier to type check the values
ACKNOWLEDGE_ACTION_BITMASK: Final[Dict[str, int]] = {
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


def get_acknowledge_actions(code: int) -> List[str]:
    """Get acknowledge actions from code.

    See: https://www.zabbix.com/documentation/current/en/manual/api/reference/event/acknowledge (action parameter)"""
    # Create reverse lookup for action bitmask
    acknowledge_actions = {v: k for k, v in ACKNOWLEDGE_ACTION_BITMASK.items()}
    active_action = []
    for n, action in acknowledge_actions.items():
        if code & n:
            active_action.append(action)
    return active_action


def get_autologin_type(code):
    """Get autologin type from code."""
    autologin_type = {0: "Disable", 1: "Enable"}

    if code in autologin_type:
        return autologin_type[code] + " (" + str(code) + ")"

    return f"Unknown ({str(code)})"


# TODO: refactor these two functions and add them to
# pyzabbix.types.UsergroupPermission


def get_permission(code: int) -> str:
    """Get permission."""
    permission = {0: "deny", 2: "ro", 3: "rw"}
    return _format_code(code, permission)


def get_permission_code(permission: str) -> int:
    """Get permission code."""
    permission_code = {"deny": 0, "ro": 2, "rw": 3}

    if permission in permission_code:
        return permission_code[permission]

    return 0


def get_item_type(code: int | None) -> str:
    """Get item type from code."""
    item_type = {
        0: "Zabbix agent",
        1: "SNMPv1 agent",
        2: "Zabbix trapper",
        3: "Simple check",
        4: "SNMPv2 agent",
        5: "Zabbix internal",
        6: "SNMPv3 agent",
        7: "Zabbix agent (active)",
        8: "Zabbix aggregate",
        9: "Web item",
        10: "External check",
        11: "Database monitor",
        12: "IPMI agent",
        13: "SSH agent",
        14: "TELNET agent",
        15: "calculated",
        16: "JMX agent",
        17: "SNMP trap",
        18: "Dependent item",
        19: "HTTP agent",
        20: "SNMP agent",
        21: "Script",
    }
    return _format_code(code, item_type)


def get_value_type(code: int | None) -> str:
    """Get value type from code."""
    value_type = {
        0: "Numeric float",
        1: "Character",
        2: "Log",
        3: "Numeric unsigned",
        4: "Text",
    }
    return _format_code(code, value_type)


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """Compile regex pattern."""
    try:
        p = re.compile(pattern)
    except re.error as e:
        raise ZabbixCLIError(f"Invalid regex pattern: {pattern}") from e
    return p


def get_macro_type(code: int | None) -> str:
    """Get macro type from code."""
    macro_type = {
        0: "Text",
        1: "Secret",
        2: "Vault secret",
    }
    return _format_code(code, macro_type)


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


def convert_time_to_interval(time: str) -> Tuple[datetime, datetime]:
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


def convert_timestamp_interval(time: str) -> Tuple[datetime, datetime]:
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


def sanitize_filename(filename: str) -> str:
    """Make a filename safe(r) for use in filesystems.

    Very naive implementation that removes illegal characters.
    Does not check for reserved names or path length."""
    return re.sub(r"[^\w\-.]", "_", filename)


def open_directory(
    directory: Path, command: Optional[str] = None, force: bool = False
) -> None:
    """Open directory in file explorer.

    Prints the path to the directory to stderr if no window server is detected.
    The path must be a directory, otherwise a ZabbixCLIError is raised.

    Args:
        directory (Path): The directory to open.
        command (str, optional): The command to use to open the directory. If `None`, the command is determined based on the platform.
        force (bool, optional): If `True`, open the directory even if no window server is detected. Defaults to `False`.
    """
    try:
        if not directory.exists():
            raise FileNotFoundError
        directory = directory.resolve(strict=True)
    except FileNotFoundError:
        raise ZabbixCLIError(f"Directory {directory} does not exist")
    except RuntimeError:
        raise ZabbixCLIError(f"Unable to resolve symlinks for {directory}")
    if not directory.is_dir():
        raise ZabbixCLIError(f"{directory} is not a directory")

    spath = str(directory)
    if sys.platform == "win32":
        subprocess.run([command or "explorer", spath])
    elif sys.platform == "darwin":
        subprocess.run([command or "open", spath])
    else:  # Linux and Unix
        if not os.environ.get("DISPLAY"):
            from zabbix_cli.output.console import print_path

            print_path(directory)
            if not force:
                return
        subprocess.run([command or "xdg-open", spath])
