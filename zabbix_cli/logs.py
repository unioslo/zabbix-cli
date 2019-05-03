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
from __future__ import print_function

import collections
import logging
import sys

logger = logging.getLogger(__name__)

DEFAULT_FORMAT = " ".join((
    "%(asctime)s",
    "[%(name)s][%(user)s][%(process)d][%(levelname)s]:",
    "%(message)s",
))


class ContextFilter(logging.Filter):
    """Log filter that adds a static field to a record."""

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def filter(self, record):
        setattr(record, self.field, self.value)
        return True


class LogContext(object):
    """A context that adds ContextFilters to a logger."""

    def __init__(self, logger, **context):
        self.logger = logger
        self.filters = [ContextFilter(k, context[k]) for k in context]

    def __enter__(self):
        for f in self.filters:
            self.logger.addFilter(f)
        return self.logger

    def __exit__(self, *args, **kwargs):
        for f in self.filters:
            self.logger.removeFilter(f)


class SafeRecord(logging.LogRecord, object):
    """A LogRecord wrapper that returns None for unset fields."""

    def __init__(self, record):
        self.__dict__ = collections.defaultdict(lambda: None, record.__dict__)


class SafeFormatter(logging.Formatter):
    """A Formatter that use SafeRecord to avoid failure."""

    def format(self, record):
        record = SafeRecord(record)
        return super(SafeFormatter, self).format(record)


def get_log_level(level):
    if level and level.isdigit():
        return int(level)
    elif level:
        # Given a name, getLevelName returns the int level
        return logging.getLevelName(level.upper())
    else:
        return logging.NOTSET


def configure_logging(config):
    """Configure the root logger."""
    enable = config.logging == 'ON'
    level = get_log_level(config.log_level)
    filename = config.log_file

    if enable and filename:
        # log to given filename
        handler = logging.FileHandler(filename)
    elif enable:
        # log to stderr
        handler = logging.StreamHandler(sys.stderr)
    else:
        # disable logging
        handler = logging.NullHandler()

    handler.setFormatter(SafeFormatter(fmt=DEFAULT_FORMAT))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)


#
# python -m zabbix_cli.logs
#

def main(inargs=None):
    import argparse
    from zabbix_cli.config import get_config

    parser = argparse.ArgumentParser('test log settings')
    parser.add_argument(
        '-c', '--config',
        default=None)
    parser.add_argument(
        '--level',
        dest='log_level',
        default=None,
        help='override %(dest)s from config')
    parser.add_argument(
        '--file',
        dest='log_file',
        default=None,
        help='override %(dest)s from config')
    parser.add_argument(
        '--enable',
        dest='logging',
        choices=('ON', 'OFF'),
        default=None,
        help='override %(dest)s from config')

    args = parser.parse_args(inargs)
    config = get_config(args.config)

    for attr in ('logging', 'log_level', 'log_file'):
        value = getattr(args, attr)
        if value is not None:
            setattr(config, attr, value)

    configure_logging(config)

    logger.debug('a debug message')
    logger.info('an info message')
    logger.warning('a warn message')
    logger.error('an error message')
    try:
        this_name_is_not_in_scope  # noqa: F821
    except NameError:
        logger.error('an error message with traceback', exc_info=True)

    logger.debug("Message without user context")
    with LogContext(logger, user='user1'):
        logger.debug("Message with context user=user1")
        with LogContext(logger, user='user2'):
            logger.debug("Message with nested context user=user2")
    logger.debug("Message after context")

    logger.info('done')


if __name__ == '__main__':
    main()
