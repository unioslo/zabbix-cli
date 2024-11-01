# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014-2015 USIT-University of Oslo
#
# This file is part of Zabbix-CLI
# https://github.com/rafaelma/zabbix-cli
#
# Zabbix-CLI is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Zabbix-CLI is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zabbix-CLI.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import annotations

import collections
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal

if TYPE_CHECKING:
    from zabbix_cli.config.model import LoggingConfig

# NOTE: important that this logger is named `zabbix_cli` with an underscore
# so that modules calling `logging.getLogger(__name__)` inherit the same
# configuration
logger = logging.getLogger("zabbix_cli")

DEFAULT_FORMAT = " ".join(
    (
        "%(asctime)s",
        "[%(name)s][%(user)s][%(levelname)s][%(filename)s:%(lineno)d %(funcName)s]:",
        "%(message)s",
    )
)


def remove_markup(text: str) -> str:
    """Remove Rich markup from a string."""
    from zabbix_cli.utils.rich import get_text

    # NOTE: we cannot EVER log when removing markup from a record, since
    # we would infinitely recurse into this function
    t = get_text(text, log=False)
    return t.plain


class ContextFilter(logging.Filter):
    """Log filter that adds a static field to a record."""

    def __init__(self, field: str, value: Any) -> None:
        self.field = field
        self.value = value

    def filter(self, record: logging.LogRecord) -> Literal[True]:
        setattr(record, self.field, self.value)
        return True


class SafeRecord(logging.LogRecord):
    """A LogRecord wrapper that returns None for unset fields."""

    def __init__(self, record: logging.LogRecord):
        self.__dict__ = collections.defaultdict(lambda: None, record.__dict__)


class SafeFormatter(logging.Formatter):
    """A Formatter that uses SafeRecord to avoid failure."""

    def format(self, record: logging.LogRecord) -> str:
        record = SafeRecord(record)
        record.msg = remove_markup(record.msg)
        return super().format(record)


LogLevelStr = Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"]


def get_log_level(level: LogLevelStr) -> int:
    if level == "DEBUG":
        return logging.DEBUG
    elif level == "INFO":
        return logging.INFO
    elif level in ("WARN", "WARNING"):
        return logging.WARNING
    elif level == "ERROR":
        return logging.ERROR
    elif level in ("CRITICAL", "FATAL"):
        return logging.CRITICAL
    else:
        return logging.NOTSET


def add_user(user: str) -> None:
    """Add a username to the log record."""
    add_log_context("user", user)


def add_log_context(field: str, value: Any) -> None:
    """Add a ContextFilter filter to the root logger's handlers."""
    root_logger = logging.getLogger()
    # In order to affect all loggers, we need to modify the handler itself
    # rather than the logger's filters. Filters are not propagated to
    # child loggers, but since they all share the same handler, we can
    # modify the handler's filters to achieve this.
    for handler in root_logger.handlers:
        # Modify existing filter if exists, otherwise add a new one
        for filter_ in handler.filters:
            if isinstance(filter_, ContextFilter) and filter_.field == field:
                filter_.value = value
                break
        else:
            handler.addFilter(ContextFilter(field, value))


def get_file_handler_safe(filename: Path) -> logging.Handler:
    """Return a FileHandler that does not fail if the file cannot be opened.

    Returns a stderr StreamHandler if the file cannot be opened."""
    from zabbix_cli.utils.fs import mkdir_if_not_exists

    try:
        mkdir_if_not_exists(filename.parent)
        return logging.FileHandler(filename)
    except Exception as e:
        from zabbix_cli.output.console import error

        error(f"Could not open log file {filename} for writing: {e}")
        return logging.StreamHandler()


def configure_logging(config: LoggingConfig | None = None):
    """Configure the root logger."""
    if not config:
        from zabbix_cli.config.model import LoggingConfig

        config = LoggingConfig()
        # unconfigured logging uses debug log level to catch everything
        config.log_level = "DEBUG"

    if config.enabled and config.log_file:
        # log to given filename
        handler = get_file_handler_safe(config.log_file)
    elif config.enabled:
        # log to stderr
        handler = logging.StreamHandler(sys.stderr)
    else:
        # disable logging
        handler = logging.NullHandler()

    level = get_log_level(config.log_level)
    handler.setFormatter(SafeFormatter(fmt=DEFAULT_FORMAT))

    # Configure root logger and zabbix-cli logger
    root = logging.getLogger()
    root.handlers.clear()  # clear any existing handlers
    root.addHandler(handler)
    root.setLevel(level)
    logger.setLevel(level)  # configure global app logger

    # Also log from HTTPX
    httpx = logging.getLogger("httpx")
    httpx.setLevel(level)
