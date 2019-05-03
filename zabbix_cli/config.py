# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014-2016 USIT-University of Oslo
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
import os
import sys

try:
    # PY3
    import configparser
except ImportError:
    import ConfigParser as configparser

# Config file basename
CONFIG_FILENAME = 'zabbix-cli.conf'
CONFIG_FIXED_NAME = 'zabbix-cli.fixed.conf'

# Config file locations
CONFIG_DEFAULT_DIR = '/usr/share/zabbix-cli'
CONFIG_SYSTEM_DIR = '/etc/zabbix-cli'
CONFIG_USER_DIR = os.path.expanduser('~/.zabbix-cli')

# Any item will overwrite values from the previous
CONFIG_PRIORITY = tuple((
    os.path.join(d, f) for d, f in (
        (CONFIG_DEFAULT_DIR, CONFIG_FILENAME),
        (CONFIG_SYSTEM_DIR, CONFIG_FILENAME),
        (CONFIG_USER_DIR, CONFIG_FILENAME),
        (CONFIG_SYSTEM_DIR, CONFIG_FIXED_NAME),
        (CONFIG_DEFAULT_DIR, CONFIG_FIXED_NAME),
    )))

# Where custom configs should be put into the order
CONFIG_CUSTOM_GOES_AFTER = os.path.join(CONFIG_USER_DIR, CONFIG_FILENAME)

logger = logging.getLogger(__name__)


def get_priority(filename=None):
    """Get and ordered list of config file locations."""
    priority = list(CONFIG_PRIORITY)
    if filename:
        if CONFIG_CUSTOM_GOES_AFTER in priority:
            priority.insert(priority.index(CONFIG_CUSTOM_GOES_AFTER) + 1,
                            filename)
        else:
            priority.append(filename)
    return priority


def find_config(filename=None):
    """Find all available configuration files.

    :param filename: An optional user supplied file to throw into the mix
    """
    for filename in get_priority(filename):
        if os.path.isfile(filename):
            logger.debug('found config %r', filename)
            yield filename


class OptionDescriptor(object):
    """Descriptor to access ConfigParser settings as attributes."""

    # TODO: Add serialization, so that 'ON', 'OFF' -> boolean, etc...

    def __init__(self, section, option,
                 default=None, required=False, disable=False):
        self.section = section
        self.option = option
        self.default = default
        self.required = required
        self.disable = disable

    def __get__(self, obj, cls=None):
        if not obj:
            return self
        return obj.get(self.section, self.option)

    def __set__(self, obj, value):
        return obj.set(self.section, self.option, value)

    def __delete__(self, obj):
        return obj.set(self.section, self.option, self.default)

    def __repr__(self):
        return ('<{cls.__name__} {obj.section}.{obj.option}'
                ' default={obj.default!r}'
                ' required={obj.required!r}'
                ' disable={obj.disable!r}'
                '>').format(cls=type(self), obj=self)


class OptionRegister(collections.Mapping):
    """A registry of ConfigParser sections, options and default values."""

    def __init__(self):
        self._settings = collections.OrderedDict()

    def __len__(self):
        return len(self._settings)

    def __iter__(self):
        return iter(self._settings)

    def __getitem__(self, option_tuple):
        return self._settings[option_tuple]

    def add(self, section, option, *args, **kwargs):
        self._settings[(section, option)] = OptionDescriptor(section, option,
                                                             *args, **kwargs)
        return self._settings[(section, option)]

    @property
    def sections(self):
        def _get():
            seen = set()
            for section, option in self:
                if section not in seen:
                    seen.add(section)
                    yield section
        return tuple(_get())

    def initialize(self, obj):
        seen = set()
        for section, option in self:
            if section not in seen:
                seen.add(section)
                obj.add_section(section)
            obj.set(section, option, self[(section, option)].default)


