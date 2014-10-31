#!/usr/bin/env python
#
# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014 USIT-University of Oslo
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

import socket
import os
import ConfigParser
import sys

class configuration():

    # ############################################
    # Constructor
    # ############################################
    
    def __init__(self):
        """ The Constructor."""
        
        self.config_file = ''

        # Zabbix API section
        self.zabbix_api_url = ''

        # LDAP section
        self.ldap_uri = ''
        self.ldap_users_tree = ''
        self.ldap_usergroups_tree = ''
        self.usergroups_to_sync = ''

        # Zabbix_config section
        self.default_hostgroup = '0'

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
        
        config_file_list = (os.getenv('HOME') + '/.zabbix-cli/zabbix-cli.conf','/etc/zabbix-cli/zabbix-cli.conf','/etc/zabbix-cli.conf')
        
        for file in config_file_list:
            if os.path.isfile(file):
                self.config_file = file 
                break

        if self.config_file == '':
            
            print '\n[ERROR]: No config file found. Exiting.\n'
            sys.exit(1)


    # ############################################
    # Method
    # ############################################
    
    def set_configuration_parameters(self):
        """Set configuration parameters"""

        if self.config_file:

            config = ConfigParser.RawConfigParser()
            config.read(self.config_file)
            
            #
            # Zabbix APIsection
            #
            
            if config.has_option('zabbix_api','zabbix_api_url'):
                self.zabbix_api_url = config.get('zabbix_api','zabbix_api_url')
    
            #
            # LDAP section
            #

            if config.has_option('ldap','ldap_uri'):
                self.ldap_uri = config.get('ldap','ldap_uri')    
                
            if config.has_option('ldap','ldap_users_tree'):
                self.ldap_users_tree = config.get('ldap','ldap_users_tree')

            if config.has_option('ldap','ldap_usergroups_tree'):
                self.ldap_usergroups_tree = config.get('ldap','ldap_usergroups_tree')

            if config.has_option('ldap','usergroups_to_sync'):
                self.usergroups_to_sync = config.get('ldap','usergroups_to_sync')
             
            #
            # Zabbix configuration
            #

            if config.has_option('zabbix_config','default_hostgroup'):
                self.default_hostgroup = config.get('zabbix_config','default_hostgroup')

            #
            # Logging section
            #

            if config.has_option('logging','logging'):
                self.logging = config.get('logging','logging')

            if config.has_option('logging','log_level'):
                self.log_level = config.get('logging','log_level')

            if config.has_option('logging','log_file'):
                self.log_file = config.get('logging','log_file')
            

