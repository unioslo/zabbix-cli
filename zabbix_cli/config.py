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

import os
try:  # python 2 vs 3
    import configparser
except ImportError:
    import ConfigParser as configparser
import sys


class configuration():

    # ############################################
    # Constructor
    # ############################################

    def __init__(self, config_file_from_parameter):
        """ The Constructor."""

        self.config_file_from_parameter = config_file_from_parameter
        self.config_file_list = []

        # Zabbix API section
        self.zabbix_api_url = ''

        # Zabbix_config section
        self.system_id = 'zabbix-ID'
        self.default_hostgroup = 'All-hosts'
        self.default_admin_usergroup = 'Zabbix-root'
        self.default_create_user_usergroup = 'All-users'
        self.default_notification_users_usergroup = 'All-notification-users'
        self.default_directory_exports = os.getenv('HOME') + '/zabbix_exports'
        self.default_export_format = 'XML'
        self.include_timestamp_export_filename = 'ON'
        self.use_colors = 'ON'
        self.use_auth_token_file = 'OFF'
        self.use_paging = 'OFF'

        # Logging section
        self.logging = 'OFF'
        self.log_level = 'ERROR'
        self.log_file = '/var/log/zabbix-cli/zabbix-cli.log'

        self.set_configuration_file()
        self.set_configuration_parameters()

    # ############################################
    # Method
    # ############################################

    def set_configuration_file(self):
        """Set the zabbix-cli configuration file"""

        # This list defines the priority list of configuration files
        # that can exist in the system. Files close to the top of the
        # list will have priority to define configuration parameters
        # in the system.
        #
        # 1. /usr/share/zabbix-cli/zabbix-cli.fixed.conf
        # 2. /etc/zabbix-cli/zabbix-cli.fixed.conf
        # 3. Configuration file defined with the parameter -c / --config when executing zabbix-cli
        # 4. $HOME/.zabbix-cli/zabbix-cli.conf
        # 5. /etc/zabbix-cli/zabbix-cli.conf
        # 6. /usr/share/zabbix-cli/zabbix-cli.conf
        #

        config_file_priority_list = ['/usr/share/zabbix-cli/zabbix-cli.conf', '/etc/zabbix-cli/zabbix-cli.conf', os.getenv('HOME') + '/.zabbix-cli/zabbix-cli.conf'] + [self.config_file_from_parameter] + ['/etc/zabbix-cli/zabbix-cli.fixed.conf', '/usr/share/zabbix-cli/zabbix-cli.fixed.conf']

        # We check if the configuration files defined in
        # config_file_priority_list exist before we start reading
        # them.

        for file in config_file_priority_list:
            if os.path.isfile(file):
                self.config_file_list.append(file)

        if not self.config_file_list:

            print('\n[ERROR]: No config file found. Exiting.\n')
            sys.exit(1)

    # ############################################
    # Method
    # ############################################

    def set_configuration_parameters(self):
        """Set configuration parameters"""

        for config_file in self.config_file_list:

            config = configparser.RawConfigParser()
            config.read(config_file)

            #
            # Zabbix APIsection
            #

            if config.has_option('zabbix_api', 'zabbix_api_url'):
                self.zabbix_api_url = config.get('zabbix_api', 'zabbix_api_url')

            #
            # Zabbix configuration
            #

            if config.has_option('zabbix_config', 'system_id'):
                self.system_id = config.get('zabbix_config', 'system_id')

            if config.has_option('zabbix_config', 'default_hostgroup'):
                self.default_hostgroup = config.get('zabbix_config', 'default_hostgroup')

            if config.has_option('zabbix_config', 'default_admin_usergroup'):
                self.default_admin_usergroup = config.get('zabbix_config', 'default_admin_usergroup')

            if config.has_option('zabbix_config', 'default_create_user_usergroup'):
                self.default_create_user_usergroup = config.get('zabbix_config', 'default_create_user_usergroup')

            if config.has_option('zabbix_config', 'default_notification_users_usergroup'):
                self.default_notification_users_usergroup = config.get('zabbix_config', 'default_notification_users_usergroup')

            if config.has_option('zabbix_config', 'default_directory_exports'):
                self.default_directory_exports = config.get('zabbix_config', 'default_directory_exports')

            #
            # We deactivate this until https://support.zabbix.com/browse/ZBX-10607 gets fixed.
            # We use XML as the export format.
            #
            # if config.has_option('zabbix_config','default_export_format'):
            #    self.default_export_format = config.get('zabbix_config','default_export_format')
            #

            if config.has_option('zabbix_config', 'include_timestamp_export_filename'):
                self.include_timestamp_export_filename = config.get('zabbix_config', 'include_timestamp_export_filename')

            if config.has_option('zabbix_config', 'use_colors'):
                self.use_colors = config.get('zabbix_config', 'use_colors')

            if config.has_option('zabbix_config', 'use_auth_token_file'):
                self.use_auth_token_file = config.get('zabbix_config', 'use_auth_token_file')

            if config.has_option('zabbix_config', 'use_paging'):
                self.use_paging = config.get('zabbix_config', 'use_paging')

            #
            # Logging section
            #

            if config.has_option('logging', 'logging'):
                self.logging = config.get('logging', 'logging')

            if config.has_option('logging', 'log_level'):
                self.log_level = config.get('logging', 'log_level')

            if config.has_option('logging', 'log_file'):
                self.log_file = config.get('logging', 'log_file')