class Configuration(configparser.RawConfigParser, object):
    """A custom ConfigParser object with zabbix-cli settings."""

    _registry = OptionRegister()

    zabbix_api_url = _registry.add(
        'zabbix_api', 'zabbix_api_url',
        required=True)

    cert_verify = _registry.add(
        'zabbix_api', 'cert_verify',
        default='ON')

    system_id = _registry.add(
        'zabbix_config', 'system_id',
        default='zabbix-ID')

    default_hostgroup = _registry.add(
        'zabbix_config', 'default_hostgroup',
        default='All-hosts')

    default_admin_usergroup = _registry.add(
        'zabbix_config', 'default_admin_usergroup',
        default='All-root')

    default_create_user_usergroup = _registry.add(
        'zabbix_config', 'default_create_user_usergroup',
        default='All-users')

    default_notification_users_usergroup = _registry.add(
        'zabbix_config', 'default_notification_users_usergroup',
        default='All-notification-users')

    default_directory_exports = _registry.add(
        'zabbix_config', 'default_directory_exports',
        default=os.path.expanduser('~/zabbix_exports'))

    default_export_format = _registry.add(
        'zabbix_config', 'default_export_format',
        default='XML',
        # We deactivate this until https://support.zabbix.com/browse/ZBX-10607
        # gets fixed.  We use XML as the export format.
        disable=True)

    include_timestamp_export_filename = _registry.add(
        'zabbix_config', 'include_timestamp_export_filename',
        default='ON'
    )

    use_colors = _registry.add(
        'zabbix_config', 'use_colors',
        default='ON')

    use_auth_token_file = _registry.add(
        'zabbix_config', 'use_auth_token_file',
        default='OFF')

    use_paging = _registry.add(
        'zabbix_config', 'use_paging',
        default='OFF')

    logging = _registry.add(
        'logging', 'logging',
        default='OFF')

    log_level = _registry.add(
        'logging', 'log_level',
        default='ERROR')

    log_file = _registry.add(
        'logging', 'log_file',
        default='/var/log/zabbix-cli/zabbix-cli.log')

    def __init__(self):
        super(Configuration, self).__init__()
        self._registry.initialize(self)
        self.loaded_files = []

    def set(self, section, option, value):
        descriptor = self._registry[(section, option)]
        if descriptor.disable and value != descriptor.default:
            logger.warning('setting %s.%s is disabled, setting to %r',
                           section, option, descriptor.default)
            value = descriptor.default
        return super(Configuration, self).set(section, option, value)

    def read(self, filenames):
        files_read = super(Configuration, self).read(filenames)
        for filename in files_read:
            if filename in self.loaded_files:
                self.loaded_files.remove(filename)
            self.loaded_files.append(filename)
        return files_read

    def readfp(self, fp, filename=None):
        try:
            add_filename = filename or fp.name
        except AttributeError:
            pass
        retval = super(Configuration, self).readfp(fp, filename=filename)
        if add_filename:
            self.loaded_files.append(add_filename)
        return retval  # should be None

    def iter_descriptors(self):
        return iter(self._registry.values())

    def iter_required(self):
        for descriptor in self.iter_descriptors():
            if descriptor.required:
                yield descriptor

    def iter_missing(self):
        for descriptor in self.iter_required():
            value = self.get(descriptor.section, descriptor.option)
            if value == descriptor.default:
                yield descriptor


def get_config(filename=None):
    config = Configuration()
    for filename in find_config(filename):
        logger.debug('loading config %r', filename)
        config.read(filename)
    return config


def validate_config(config):
    missing = ['{0.section}.{0.option}'.format(d)
               for d in config.iter_missing()]
    if missing:
        raise ValueError("Missing settings: " + ', '.join(missing))


#
# python -m zabbix_cli.config
#

def main(inargs=None):
    import argparse

    class Actions(object):
        """Subparser to function map."""

        def __init__(self):
            self.funcmap = dict()

        def __getitem__(self, key):
            return self.funcmap[key]

        def __call__(self, subparser):
            def wrapper(func):
                key = subparser.prog.split(' ')[-1]
                self.funcmap[key] = func
                return func
            return wrapper

    parser = argparse.ArgumentParser(description='write default config')
    commands = parser.add_subparsers(title='commands', dest='command')
    actions = Actions()

    #
    # defaults [filename]
    #
    defaults_cmd = commands.add_parser('defaults')
    defaults_cmd.add_argument(
        'output',
        type=argparse.FileType('w'),
        nargs='?',
        default='-',
        metavar='FILE',
        help='Write an example config to %(metavar)s (default: stdout)')

    @actions(defaults_cmd)
    def write_default_config(args):
        config = Configuration()
        config.write(args.output)
        args.output.flush()
        if args.output not in (sys.stdout, sys.stderr):
            args.output.close()

    #
    # show
    #
    show_cmd = commands.add_parser('show')
    show_cmd.add_argument(
        '-c', '--config',
        default=None,
        metavar='FILE',
        help='Use config from %(metavar)s')
    show_cmd.add_argument(
        '-v', '--validate',
        action='store_true',
        default=False,
        help='validate config')

    @actions(show_cmd)
    def show_config(args):
        config = get_config(args.config)
        if args.validate:
            validate_config(config)
        config.write(sys.stdout)
        sys.stdout.flush()

    args = parser.parse_args()
    actions[args.command](args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
