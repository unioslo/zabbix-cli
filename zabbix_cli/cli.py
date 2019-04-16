# Authors:
# rafael@e-mc2.net / https://e-mc2.net/
#
# Copyright (c) 2014-2017 USIT-University of Oslo
#
# This file is part of Zabbix-CLI
# https://github.com/usit-gd/zabbix-cli
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
#

from __future__ import print_function

import ast
import cmd
import datetime
import distutils.version
import glob
import hashlib
import json
import logging
import os
import random
import re
import shlex
import signal
import subprocess
import sys
import textwrap
import time

# ipaddress is a dependency in python2 and stdlib in python3
import ipaddress  # noqa: I100, I202

import zabbix_cli
import zabbix_cli.apiutils
import zabbix_cli.utils
from zabbix_cli.prettytable import ALL, FRAME, PrettyTable
from zabbix_cli.pyzabbix import ZabbixAPI


# Python 2, 3 support
try:
    input = raw_input
except NameError:
    pass

logger = logging.getLogger(__name__)


class zabbixcli(cmd.Cmd):
    '''
    This class implements the Zabbix shell. It is based on the python module cmd
    '''

    # ###############################
    # Constructor
    # ###############################

    def __init__(self, conf, username='', password='', auth_token=''):
        cmd.Cmd.__init__(self)

        try:

            # Zabbix-cli version
            self.version = self.get_version()

            # Zabbix-cli welcome intro
            self.intro = '\n#############################################################\n' + \
                         'Welcome to the Zabbix command-line interface (v.' + self.version + ')\n' + \
                         '#############################################################\n' + \
                         'Type help or \\? to list commands.\n'

            # Pointer to Configuration class
            self.conf = conf

            # zabbix-API Username
            self.api_username = username

            # zabbix-API password
            self.api_password = password

            # zabbix-API auth-token
            self.api_auth_token = auth_token

            # Default output format (table|json|csv)
            self.output_format = 'table'

            # Use of colors (on|off)
            self.use_colors = self.conf.use_colors

            # Use of auth-token file (on|off)
            self.use_auth_token_file = self.conf.use_auth_token_file

            # Use paging (on|off)
            self.use_paging = self.conf.use_paging

            # Bulk execution of commands (True|False)
            self.bulk_execution = False

            # Non-interactive execution (True|False)
            self.non_interactive = False

            # SystemID show in prompt text
            self.system_id = self.conf.system_id

            # Prompt text
            self.prompt = '[zabbix-cli ' + self.api_username + '@' + self.system_id + ']$ '
            logger.debug('Zabbix API url: %s', self.conf.zabbix_api_url)

            #
            # Connecting to the Zabbix JSON-API
            #

            zabbix_auth_token_file = os.getenv('HOME') + '/.zabbix-cli_auth_token'

            self.zapi = ZabbixAPI(self.conf.zabbix_api_url)
            self.zapi.session.verify = True

            self.api_auth_token = self.zapi.login(self.api_username, self.api_password, self.api_auth_token)

            logger.debug('Connected to Zabbix JSON-API')

            #
            # The file $HOME/.zabbix-cli_auth_token is created if it does not exists.
            #
            # Format:
            # USERNAME::API-auth-token returned after the las login.
            #

            if self.use_auth_token_file == 'ON' and not os.path.isfile(zabbix_auth_token_file):

                with open(zabbix_auth_token_file, 'w') as auth_token_file:
                    auth_token_file.write(self.api_username + '::' + self.api_auth_token)
                    auth_token_file.flush()

                logger.info('API-auth-token file created.')

            #
            # Populate the dictionary used as a cache with hostid and
            # hostname data
            #

            self.hostid_cache = self.populate_hostid_cache()

            #
            # Populate the dictionary used as a cache with proxyid and
            # proxy name data
            #

            self.proxyid_cache = self.populate_proxyid_cache()

            #
            # Populate the dictionary used as a cache with hostgroupname and
            # hostgroupid
            #

            self.hostgroupname_cache = self.populate_hostgroupname_cache()

        except Exception as e:
            print('\n[ERROR]: ' + str(e) + '\n')

            logger.error('Problems logging on to %r', self.conf.zabbix_api_url)

            zabbix_auth_token_file = os.getenv('HOME') + '/.zabbix-cli_auth_token'

            if os.path.isfile(zabbix_auth_token_file):

                try:
                    os.remove(zabbix_auth_token_file)
                    logger.info('API-auth-token has probably expired. File %s deleted.', zabbix_auth_token_file)

                except Exception as e:
                    print('\n[ERROR]: ' + str(e) + '\n')
                    logger.error('Problems deleting file %s - %s', zabbix_auth_token_file, e)
                    sys.exit(1)

            sys.exit(1)

    def do_show_maintenance_definitions(self, args):
        '''
        DESCRIPTION:
        This command shows maintenance definitions global
        information. The logical operator AND will be used if one
        defines more than one parameter.

        COMMAND:
        show_maintenance_definitions [definitionID]
                                     [hostgroup]
                                     [host]

        [definitionID]
        --------------
        Definition ID. One can define more than one value.

        [hostgroup]:
        ------------
        Hostgroup name. One can define more than one value.

        [host]:
        -------
        Hostname. One can define more than one value.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + str(e) + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                maintenances = input('# MaintenanceID [*]: ').strip()
                hostgroups = input('# Hostgroups [*]: ').strip()
                hostnames = input('# Hosts [*]: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 3:
            maintenances = arg_list[0].strip()
            hostgroups = arg_list[1].strip()
            hostnames = arg_list[2].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Generate maintenances, hosts and hostgroups IDs
        #

        try:
            maintenance_list = []
            hostnames_list = []
            hostgroups_list = []
            maintenance_ids = ''
            hostgroup_ids = ''
            host_ids = ''
            search_data = ','

            if maintenances == '*':
                maintenances = ''

            if hostgroups == '*':
                hostgroups = ''

            if hostnames == '*':
                hostnames = ''

            if maintenances != '':
                for maintenance in maintenances.split(','):
                    maintenance_list.append(str(maintenance).strip())

                maintenance_ids = "','".join(maintenance_list)
                search_data += '\'maintenanceids\':[\'' + maintenance_ids + '\'],'

            if hostgroups != '':

                for hostgroup in hostgroups.split(','):

                    if hostgroup.isdigit():
                        hostgroups_list.append(str(hostgroup).strip())
                    else:
                        hostgroups_list.append(str(self.get_hostgroup_id(hostgroup.strip())))

                hostgroup_ids = "','".join(hostgroups_list)
                search_data += '\'groupids\':[\'' + hostgroup_ids + '\'],'

            if hostnames != '':

                for hostname in hostnames.split(','):

                    if hostname.isdigit():
                        hostnames_list.append(str(hostname).strip())
                    else:
                        hostnames_list.append(str(self.get_host_id(hostname.strip())))

                host_ids = "','".join(hostnames_list)
                search_data += '\'hostids\':[\'' + host_ids + '\'],'

        except Exception as e:
            logger.error('Problems getting maintenance definitions information - %s', e)
            self.generate_feedback('Error', 'Problems getting maintenance definitions information')
            return False

        #
        # Get result from Zabbix API
        #
        try:
            query = ast.literal_eval("{'output':'extend'" + search_data + "'selectGroups':['name'],'selectHosts':['name'],'sortfield':'maintenanceid','sortorder':'ASC','searchByAny':'True'}")
            result = self.zapi.maintenance.get(**query)
            logger.info('Command show_maintenance_definitions executed')
        except Exception as e:
            logger.error('Problems getting maintenance definitions information - %s', e)
            self.generate_feedback('Error', 'Problems getting maintenance definitions information')
            return False

        #
        # Get the columns we want to show from result
        #
        for maintenance in result:

            if (int(time.time()) - int(maintenance['active_till'])) > 0:
                state = 'Expired'
            else:
                state = 'Active'

            if self.output_format == 'json':

                result_columns[result_columns_key] = {'maintenanceid': maintenance['maintenanceid'],
                                                      'name': maintenance['name'],
                                                      'maintenance_type': zabbix_cli.utils.get_maintenance_type(int(maintenance['maintenance_type'])),
                                                      'state': state,
                                                      'active_till': maintenance['active_till'],
                                                      'hosts': maintenance['hosts'],
                                                      'groups': maintenance['groups'],
                                                      'description': maintenance['description']}

            else:

                host_list = []
                for host in maintenance['hosts']:
                    host_list.append(host['name'])

                host_list.sort()

                group_list = []
                for group in maintenance['groups']:
                    group_list.append(group['name'])

                group_list.sort()

                result_columns[result_columns_key] = {'1': maintenance['maintenanceid'],
                                                      '2': '\n'.join(textwrap.wrap(maintenance['name'], 30)),
                                                      '3': zabbix_cli.utils.get_maintenance_type(int(maintenance['maintenance_type'])),
                                                      '4': state,
                                                      '5': datetime.datetime.utcfromtimestamp(float(maintenance['active_till'])).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                                      '6': '\n'.join(host_list),
                                                      '7': '\n'.join(group_list),
                                                      '8': '\n'.join(textwrap.wrap(maintenance['description'], 40))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['ID', 'Name', 'Type', 'State', 'To', 'Hostnames', 'Hostgroups', 'Description'],
                             ['Name', 'Description', 'Hostnames', 'Hostgroups'],
                             ['ID'],
                             ALL)

    def do_show_maintenance_periods(self, args):
        '''
        DESCRIPTION:
        This command shows maintenance periods global information.

        COMMAND: show_maintenance_periods [definitionID]

        [definitionID]
        --------------
        Definition ID. One can define more than one value.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + str(e) + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                maintenances = input('# MaintenanceID [*]: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            maintenances = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Generate maintenances, hosts and hostgroups IDs
        #

        try:
            search_data = ','
            maintenance_list = []
            maintenance_ids = ''

            if maintenances == '*':
                maintenances = ''

            if maintenances != '':
                for maintenance in maintenances.split(','):
                    maintenance_list.append(str(maintenance).strip())

                maintenance_ids = "','".join(maintenance_list)
                search_data += '\'maintenanceids\':[\'' + maintenance_ids + '\'],'

        except Exception as e:
            logger.error('Problems getting maintenance periods information - %s', e)
            self.generate_feedback('Error', 'Problems getting maintenance periods information')
            return False

        #
        # Get result from Zabbix API
        #
        try:
            query = ast.literal_eval("{'output':'extend'" + search_data + "'selectGroups':['name'],'selectHosts':['name'],'selectTimeperiods':['timeperiodid','day','dayofweek','every','month','period','start_date','start_time','timeperiod_type'],'sortfield':'maintenanceid','sortorder':'ASC','searchByAny':'True'}")
            result = self.zapi.maintenance.get(**query)

            logger.info('Command show_maintenance_periods executed')

        except Exception as e:
            logger.error('Problems getting maintenance periods information - %s', e)
            self.generate_feedback('Error', 'Problems getting maintenance periods information')
            return False

        #
        # Get the columns we want to show from result
        #
        for maintenance in result:

            if self.output_format == 'json':

                result_columns[result_columns_key] = {'maintenanceid': maintenance['maintenanceid'],
                                                      'name': maintenance['name'],
                                                      'timeperiods': maintenance['timeperiods'],
                                                      'hosts': maintenance['hosts'],
                                                      'groups': maintenance['groups']}

                result_columns_key = result_columns_key + 1

            else:

                host_list = []
                for host in maintenance['hosts']:
                    host_list.append(host['name'])

                host_list.sort()

                group_list = []
                for group in maintenance['groups']:
                    group_list.append(group['name'])

                group_list.sort()

                for period in maintenance['timeperiods']:

                    result_columns[result_columns_key] = {1: maintenance['maintenanceid'],
                                                          2: '\n'.join(textwrap.wrap(maintenance['name'], 30)),
                                                          3: period['timeperiodid'],
                                                          4: period['day'],
                                                          5: format(int(period['dayofweek']), "07b"),
                                                          6: period['every'],
                                                          7: format(int(period['month']), "012b"),
                                                          8: datetime.datetime.utcfromtimestamp(float(period['start_date'])).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                                          9: str(datetime.timedelta(seconds=int(period['start_time']))),
                                                          10: str(datetime.timedelta(seconds=int(period['period']))),
                                                          11: zabbix_cli.utils.get_maintenance_period_type(int(period['timeperiod_type'])),
                                                          12: '\n'.join(host_list),
                                                          13: '\n'.join(group_list)}

                    result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['DefID', 'DefName', 'PerID', 'Days', 'Dayweek', 'Every', 'Month', 'Start_date', 'Start_time', 'Period', 'PerType', 'Hostnames', 'Hostgroups'],
                             ['DefName', 'Hostnames', 'Hostgroups'],
                             ['DefID'],
                             ALL)

    def do_show_zabbixcli_config(self, args):
        '''
        DESCRIPTION:
        This command shows information about the
        configuration used by this zabbix-cli instance.

        COMMAND:
        show_zabbixcli_config

        '''

        result_columns = {}
        for i, filename in enumerate(self.conf.loaded_files):
            result_columns[i] = {1: '* ' + filename}

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Active configuration files'],
                             ['Active configuration files'],
                             [''],
                             FRAME)

        #
        # Generate information with all the configuration parameters
        #
        result_columns = {}
        for i, desc in enumerate(self.conf.iter_descriptors()):
            result_columns[i] = {
                1: desc.option,
                2: self.conf.get(desc.section, desc.option),
            }

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Configuration parameter', 'Value'],
                             ['Value'],
                             ['Configuration parameter'],
                             FRAME)

    def do_show_hostgroups(self, args):
        '''
        DESCRIPTION:
        This command shows all hostgroups defined in the system.

        COMMAND:
        show_hostgroups
        '''

        cmd.Cmd.onecmd(self, 'show_hostgroup "*"')

    def do_show_hostgroup(self, args):
        '''
        DESCRIPTION:
        This command shows hostgroup information

        COMMAND:
        show_hostgroup [hostgroup]

        [hostgroup]:
        ----------------
        Hostgroup name. One can use wildcards.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + str(e) + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                hostgroup = input('# Hostgroup: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            hostgroup = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroup == '':
            self.generate_feedback('Error', 'Template value is empty')
            return False

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.hostgroup.get(output='extend',
                                             search={'name': hostgroup},
                                             searchWildcardsEnabled=True,
                                             selectHosts=['host'],
                                             sortfield='name',
                                             sortorder='ASC')

            logger.info('Command show_hostgroups executed')

        except Exception as e:
            logger.error('Problems getting hostgroups information - %s', e)
            self.generate_feedback('Error', 'Problems getting hostgroups information')
            return False

        #
        # Get the columns we want to show from result
        #
        for group in result:
            if self.output_format == 'json':
                result_columns[result_columns_key] = {'groupid': group['groupid'],
                                                      'name': group['name'],
                                                      'flags': zabbix_cli.utils.get_hostgroup_flag(int(group['flags'])),
                                                      'type': zabbix_cli.utils.get_hostgroup_type(int(group['internal'])),
                                                      'hosts': group['hosts']}
            else:
                host_list = []
                for host in group['hosts']:
                    host_list.append(host['host'])

                host_list.sort()

                result_columns[result_columns_key] = {'1': group['groupid'],
                                                      '2': group['name'],
                                                      '3': zabbix_cli.utils.get_hostgroup_flag(int(group['flags'])),
                                                      '4': zabbix_cli.utils.get_hostgroup_type(int(group['internal'])),
                                                      '5': '\n'.join(textwrap.wrap(', '.join(host_list), 60))}
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['GroupID', 'Name', 'Flag', 'Type', 'Hosts'],
                             ['Name', 'Hosts'],
                             ['GroupID'],
                             ALL)

    def do_show_hosts(self, args):
        '''
        DESCRIPTION:
        This command shows all hosts defined in the system.

        COMMAND:
        show_hosts
        '''

        cmd.Cmd.onecmd(self, 'show_host "*"')

    def do_show_host(self, args):
        '''
        DESCRIPTION:
        This command shows hosts information

        COMMAND:
        show_host [HostID / Hostname]
                  [Filter]

        [HostID / Hostname]:
        -------------------
        One can search by HostID or by Hostname. One can use wildcards
        if we search by Hostname

        [Filter]:
        --------
        * Zabbix agent: 'available': 0=Unknown
                                     1=Available
                                     2=Unavailable

        * Maintenance: 'maintenance_status': 0:No maintenance
                                             1:In progress

        * Status: 'status': 0:Monitored
                            1: Not monitored

        e.g.: Show all hosts with Zabbix agent: Available AND Status: Monitored:
              show_host * "'available':'1','status':'0'"

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + str(e) + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                host = input('# Host: ').strip()
                filter = input('# Filter: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 1:

            host = arg_list[0].strip()
            filter = ''

        #
        # Command with filters attributes
        #

        elif len(arg_list) == 2:

            host = arg_list[0].strip()
            filter = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Check if we are searching by hostname or hostID
        #

        if host.isdigit():
            search_host = '\'hostids\':\'' + host + '\''
        else:
            search_host = '\'search\':{\'host\':\'' + host + '\'}'

        #
        # Generate query
        #

        try:
            query = ast.literal_eval("{'output':'extend'," + search_host + ",'selectParentTemplates':['templateid','name'],'selectGroups':['groupid','name'],'selectApplications':['name'],'sortfield':'host','sortorder':'ASC','searchWildcardsEnabled':'True','filter':{" + filter + "}}")
        except Exception as e:
            logger.error('Problems generating show_host query - %s', e)
            self.generate_feedback('Error', 'Problems generating show_host query')
            return False

        #
        # Get result from Zabbix API
        #

        try:
            result = self.zapi.host.get(**query)
            logger.info('Command show_host executed.')
        except Exception as e:
            logger.error('Problems getting host information - %s', e)
            self.generate_feedback('Error', 'Problems getting host information')
            return False

        #
        # Get the columns we want to show from result
        #

        for host in result:
            proxy = self.zapi.proxy.get(proxyids=host['proxy_hostid'])
            proxy_name = proxy[0]['host'] if proxy else ""
            if self.output_format == 'json':
                result_columns[result_columns_key] = {'hostid': host['hostid'],
                                                      'host': host['host'],
                                                      'groups': host['groups'],
                                                      'templates': host['parentTemplates'],
                                                      'zabbix_agent': zabbix_cli.utils.get_zabbix_agent_status(int(host['available'])),
                                                      'maintenance_status': zabbix_cli.utils.get_maintenance_status(int(host['maintenance_status'])),
                                                      'status': zabbix_cli.utils.get_monitoring_status(int(host['status'])),
                                                      'proxy': proxy_name}

            else:

                hostgroup_list = []
                template_list = []

                for hostgroup in host['groups']:
                    hostgroup_list.append(hostgroup['name'])

                for template in host['parentTemplates']:
                    template_list.append(template['name'])

                hostgroup_list.sort()
                template_list.sort()

                result_columns[result_columns_key] = {'1': host['hostid'],
                                                      '2': host['host'],
                                                      '3': '\n'.join(hostgroup_list),
                                                      '4': '\n'.join(template_list),
                                                      '5': zabbix_cli.utils.get_zabbix_agent_status(int(host['available'])),
                                                      '6': zabbix_cli.utils.get_maintenance_status(int(host['maintenance_status'])),
                                                      '7': zabbix_cli.utils.get_monitoring_status(int(host['status'])),
                                                      '8': proxy_name}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['HostID', 'Name', 'Hostgroups', 'Templates', 'Zabbix agent', 'Maintenance', 'Status', 'Proxy'],
                             ['Name', 'Hostgroups', 'Templates'],
                             ['HostID'],
                             ALL)

    def do_update_host_inventory(self, args):
        '''
        DESCRIPTION:
        This command updates one hosts' inventory

        COMMAND:
        update_host_inventory [hostname]
                              [inventory_key]
                              [inventory value]

        Inventory key is not the same as seen in web-gui. To
        look at possible keys and their current values, use
        "zabbix-cli --use-json-format show_host_inventory <hostname>"
        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + str(e) + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                host = input('# Host: ')
                inventory_key = input('# Inventory key: ')
                inventory_value = input('# Inventory value: ')
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without inventory_key and inventory value  attributes
        #

        elif len(arg_list) == 1:

            host = arg_list[0]
            inventory_key = input('# Inventory key: ')
            inventory_value = input('# Inventory value: ')

        #
        # Command cithout inventory value attribute
        #

        elif len(arg_list) == 2:

            host = arg_list[0]
            inventory_key = arg_list[1]
            inventory_value = input('# Inventory value: ')

        elif len(arg_list) == 3:

            host = arg_list[0]
            inventory_key = arg_list[1]
            inventory_value = arg_list[2]

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        try:
            host_id = str(self.get_host_id(host))

        except Exception as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Generate query
        #

        if host_id == '0':
            self.generate_feedback('Error', 'Host id for "' + host + '" not found')
            return False

        update_id = "'hostid': '" + host_id + "'"
        update_value = "'inventory':  {'" + inventory_key + "':'" + inventory_value + "'}"

        try:
            query = ast.literal_eval("{" + update_id + "," + update_value + "}")

        except Exception as e:
            logger.error('Problems generating query - %s', e)
            self.generate_feedback('Error', 'Problems generating query')
            return False

        #
        # Get result from Zabbix API
        #

        try:
            self.zapi.host.update(**query)
            logger.info('Command update_host_inventory executed [%s] [%s] [%s].', host, inventory_key, inventory_value)
        except Exception as e:
            logger.error('Problems updating host inventory information - %s', e)
            self.generate_feedback('Error', 'Problems updating host inventory information')
            return False

    def do_show_host_inventory(self, args):
        '''
        DESCRIPTION:
        This command shows hosts inventory

        COMMAND:
        show_host_inventory [Hostname]

        [Hostname]:
        ----------
        Hostname.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                host = input('# Host: ').strip()
                filter = input('# Filter: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #
        #

        elif len(arg_list) == 1:

            host = arg_list[0].strip()
            filter = ''

        #
        # Command with filters attributes
        #

        elif len(arg_list) == 2:

            host = arg_list[0].strip()
            filter = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Check if we are searching by hostname or hostID
        #

        if host.isdigit():
            search_host = '\'hostids\':\'' + host + '\''
        else:
            search_host = '\'search\':{\'host\':\'' + host + '\'}'

        #
        # Generate query
        #

        try:
            query = ast.literal_eval("{'output':'extend'," + search_host + ",'selectInventory':'extend','sortfield':'host','sortorder':'ASC','searchWildcardsEnabled':'True','filter':{" + filter + "}}")
        except Exception as e:
            logger.error('Problems generating query - %s', e)
            self.generate_feedback('Error', 'Problems generating query')
            return False

        #
        # Get result from Zabbix API
        #

        try:
            result = self.zapi.host.get(**query)
            logger.info('Command show_host_inventory [%s] executed.', host)
        except Exception as e:
            logger.error('Problems getting host inventory information - %s', e)
            self.generate_feedback('Error', 'Problems getting host inventory information')
            return False

        #
        # Get the columns we want to show from result if the host has
        # some inventory data
        #

        for host in result:

            if host['inventory'] != []:

                if self.output_format == 'json':
                    result_columns[result_columns_key] = dict({"host": host['host']}.items() + host['inventory'].items())

                else:
                    result_columns[result_columns_key] = {'1': host['host'],
                                                          '2': host['inventory']['vendor'],
                                                          '3': host['inventory']['chassis'],
                                                          '4': host['inventory']['host_router'],
                                                          '5': host['inventory']['poc_1_email']}
                result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Hostname', 'Vendor', 'Chassis', 'Networks', 'Contact'],
                             ['Hostname', 'Chassis', 'Contact'],
                             [],
                             FRAME)

    def do_show_usergroups(self, args):
        '''
        DESCRIPTION:
        This command shows all usergroups defined in the system.

        COMMAND:
        show_usergroups
        '''

        cmd.Cmd.onecmd(self, 'show_usergroup "*"')

    def do_show_usergroup(self, args):
        '''
        DESCRIPTION:
        This command shows user group information.

        COMMAND:
        show_usergroup [usergroup]

        [usergroup]
        -----------
        User group name. One can use wildcards.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                usergroup = input('# Usergroup: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            usergroup = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if usergroup == '':
            self.generate_feedback('Error', 'Usergroup value is empty')
            return False

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.usergroup.get(output='extend',
                                             search={'name': usergroup},
                                             searchWildcardsEnabled=True,
                                             sortfield='name',
                                             sortorder='ASC',
                                             selectUsers=['alias'])
            logger.info('Command show_usergroup executed')
        except Exception as e:
            logger.error('Problems getting usergroup information - %s', e)
            self.generate_feedback('Error', 'Problems getting usergroup information')
            return False

        #
        # Get the columns we want to show from result
        #
        for group in result:

            if self.output_format == 'json':

                result_columns[result_columns_key] = {'usrgrpid': group['usrgrpid'],
                                                      'name': group['name'],
                                                      'gui_access': zabbix_cli.utils.get_gui_access(int(group['gui_access'])),
                                                      'user_status': zabbix_cli.utils.get_usergroup_status(int(group['users_status'])),
                                                      'users': group['users']}
            else:
                users = []
                for user in group['users']:
                    users.append(user['alias'])

                users.sort()

                result_columns[result_columns_key] = {'1': group['usrgrpid'],
                                                      '2': group['name'],
                                                      '3': zabbix_cli.utils.get_gui_access(int(group['gui_access'])),
                                                      '4': zabbix_cli.utils.get_usergroup_status(int(group['users_status'])),
                                                      '5': '\n'.join(textwrap.wrap(', '.join(users), 60))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['GroupID', 'Name', 'GUI access', 'Status', 'Users'],
                             ['Name', 'Users'],
                             ['GroupID'],
                             FRAME)

    def do_show_users(self, args):
        '''
        DESCRIPTION:
        This command shows users information.

        COMMAND:
        show_users
        '''

        result_columns = {}
        result_columns_key = 0

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.user.get(output='extend',
                                        getAccess=True,
                                        selectUsrgrps=['name'],
                                        sortfield='alias',
                                        sortorder='ASC')
            logger.info('Command show_users executed')
        except Exception as e:
            logger.error('Problems getting users information - %s', e)
            self.generate_feedback('Error', 'Problems getting users information')
            return False

        #
        # Get the columns we want to show from result
        #

        for user in result:

            if self.output_format == 'json':
                result_columns[result_columns_key] = {'userid': user['userid'],
                                                      'alias': user['alias'],
                                                      'name': user['name'] + ' ' + user['surname'],
                                                      'autologin': zabbix_cli.utils.get_autologin_type(int(user['autologin'])),
                                                      'autologout': user['autologout'],
                                                      'type': zabbix_cli.utils.get_user_type(int(user['type'])),
                                                      'usrgrps': user['usrgrps']}

            else:

                usrgrps = []

                for group in user['usrgrps']:
                    usrgrps.append(group['name'])

                result_columns[result_columns_key] = {'1': user['userid'],
                                                      '2': user['alias'],
                                                      '3': user['name'] + ' ' + user['surname'],
                                                      '4': zabbix_cli.utils.get_autologin_type(int(user['autologin'])),
                                                      '5': user['autologout'],
                                                      '6': zabbix_cli.utils.get_user_type(int(user['type'])),
                                                      '7': '\n'.join(textwrap.wrap(', '.join(usrgrps), 60))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['UserID', 'Alias', 'Name', 'Autologin', 'Autologout', 'Type', 'Usrgrps'],
                             ['Name', 'Type', 'Usrgrps'],
                             ['UserID'],
                             FRAME)

    def do_show_alarms(self, args):
        '''
        DESCRIPTION:

        This command shows all active alarms with the last event
        unacknowledged.

        COMMAND:
        show_alarms [description]
                    [filters]
                    [hostgroups]
                    [Last event unacknowledged]

        [description]
        -------------
        Type of alarm description to search for. Leave this parameter
        empty to search for all descriptions. One can also use wildcards.


        [filters]
        ---------
        One can filter the result by host and priority. No wildcards
        can be used.

        Priority values:

        0 - (default) not classified;
        1 - information;
        2 - warning;
        3 - average;
        4 - high;
        5 - disaster.

        [hostgroups]
        -----------
        One can filter the result to get alarms from a particular
        hostgroup or group og hostgroups. One can define several
        values in a comma separated list.

        [Last event unacknowledged]
        ---------------------------
        One can filter the result after the acknowledged value of the
        last event of an alarm.

        Values:

        true - (default) Show only active alarms with last event unacknowledged.
        false - Show all active alarms, also those with the last event acknowledged.


        e.g.: Get all alarms with priority 'High' that contain the word
              'disk' in the description for the host 'host.example.org' and
              the last event unacknowledged

        show_alarms *disk* "'host':'host.example.org','priority':'4'" * true

        '''

        result_columns = {}
        result_columns_key = 0
        filters = ''
        hostgroup_list = []

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                description = input('# Description []: ').strip()
                filters = input('# Filter []: ').strip()
                hostgroups = input('# Hostgroups []: ').strip()
                ack_filter = input('# Last event unacknowledged [true]: ').strip().lower()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 4:

            description = arg_list[0].strip()
            filters = arg_list[1].strip()
            hostgroups = arg_list[2].strip()
            ack_filter = arg_list[3].strip().lower()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if ack_filter in ['', 'true']:
            ack_filter = ",'withLastEventUnacknowledged':'True'"
        elif ack_filter in ['*', 'false']:
            ack_filter = ""
        else:
            ack_filter = ",'withLastEventUnacknowledged':'True'"

        if filters == '*':
            filters = ''

        if filters != '':
            filters = ',' + filters

        if hostgroups == '' or hostgroups == '*':
            groupids = ''

        else:

            #
            # Generate a list with all hostgroupsIDs from the defined
            # hostgroups
            #

            for hostgroup in hostgroups.split(','):
                if hostgroup.isdigit():
                    hostgroup_list.append(hostgroup)
                else:
                    try:
                        hostgroup_list.append(self.get_hostgroup_id(hostgroup.strip()))

                    except Exception as e:
                        logger.error('Problems getting the hostgroupID for %s - %s', hostgroup, e)
                        self.generate_feedback('Error', 'Problems getting the hostgroupID for [' + hostgroup + ']')
                        return False

            groupids = "'groupids':['" + "','".join(hostgroup_list) + "']"

        #
        # Generate query
        #

        try:
            query = ast.literal_eval("{'selectHosts':'host'" + ack_filter + ",'search':{'description':'" + description + "'},'skipDependent':1,'monitored':1,'active':1,'output':'extend','expandDescription':1,'sortfield':'lastchange','sortorder':'DESC','searchWildcardsEnabled':'True','filter':{'value':'1'" + filters + "}," + groupids + "}")
        except Exception as e:
            logger.error('Problems generating show_alarms query - %s', e)
            self.generate_feedback('Error', 'Problems generating show_alarms query')
            return False

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.trigger.get(**query)
            logger.info('Command show_alarms executed')
        except Exception as e:
            logger.error('Problems getting alarm information - %s', e)
            self.generate_feedback('Error', 'Problems getting alarm information')
            return False

        #
        # Get the columns we want to show from result
        #
        for trigger in result:

            lastchange = datetime.datetime.fromtimestamp(int(trigger['lastchange']))
            age = datetime.datetime.now() - lastchange

            if self.output_format == 'json':
                result_columns[result_columns_key] = {'triggerid': trigger['triggerid'],
                                                      'hostname': self.get_host_name(trigger['hosts'][0]['hostid']),
                                                      'description': trigger['description'],
                                                      'severity': zabbix_cli.utils.get_trigger_severity(int(trigger['priority'])),
                                                      'lastchange': str(lastchange),
                                                      'age': str(age)}
            else:

                if self.use_colors == 'ON':

                    if int(trigger['priority']) == 1:
                        ansi_code = "\033[38;5;158m"
                        ansi_end = "\033[0m"

                    elif int(trigger['priority']) == 2:
                        ansi_code = "\033[38;5;190m"
                        ansi_end = "\033[0m"

                    elif int(trigger['priority']) == 3:
                        ansi_code = "\033[38;5;208m"
                        ansi_end = "\033[0m"

                    elif int(trigger['priority']) == 4:
                        ansi_code = "\033[38;5;160m"
                        ansi_end = "\033[0m"

                    elif int(trigger['priority']) == 5:
                        ansi_code = "\033[38;5;196m"
                        ansi_end = "\033[0m"

                    else:
                        ansi_code = ''
                        ansi_end = ''

                else:
                    ansi_code = ''
                    ansi_end = ''

                result_columns[result_columns_key] = {'1': trigger['triggerid'],
                                                      '2': self.get_host_name(trigger['hosts'][0]['hostid']),
                                                      '3': '\n  '.join(textwrap.wrap("* " + trigger['description'], 62)),
                                                      '4': ansi_code + zabbix_cli.utils.get_trigger_severity(int(trigger['priority'])).upper() + ansi_end,
                                                      '5': str(lastchange),
                                                      '6': str(age)}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['TriggerID', 'Host', 'Description', 'Severity', 'Last change', 'Age'],
                             ['Host', 'Description', 'Last change', 'Age'],
                             ['TriggerID'],
                             FRAME)

    def do_add_host_to_hostgroup(self, args):
        '''
        DESCRIPTION:
        This command adds one/several hosts to
        one/several hostgroups

        COMMAND:
        add_host_to_hostgroup [hostnames]
                              [hostgroups]


        [hostnames]
        -----------
        Hostnames or IDs.
        One can define several values in a comma separated list.

        [hostgroups]
        ------------
        Hostgroup names or IDs.
        One can define several values in a comma separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                hostnames = input('# Hostnames: ').strip()
                hostgroups = input('# Hostgroups: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 2:

            hostnames = arg_list[0].strip()
            hostgroups = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroups == '':
            self.generate_feedback('Error', 'Hostgroups information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error', 'Hostnames information is empty')
            return False

        try:

            #
            # Generate hosts and hostgroups IDs
            #

            hostgroups_list = []
            hostnames_list = []
            hostgroup_ids = ''
            host_ids = ''

            for hostgroup in hostgroups.split(','):

                if hostgroup.isdigit():
                    hostgroups_list.append('{"groupid":"' + str(hostgroup).strip() + '"}')
                else:
                    hostgroups_list.append('{"groupid":"' + str(self.get_hostgroup_id(hostgroup.strip())) + '"}')

            hostgroup_ids = ','.join(hostgroups_list)

            for hostname in hostnames.split(','):

                if hostname.isdigit():
                    hostnames_list.append('{"hostid":"' + str(hostname).strip() + '"}')
                else:
                    hostnames_list.append('{"hostid":"' + str(self.get_host_id(hostname.strip())) + '"}')

            host_ids = ','.join(hostnames_list)

            #
            # Generate zabbix query
            #

            query = ast.literal_eval("{\"groups\":[" + hostgroup_ids + "],\"hosts\":[" + host_ids + "]}")

            #
            # Add hosts to hostgroups
            #

            self.zapi.hostgroup.massadd(**query)

            self.generate_feedback('Done', 'Hosts ' + hostnames + ' (' + host_ids + ') added to these groups: ' + hostgroups + ' (' + hostgroup_ids + ')')

            logger.info('Hosts: %s (%s) added to these groups: %s (%s)', hostnames, host_ids, hostgroups, hostgroup_ids)

        except Exception as e:
            logger.error('Problems adding hosts %s (%s) to groups %s (%s) - %s', hostnames, host_ids, hostgroups, hostgroup_ids, e)
            self.generate_feedback('Error', 'Problems adding hosts ' + hostnames + ' (' + host_ids + ') to groups ' + hostgroups + ' (' + hostgroup_ids + ')')
            return False

    def do_remove_host_from_hostgroup(self, args):
        '''
        DESCRIPTION:
        This command removes one/several hosts from
        one/several hostgroups

        COMMAND:
        remove_host_from_hostgroup [hostnames]
                                   [hostgroups]

        [hostnames]
        -----------
        Hostnames or IDs.
        One can define several values in a comma separated list.

        [hostgroups]
        ------------
        Hostgroup names or IDs.
        One can define several values in a comma separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                hostnames = input('# Hostnames: ').strip()
                hostgroups = input('# Hostgroups: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 2:

            hostnames = arg_list[0].strip()
            hostgroups = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('ERROR', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroups == '':
            self.generate_feedback('Error', 'Hostgroups information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error', 'Hostnames information is empty')
            return False

        try:

            #
            # Generate hosts and hostgroups IDs
            #

            hostgroups_list = []
            hostnames_list = []
            hostgroup_ids = ''
            host_ids = ''

            for hostgroup in hostgroups.split(','):

                if hostgroup.isdigit():
                    hostgroups_list.append(str(hostgroup).strip())
                else:
                    hostgroups_list.append(str(self.get_hostgroup_id(hostgroup.strip())))

            hostgroup_ids = ','.join(hostgroups_list)

            for hostname in hostnames.split(','):

                if hostname.isdigit():
                    hostnames_list.append(str(hostname).strip())
                else:
                    hostnames_list.append(str(self.get_host_id(hostname.strip())))

            host_ids = ','.join(hostnames_list)

            #
            # Generate zabbix query
            #
            query = ast.literal_eval("{\"groupids\":[" + hostgroup_ids + "],\"hostids\":[" + host_ids + "]}")

            #
            # Remove hosts from hostgroups
            #

            self.zapi.hostgroup.massremove(**query)
            logger.info('Hosts: %s (%s) removed from these groups: %s (%s)', hostnames, host_ids, hostgroups, hostgroup_ids)
            self.generate_feedback('Done', 'Hosts ' + hostnames + ' (' + host_ids + ') removed from these groups: ' + hostgroups + ' (' + hostgroup_ids + ')')
        except Exception as e:
            logger.error('Problems removing hosts %s (%s) from groups %s (%s) - %s', hostnames, host_ids, hostgroups, hostgroup_ids, e)
            self.generate_feedback('Error', 'Problems removing hosts ' + hostnames + ' (' + host_ids + ') from groups (' + hostgroups + ' (' + hostgroup_ids + ')')
            return False

    def do_add_user_to_usergroup(self, args):
        '''
        DESCRIPTION:
        This command adds one/several users to
        one/several usergroups

        COMMAND:
        add_user_to_usergroup [usernames]
                              [usergroups]


        [usernames]
        -----------
        Usernames or IDs.
        One can define several values in a comma separated list.

        [usergroups]
        ------------
        Usergroup names or IDs.
        One can define several values in a comma separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                usernames = input('# Usernames: ').strip()
                usergroups = input('# Usergroups: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 2:

            usernames = arg_list[0].strip()
            usergroups = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if usergroups == '':
            self.generate_feedback('Error', 'Usergroups value is empty')
            return False

        if usernames == '':
            self.generate_feedback('Error', 'Usernames value is empty')
            return False

        try:

            #
            # Generate users and usergroups IDs
            #

            usergroupids = []
            userids = []

            for usergroup in usergroups.split(','):

                if usergroup.isdigit():
                    usergroupids.append(str(usergroup).strip())
                else:
                    usergroupids.append(str(self.get_usergroup_id(usergroup.strip())))

            for username in usernames.split(','):

                if username.isdigit():
                    userids.append(str(username).strip())
                else:
                    userids.append(str(self.get_user_id(username.strip())))

            #
            # Add users to usergroups
            #

            for usergroupid in usergroupids:
                zabbix_cli.apiutils.update_usergroup(self.zapi, usergroupid, userids=userids)
            self.generate_feedback('Done', 'Users ' + usernames + ' added to these usergroups: ' + usergroups)
            logger.info('Users: %s added to these usergroups: %s', usernames, usergroups)

        except Exception as e:
            logger.error('Problems adding users %s to usergroups %s - %s', usernames, usergroups, e)
            self.generate_feedback('Error', 'Problems adding users ' + usernames + ' to usergroups ' + usergroups)
            return False

    def do_remove_user_from_usergroup(self, args):
        '''
        DESCRIPTION:
        This command removes an user from
        one/several usergroups

        COMMAND:
        remove_user_to_usergroup [username]
                                 [usergroups]


        [username]
        -----------
        Username to remove

        [usergroups]
        ------------
        Usergroup names from where the username will be removed.  One
        can define several values in a comma separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                username = input('# Username: ').strip()
                usergroups = input('# Usergroups: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 2:

            username = arg_list[0].strip()
            usergroups = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if usergroups == '':
            self.generate_feedback('Error', 'Usergroups value is empty')
            return False

        if username == '':
            self.generate_feedback('Error', 'Username value is empty')
            return False

        user_to_remove = []
        user_to_remove.append(username)

        try:

            for usergroup in usergroups.split(','):

                usergroup = usergroup.strip()
                usernames_list_orig = []
                usernames_list_final = []
                usernameids_list_final = []

                #
                # Get list with users to keep in this  usergroup
                #

                result = self.zapi.usergroup.get(output='extend',
                                                 search={'name': usergroup},
                                                 searchWildcardsEnabled=True,
                                                 sortfield='name',
                                                 sortorder='ASC',
                                                 selectUsers=['alias'])

                for users in result:
                    for alias in users['users']:
                        usernames_list_orig.append(alias['alias'])

                usernames_list_final = list(set(usernames_list_orig) - set(user_to_remove))

                #
                # Update usergroup with the new users list
                #

                usergroupid = self.get_usergroup_id(usergroup)

                for user in usernames_list_final:
                    usernameids_list_final.append(self.get_user_id(user))

                result = self.zapi.usergroup.update(usrgrpid=usergroupid, userids=usernameids_list_final)
                self.generate_feedback('Done', 'User ' + username + ' removed from this usergroup: ' + usergroup)
                logger.info('User: %s removed from this usergroup: %s', username, usergroup)

        except Exception as e:
            logger.error('Problems removing user %s from usergroups %s - %s', username, usergroups, e)
            self.generate_feedback('Error', 'Problems removing user ' + username + ' from usergroups ' + usergroups)
            return False

    def do_link_template_to_host(self, args):
        '''
        DESCRIPTION:
        This command links one/several templates to
        one/several hosts

        COMMAND:
        link_template_to_host [templates]
                              [hostnames]


        [templates]
        ------------
        Template names or IDs.
        One can define several values in a comma separated list.

        [hostnames]
        -----------
        Hostnames or IDs.
        One can define several values in a comma separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                templates = input('# Templates: ').strip()
                hostnames = input('# Hostnames: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 2:

            templates = arg_list[0].strip()
            hostnames = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('ERROR', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if templates == '':
            self.generate_feedback('Error', 'Templates information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error', 'Hostnames information is empty')
            return False

        try:

            #
            # Generate templates and hosts IDs
            #

            templates_list = []
            hostnames_list = []
            template_ids = ''
            host_ids = ''

            for template in templates.split(','):

                if template.isdigit():
                    templates_list.append('{"templateid":"' + str(template).strip() + '"}')
                else:
                    templates_list.append('{"templateid":"' + str(self.get_template_id(template.strip())) + '"}')

            template_ids = ','.join(templates_list)

            for hostname in hostnames.split(','):

                if hostname.isdigit():
                    hostnames_list.append('{"hostid":"' + str(hostname).strip() + '"}')
                else:
                    hostnames_list.append('{"hostid":"' + str(self.get_host_id(hostname.strip())) + '"}')

            host_ids = ','.join(hostnames_list)

            #
            # Generate zabbix query
            #

            query = ast.literal_eval("{\"templates\":[" + template_ids + "],\"hosts\":[" + host_ids + "]}")

            #
            # Link templates to hosts
            #

            self.zapi.template.massadd(**query)
            logger.info('Templates: %s (%s) linked to these hosts: %s (%s)', templates, template_ids, hostnames, host_ids)
            self.generate_feedback('Done', 'Templates ' + templates + ' (' + template_ids + ') linked to these hosts: ' + hostnames + ' (' + host_ids + ')')

        except Exception as e:
            logger.error('Problems linking templates %s (%s) to hosts %s (%s) - %s', templates, template_ids, hostnames, host_ids, e)
            self.generate_feedback('Error', 'Problems linking templates ' + templates + ' (' + template_ids + ') to hosts ' + hostnames + ' (' + host_ids + ')')
            return False

    def do_unlink_template_from_host(self, args):
        '''
        DESCRIPTION:
        This command unlink one/several templates from
        one/several hosts

        COMMAND:
        unlink_template_from_host [templates]
                                  [hostnames]

        [templates]
        ------------
        Templates names or IDs.
        One can define several values in a comma separated list.

        [hostnames]
        -----------
        Hostnames or IDs.
        One can define several values in a comma separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                templates = input('# Templates: ').strip()
                hostnames = input('# Hostnames: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 2:

            templates = arg_list[0].strip()
            hostnames = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if templates == '':
            self.generate_feedback('Error', 'Templates information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error', 'Hostnames information is empty')
            return False

        try:

            #
            # Generate templates and hosts IDs
            #

            templates_list = []
            hostnames_list = []
            template_ids = ''
            host_ids = ''

            for template in templates.split(','):

                if template.isdigit():
                    templates_list.append(str(template).strip())
                else:
                    templates_list.append(str(self.get_template_id(template.strip())))

            template_ids = ','.join(templates_list)

            for hostname in hostnames.split(','):

                if hostname.isdigit():
                    hostnames_list.append(str(hostname).strip())
                else:
                    hostnames_list.append(str(self.get_host_id(hostname.strip())))

            host_ids = ','.join(hostnames_list)

            #
            # Generate zabbix query
            #

            query = ast.literal_eval("{\"hostids\":[" + host_ids + "],\"templateids_clear\":[" + template_ids + "]}")

            #
            # Unlink templates from hosts
            #

            self.zapi.host.massremove(**query)
            logger.info('Templates: %s (%s) unlinked and cleared from these hosts: %s (%s)', templates, template_ids, hostnames, host_ids)
            self.generate_feedback('Done', 'Templates ' + templates + ' (' + template_ids + ') unlinked and cleared from these hosts: ' + hostnames + ' (' + host_ids + ')')

        except Exception as e:
            logger.error('Problems unlinking and clearing templates %s (%s) from hosts %s (%s) - %s', templates, template_ids, hostnames, host_ids, e)
            self.generate_feedback('Error', 'Problems unlinking and clearing templates ' + templates + ' (' + template_ids + ') from hosts ' + hostnames + ' (' + host_ids + ')')
            return False

    def do_create_usergroup(self, args):
        '''
        DESCRIPTION:
        This command creates an usergroup.

        COMMAND:
        create_usergroup [group name]
                         [GUI access]
                         [Status]

        [group name]
        ------------
        Usergroup name

        [GUI access]
        ------------
        0:'System default' [*]
        1:'Internal'
        2:'Disable'

        [Status]
        --------
        0:'Enable' [*]
        1:'Disable'

        '''

        # Default 0: System default
        gui_access_default = '0'

        # Default 0: Enable
        users_status_default = '0'

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                groupname = input('# Name: ').strip()
                gui_access = input('# GUI access [' + gui_access_default + ']: ').strip()
                users_status = input('# Status [' + users_status_default + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 3:

            groupname = arg_list[0].strip()
            gui_access = arg_list[1].strip()
            users_status = arg_list[2].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if gui_access == '' or gui_access not in ('0', '1', '2'):
            gui_access = gui_access_default

        if users_status == '' or users_status not in ('0', '1'):
            users_status = users_status_default

        #
        # Check if usergroup exists
        #

        try:
            result = self.usergroup_exists(groupname)
            logger.debug('Cheking if usergroup (%s) exists', groupname)

        except Exception as e:
            logger.error('Problems checking if usergroup (%s) exists - %s', groupname, e)
            self.generate_feedback('Error', 'Problems checking if usergroup (' + groupname + ') exists')
            return False

        #
        # Create usergroup if it does not exist
        #

        try:
            if result:
                logger.debug('Usergroup (%s) already exists', groupname)
                self.generate_feedback('Warning', 'This usergroup (' + groupname + ') already exists.')
                return False

            else:
                result = self.zapi.usergroup.create(name=groupname,
                                                    gui_access=gui_access,
                                                    users_status=users_status)
                logger.info('Usergroup (%s) with ID: %s created', groupname, str(result['usrgrpids'][0]))
                self.generate_feedback('Done', 'Usergroup (' + groupname + ') with ID: ' + str(result['usrgrpids'][0]) + ' created.')

        except Exception as e:
            logger.error('Problems creating Usergroup (%s) - %s', groupname, e)
            self.generate_feedback('Error', 'Problems creating usergroup (' + groupname + ')')
            return False

    def do_create_host(self, args):
        '''
        DESCRIPTION:
        This command creates a host.

        COMMAND:
        create_host [hostname|IP]
                    [hostgroups]
                    [proxy]
                    [status]

        [hostname|IP]
        -------------
        Hostname or IP

        [hostgroups]
        ------------
        Hostgroup names or IDs. One can define several values in a
        comma separated list.

        Remember that the host will get added to all hostgroups
        defined with the parameter 'default_hostgroup' in the
        zabbix-cli configuration file 'zabbix-cli.conf'

        This command will fail if both 'default_hostgroup' and
        [hostgroups] are empty.

        [proxy]
        -------
        Proxy server used to monitor this host. One can use regular
        expressions to define a group of proxy servers from where the
        system will choose a random proxy.

        If this parameter is not defined, the system will assign a
        random proxy from the list of all available proxies.

        If the system does not have proxy servers defined, the new
        host will be monitor by the Zabbix-server.

        e.g. Some regular expressions that can be used:

        * proxy-(prod|test)+d\\.example\\.org
          e.g. proxy-prod1.example.org and proxy-test8.example.org
               will match this expression.

        * .+
          All proxies will match this expression.

        [Status]
        --------
        0:'Monitored' [*]
        1:'Unmonitored'

        All host created with this command will get assigned a
        default interface of type 'Agent' using the port 10050.

        '''

        # Default hostgroups.
        # Use these values only if they exist.

        hostgroup_default = self.conf.default_hostgroup.strip()

        for hostgroup in self.conf.default_hostgroup.split(','):

            if not self.hostgroup_exists(hostgroup.strip()):
                hostgroup_default = ''
                break

        # Proxy server to use to monitor this host
        proxy_default = '.+'

        # Default 0: Enable
        host_status_default = '0'

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                host = input('# Hostname|IP: ').strip()
                hostgroups = input('# Hostgroups[' + hostgroup_default + ']: ').strip()
                proxy = input('# Proxy [' + proxy_default + ']: ').strip()
                host_status = input('# Status [' + host_status_default + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 4:

            host = arg_list[0].strip()
            hostgroups = arg_list[1].strip()
            proxy = arg_list[2].strip()
            host_status = arg_list[3].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if host == '':
            self.generate_feedback('Error', 'Hostname|IP value is empty')
            return False

        if proxy == '':
            proxy = proxy_default

        if host_status == '' or host_status not in ('0', '1'):
            host_status = host_status_default

        # Generate interface definition. Per default all hosts get a
        # Zabbix agent and a SNMP interface defined

        try:
            # Check if we are using a hostname or an IP
            ipaddress.ip_address(u"{}".format(host))  # Unicodify for python2 compability

            useip = '"useip":1,'
            interface_ip = '"ip":"' + host + '",'
            interface_dns = '"dns":"",'

        except ValueError:
            useip = '"useip":0,'
            interface_ip = '"ip":"",'
            interface_dns = '"dns":"' + host + '",'

        interfaces_def = '"interfaces":[' + \
                         '{"type":1,' + \
                         '"main":1,' + \
                         useip + \
                         interface_ip + \
                         interface_dns + \
                         '"port":"10050"}]'

        #
        # Generate hostgroups and proxy IDs
        #

        try:
            hostgroups_list = []
            hostgroup_ids = ''

            for hostgroup in hostgroup_default.split(','):

                if hostgroup != '':
                    hostgroups_list.append('{"groupid":"' + str(self.get_hostgroup_id(hostgroup.strip())) + '"}')

            for hostgroup in hostgroups.split(','):

                if hostgroup != '':
                    if hostgroup.isdigit():
                        hostgroups_list.append('{"groupid":"' + str(hostgroup).strip() + '"}')
                    else:
                        hostgroups_list.append('{"groupid":"' + str(self.get_hostgroup_id(hostgroup.strip())) + '"}')

            hostgroup_ids = ','.join(set(hostgroups_list))

        except Exception as e:
            logger.error('%s', e)
            self.generate_feedback('Error', e)
            return False

        try:
            proxy_id = str(self.get_random_proxyid(proxy.strip()))
            proxy_hostid = "\"proxy_hostid\":\"" + proxy_id + "\","

        except Exception as e:
            logger.debug('Host [%s] - %s', host, e)
            proxy_hostid = ""

        #
        # Checking if host exists
        #

        try:
            result = self.host_exists(host.strip())
            logger.debug('Cheking if host (%s) exists', host)

        except Exception as e:
            logger.error('Problems checking if host (%s) exists - %s', host, e)
            self.generate_feedback('Error', 'Problems checking if host (' + host + ') exists')
            return False

        try:
            if result:
                logger.debug('Host (%s) already exists', host)
                self.generate_feedback('Warning', 'This host (' + host + ') already exists.')
                return False

            else:

                #
                # Create host via Zabbix-API
                #

                query = ast.literal_eval("{\"host\":\"" + host + "\"," + "\"groups\":[" + hostgroup_ids + "]," + proxy_hostid + "\"status\":" + host_status + "," + interfaces_def + ",\"inventory_mode\":1,\"inventory\":{\"name\":\"" + host + "\"}}")
                result = self.zapi.host.create(**query)
                logger.info('Host (%s) with ID: %s created', host, str(result['hostids'][0]))

                self.generate_feedback('Done', 'Host (' + host + ') with ID: ' + str(result['hostids'][0]) + ' created')

                #
                # Update the hostid cache with the created host.
                #
                self.hostid_cache[result['hostids'][0]] = host

        except Exception as e:
            logger.error('Problems creating host (%s) - %s', host, e)
            self.generate_feedback('Error', 'Problems creating host (' + host + ')')
            return False

    def do_remove_host(self, args):
        '''
        DESCRIPTION:
        This command removes a host.

        COMMAND:
        remove_host [hostname]

        [hostname]
        ----------
        Hostname

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                hostname = input('# Hostname: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 1:

            hostname = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error', 'Hostname value is empty')
            return False

        try:

            #
            # Generate hostnames IDs
            #

            if not hostname.isdigit():
                hostid = str(self.get_host_id(hostname))
            else:
                hostid = str(hostname)

            #
            # Delete host via zabbix-API
            #

            result = self.zapi.host.delete(hostid)
            logger.info('Hosts (%s) with IDs: %s removed', hostname, str(result['hostids'][0]))
            self.generate_feedback('Done', 'Hosts (' + hostname + ') with IDs: ' + str(result['hostids'][0]) + ' removed')

            #
            # Delete the deleted host from the hostid cache if it
            # exists. If a host is created via the zabbix frontend
            # after a zabbix-cli session has been started, the host
            # will not exist in the zabbix-cli cache of this session.
            #

            if hostid in self.hostid_cache.values():
                del self.hostid_cache[hostid]

        except Exception as e:
            logger.error('Problems removing hosts (%s) - %s', hostname, e)
            self.generate_feedback('Error', 'Problems removing hosts (' + hostname + ')')
            return False

    def do_remove_maintenance_definition(self, args):
        '''
        DESCRIPTION:
        This command removes one or several maintenance definitions

        COMMAND:
        remove_maintenance_definitions [definitionID]

        [definitionID]
        --------------
        Definition ID. One can define more than one value in a comma
        separated list.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                maintenanceid = input('# maintenanceID: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 1:

            maintenanceid = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if maintenanceid == '':
            self.generate_feedback('Error', 'MaintenceID value is empty')
            return False

        try:

            #
            # Generate maintenanceIDs list
            #

            maintenances = [int(i) for i in maintenanceid.replace(' ', '').split(',')]

            #
            # Delete maintenances via zabbix-API
            #

            for maintenance in maintenances:
                self.zapi.maintenance.delete(maintenance)

            logger.info('Maintenances defintions with IDs: [%s] removed', maintenanceid.replace(' ', ''))
            self.generate_feedback('Done', 'Maintenance definitions with IDs: [' + maintenanceid.replace(' ', '') + '] removed')

        except Exception as e:
            logger.error('Problems removing maintenance IDs: [%s] - %s', maintenanceid.replace(' ', ''), e)
            self.generate_feedback('Error', 'Problems removing maintenance IDs (' + maintenanceid.replace(' ', '') + ')')
            return False

    def do_create_maintenance_definition(self, args):
        '''
        DESCRIPTION:

        This command creates a 'one time only' maintenance definition
        for a defined period of time. Use the zabbix dashboard for
        more advance definitions.

        COMMAND:
        create_maintenance_definition [name]
                                      [description]
                                      [host/hostgroup]
                                      [time period]
                                      [maintenance type]

        [name]
        ------
        Maintenance definition name.

        [description]
        -------------
        Maintenance definition description

        [host/hostgroup]
        ----------------
        Host/s and/or hostgroup/s the that will undergo
        maintenance.

        One can define more than one value in a comma separated list
        and mix host and hostgroup values.

        [time period]
        -------------
        Time period when the maintenance must come into effect.

        One can define an interval between to timestamps in ISO format
        or a time period in minutes, hours or days from the moment the
        definition is created.

        e.g. From 22:00 until 23:00 on 2016-11-21 -> '2016-11-21T22:00 to 2016-11-21T23:00'
             2 hours from the moment we create the maintenance -> '2 hours'


        [maintenance type]
        ------------------
        Maintenance type.

        Type values:

        0 - (default) With data collection
        1 - Without data collection

        '''

        host_ids = []
        hostgroup_ids = []

        # Default values
        x = hashlib.md5()
        x.update(str(random.randint(1, 1000000)).encode('ascii'))
        tag_default = x.hexdigest()[1:10].upper()

        maintenance_name_default = 'zabbixCLI-' + tag_default
        time_period_default = '1 hour'
        maintenance_type_default = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                maintenance_name = input('# Maintenance name [' + maintenance_name_default + ']: ').strip()
                maintenance_description = input('# Maintenance description []: ').strip()
                host_hostgroup = input('# Host/Hostgroup []: ').strip()
                time_period = input('# Time period [' + time_period_default + ']: ').strip()
                maintenance_type_ = input('# Maintenance type [' + str(maintenance_type_default) + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 5:

            maintenance_name = arg_list[0].strip()
            maintenance_description = arg_list[1].strip()
            host_hostgroup = arg_list[2].strip()
            time_period = arg_list[3].strip()
            maintenance_type_ = arg_list[4].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        try:

            #
            # Sanity check
            #

            if maintenance_name == '':
                maintenance_name = maintenance_name_default

            if host_hostgroup == '':
                self.generate_feedback('Error', 'Maintenance host/hostgroup value is empty')
                return False

            if time_period == '':
                time_period = time_period_default.upper()
            else:
                time_period = time_period.upper()

            if maintenance_type_ == '' or maintenance_type_ not in ('0', '1'):
                maintenance_type_ = maintenance_type_default

            #
            # Generate lists with hostID anf hostgroupID information.
            #

            for value in host_hostgroup.replace(' ', '').split(','):

                if self.host_exists(value):
                    host_ids.append(self.get_host_id(value))

                elif self.hostgroup_exists(value):
                    hostgroup_ids.append(self.get_hostgroup_id(value))

            #
            # Generate since, till and period (in sec) when
            # maintenance period is defined with
            # <ISO timestamp> TO <timestamp>
            #
            # ISO timestamp = %Y-%m-%dT%H:%M
            #

            if 'TO' in time_period:

                from_, to_ = time_period.split('TO')
                since_tmp = datetime.datetime.strptime(from_.strip(), "%Y-%m-%dT%H:%M")
                till_tmp = datetime.datetime.strptime(to_.strip(), "%Y-%m-%dT%H:%M")

                diff = (till_tmp - since_tmp)
                sec = (diff.seconds + diff.days * 24 * 3600)

                # Convert to timestamp

                since = time.mktime(since_tmp.timetuple())
                till = time.mktime(till_tmp.timetuple())

            #
            # Generate since, till and period (in sec) when
            # maintenance period id defined with a time period in
            # minutes, hours or days
            #
            # time period -> 'x minutes', 'y hours', 'z days'
            #

            else:

                if 'SECOND' in time_period:
                    sec = int(time_period.replace(' ', '').replace('SECONDS', '').replace('SECOND', ''))

                elif 'MINUTE' in time_period:
                    sec = int(time_period.replace(' ', '').replace('MINUTES', '').replace('MINUTE', '')) * 60

                elif 'HOUR' in time_period:
                    sec = int(time_period.replace(' ', '').replace('HOURS', '').replace('HOUR', '')) * 60 * 60

                elif 'DAY' in time_period:
                    sec = int(time_period.replace(' ', '').replace('DAYS', '').replace('DAY', '')) * 60 * 60 * 24

                since_tmp = datetime.datetime.now()
                till_tmp = since_tmp + datetime.timedelta(seconds=sec)

                # Convert to timestamp

                since = time.mktime(since_tmp.timetuple())
                till = time.mktime(till_tmp.timetuple())

            #
            # Create maintenance period
            #
            self.zapi.maintenance.create(name=maintenance_name,
                                         maintenance_type=maintenance_type_,
                                         active_since=since,
                                         active_till=till,
                                         description=maintenance_description,
                                         hostids=host_ids,
                                         groupids=hostgroup_ids,
                                         timeperiods=[
                                             {
                                                 'start_date': since,
                                                 'period': sec,
                                                 'timeperiod_type': 0
                                             }
                                         ])

            logger.info('Maintenances definition with name [%s] created', maintenance_name)
            self.generate_feedback('Done', 'Maintenance definition with name [' + maintenance_name + '] created')

        except Exception as e:
            logger.error('Problems creating maintenance definition: [%s] - %s', maintenance_name, e)
            self.generate_feedback('Error', 'Problems creating maintenance definition (' + maintenance_name + ')')
            return False

    def do_create_host_interface(self, args):
        '''
        DESCRIPTION:
        This command creates a hostinterface.

        COMMAND:
        create_host_interface [hostname]
                              [interface connection]
                              [interface type]
                              [interface port]
                              [interface IP]
                              [interface DNS]
                              [default interface]

        [hostname]
        ----------
        Hostname

        [interface connection]
        ----------------------
        0: Connect using host DNS name or interface DNS if provided [*]
        1: Connect using host IP address

        [interface type]
        ----------------
        1: Zabbix agent
        2: SNMP [*]
        3: IPMI
        4: JMX

        [interface port]
        ----------------
        Interface port [161]

        [interface IP]
        --------------
        IP address if interface connection is 1:

        [interface DNS]
        --------------
        DNS if interface connection is 0: (hostname by default)

        [default interface]
        -------------------
        0: Not default interface
        1: Default interface [*]

        '''

        #
        # Default host interface information
        #

        # We use DNS not IP
        interface_ip_default = ''

        # This interface is the 1:default one
        interface_main_default = '1'

        # Port used by the interface
        interface_port_default = '161'

        # Interface type. 2:SNMP
        interface_type_default = '2'

        # Interface connection. 0:DNS
        interface_useip_default = '0'

        # The default DNS will be set to hostname when parsed
        interface_dns_default = ''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                hostname = input('# Hostname: ').strip()
                interface_useip = input('# Interface connection[' + interface_useip_default + ']: ').strip()
                interface_type = input('# Interface type[' + interface_type_default + ']: ').strip()
                interface_port = input('# Interface port[' + interface_port_default + ']: ').strip()
                interface_ip = input('# Interface IP[' + interface_ip_default + ']: ').strip()
                interface_dns = input('# Interface DNS[' + interface_dns_default + ']: ').strip()
                interface_main = input('# Default interface[' + interface_main_default + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

            #
            # Command without filters attributes
            #

        elif len(arg_list) == 7:

            hostname = arg_list[0].strip()
            interface_useip = arg_list[1].strip()
            interface_type = arg_list[2].strip()
            interface_port = arg_list[3].strip()
            interface_ip = arg_list[4].strip()
            interface_dns = arg_list[5].strip()
            interface_main = arg_list[6].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error', 'Hostname value is empty')
            return False

        interface_dns_default = hostname

        if interface_useip == '' or interface_useip not in ('0', '1'):
            interface_useip = interface_useip_default

        if interface_type == '' or interface_type not in ('1', '2', '3', '4'):
            interface_type = interface_type_default

        if interface_port == '':
            interface_port = interface_port_default

        if interface_dns == '':
            interface_dns = interface_dns_default

        if interface_useip == '1' and interface_ip == '':
            self.generate_feedback('Error', 'Host IP value is empty and connection type is 1:IP')
            return False

        if interface_main == '' or interface_main not in ('0', '1'):
            interface_main = interface_main_default

        # Generate interface definition

        if interface_useip == '0':

            interfaces_def = '"type":' + interface_type + \
                ',"main":' + interface_main + \
                ',"useip":' + interface_useip + \
                ',"ip":"' + \
                '","dns":"' + interface_dns + \
                '","port":"' + interface_port + '"'

        elif interface_useip == '1':

            interfaces_def = '"type":' + interface_type + \
                ',"main":' + interface_main + \
                ',"useip":' + interface_useip + \
                ',"ip":"' + interface_ip + \
                '","dns":"' + \
                '","port":"' + interface_port + '"'

        #
        # Checking if hostname exists
        #

        try:
            host_exists = self.host_exists(hostname)
            logger.debug('Cheking if host (%s) exists', hostname)

            if not host_exists:
                logger.error('Host (%s) does not exists. Host Interface can not be created', hostname)
                self.generate_feedback('Error', 'Host (' + hostname + ') does not exists. Host Interface can not be created')
                return False

            else:
                hostid = str(self.get_host_id(hostname))

        except Exception as e:
            logger.error('Problems checking if host (%s) exists - %s', hostname, e)
            self.generate_feedback('Error', 'Problems checking if host (' + hostname + ') exists')
            return False

        #
        # Create host interface if it does not exist
        #

        try:

            query = ast.literal_eval("{\"hostid\":\"" + hostid + "\"," + interfaces_def + "}")
            result = self.zapi.hostinterface.create(**query)
            logger.info('Host interface with ID: %s created on %s', str(result['interfaceids'][0]), hostname)
            self.generate_feedback('Done', 'Host interface with ID: ' + str(result['interfaceids'][0]) + ' created on ' + hostname)

        except Exception as e:
            logger.error('Problems creating host interface on %s- %s', hostname, e)
            self.generate_feedback('Error', 'Problems creating host interface on ' + hostname + '')
            return False

    def do_create_user(self, args):
        '''DESCRIPTION:
        This command creates an user.

        COMMAND:
        create_user [alias]
                    [name]
                    [surname]
                    [passwd]
                    [type]
                    [autologin]
                    [autologout]
                    [groups]

        [alias]
        -------
        User alias (account name)

        [name]
        ------
        Name

        [surname]
        ---------
        Surname

        [passwd]
        --------
        Password.

        The system will generate an automatic password if this value
        is not defined.

        [type]
        ------
        1:'User' [*]
        2:'Admin'
        3:'Super admin'

        [autologin]
        -----------
        0:'Disable' [*]
        1:'Enable'

        [autologout]
        ------------
        In seconds [86400]

        [groups]
        --------
        Usergroup names where this user will be registered.

        One can define several values in a comma separated list.

        '''

        # Default: md5 value of a random int >1 and <1000000
        x = hashlib.md5()
        x.update(str(random.randint(1, 1000000)))
        passwd_default = x.hexdigest()

        # Default: 1: Zabbix user
        type_default = '1'

        # Default: 0: Disable
        autologin_default = '0'

        # Default: 1 day: 86400s
        autologout_default = '86400'

        # Default usergroups
        usergroup_default = self.conf.default_create_user_usergroup.strip()

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                alias = input('# Alias []: ').strip()
                name = input('# Name []: ').strip()
                surname = input('# Surname []: ').strip()
                passwd = input('# Password []: ').strip()
                type = input('# User type [' + type_default + ']: ').strip()
                autologin = input('# Autologin [' + autologin_default + ']: ').strip()
                autologout = input('# Autologout [' + autologout_default + ']: ').strip()
                usrgrps = input('# Usergroups []: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 8:

            alias = arg_list[0].strip()
            name = arg_list[1].strip()
            surname = arg_list[2].strip()
            passwd = arg_list[3].strip()
            type = arg_list[4].strip()
            autologin = arg_list[5].strip()
            autologout = arg_list[6].strip()
            usrgrps = arg_list[7].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if alias == '':
            self.generate_feedback('Error', 'User Alias is empty')
            return False

        if passwd == '':
            passwd = passwd_default

        if type == '' or type not in ('1', '2', '3'):
            type = type_default

        if autologin == '':
            autologin = autologin_default

        if autologout == '':
            autologout = autologout_default

        usergroup_list = []

        try:

            for usrgrp in usergroup_default.split(','):
                if usrgrp != '':
                    usrgrp_id = str(self.get_usergroup_id(usrgrp.strip()))
                    usergroup_list.append({"usrgrpid": usrgrp_id})

            for usrgrp in usrgrps.split(','):
                if usrgrp != '':
                    usrgrp_id = str(self.get_usergroup_id(usrgrp.strip()))
                    usergroup_list.append({"usrgrpid": usrgrp_id})

        except Exception as e:
            logger.error('Problems getting usergroupID - %s', e)
            self.generate_feedback('Error', 'Problems getting usergroupID - ' + str(e))
            return False

        #
        # Check if user exists
        #

        try:
            result = self.zapi.user.get(search={'alias': alias}, output='extend', searchWildcardsEnabled=True)
            logger.debug('Checking if user (%s) exists', alias)

        except Exception as e:
            logger.error('Problems checking if user (%s) exists - %s', alias, e)
            self.generate_feedback('Error', 'Problems checking if user (' + alias + ') exists')
            return False

        #
        # Create user
        #

        try:

            if result != []:
                logger.debug('This user (%s) already exists', alias)
                self.generate_feedback('Warning', 'This user (' + alias + ') already exists.')
                return False
            else:
                result = self.zapi.user.create(alias=alias,
                                               name=name,
                                               surname=surname,
                                               passwd=passwd,
                                               type=type,
                                               autologin=autologin,
                                               autologout=autologout,
                                               usrgrps=usergroup_list)
                logger.info('User (%s) with ID: %s created', alias, str(result['userids'][0]))
                self.generate_feedback('Done', 'User (' + alias + ') with ID: ' + str(result['userids'][0]) + ' created.')

        except Exception as e:
            logger.error('Problems creating user (%s) - %s', alias, e)
            self.generate_feedback('Error', 'Problems creating user (' + alias + ')')
            return False

    def do_create_notification_user(self, args):
        '''DESCRIPTION:

        This command creates a notification user. These users can be
        used to send notifications when a zabbix event happens.

        Sometimes we need to send a notification to a place not owned by any
        user in particular, e.g. an email list or jabber channel but Zabbix has
        not the possibility of defining media for a usergroup.

        This is the reason we use *notification users*. They are users nobody
        owns, but that can be used by other users to send notifications to the
        media defined in the notification user profile.

        Check the parameter **default_notification_users_usergroup** in your
        zabbix-cli configuration file. The usergroup defined here has to
        exists if you want this command to work.


        COMMAND:
        create_notification_user [sendto]
                                 [mediatype]
                                 [remarks]
        [sendto]
        --------
        E-mail address, SMS number, jabber address, ...

        [mediatype]
        -----------
        One of the media types names defined in your Zabbix
        installation, e.g.  Email, SMS, jabber, ...

        [remarks]
        ---------
        Comments about this user. e.g. Operations email.
        Max lenght is 20 characters.

        '''

        # Default: md5 value of a random int >1 and <1000000
        x = hashlib.md5()
        x.update(str(random.randint(1, 1000000)))
        passwd_default = x.hexdigest()

        # Default: 1: Zabbix user
        type_default = '1'

        # Default: 0: Disable
        autologin_default = '0'

        # Default: 1 day: 86400s
        autologout_default = '3600'

        # Default usergroups
        usergroup_default = self.conf.default_create_user_usergroup.strip()
        notifications_usergroup_default = self.conf.default_notification_users_usergroup.strip()

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                sendto = input('# SendTo []: ').strip()
                mediatype = input('# Media type []: ').strip()
                remarks = input('# Remarks []: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 3:

            sendto = arg_list[0].strip()
            mediatype = arg_list[1].strip()
            remarks = arg_list[2].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if sendto == '':
            self.generate_feedback('Error', 'SendTo is empty')
            return False

        if mediatype == '':
            self.generate_feedback('Error', 'Media type is empty')
            return False

        if remarks.strip() == '':
            alias = 'notification-user-' + sendto.replace('.', '-')
        else:
            alias = 'notification-user-' + remarks.strip()[:20].replace(' ', '_') + '-' + sendto.replace('.', '-')

        passwd = passwd_default
        type = type_default
        autologin = autologin_default
        autologout = autologout_default

        usergroup_list = []

        try:

            for usrgrp in usergroup_default.split(','):
                if usrgrp != '':
                    usergroup_list.append(str(self.get_usergroup_id(usrgrp.strip())))

            for usrgrp in notifications_usergroup_default.split(','):
                if usrgrp != '':
                    usergroup_list.append(str(self.get_usergroup_id(usrgrp.strip())))

        except Exception as e:
            logger.error('Problems getting usergroupID - %s', e)
            self.generate_feedback('Error', 'Problems getting usergroupID - ' + str(e))
            return False

        #
        # Check if user exists
        #

        try:
            result1 = self.zapi.user.get(search={'alias': alias}, output='extend', searchWildcardsEnabled=True)
            logger.debug('Checking if user (%s) exists', alias)

        except Exception as e:
            logger.error('Problems checking if user (%s) exists - %s', alias, e)
            self.generate_feedback('Error', 'Problems checking if user (' + alias + ') exists')
            return False

        #
        # Check media type exists
        #

        try:
            result2 = self.zapi.mediatype.get(search={'description': mediatype}, output='extend', searchWildcardsEnabled=True)
            logger.debug('Checking if media type (%s) exists', mediatype)

        except Exception as e:
            logger.error('Problems checking if media type (%s) exists - %s', mediatype, e)
            self.generate_feedback('Error', 'Problems checking if media type (' + mediatype + ') exists')
            return False

        #
        # Create user
        #

        try:

            if result1 != []:
                logger.debug('This user (%s) already exists', alias)
                self.generate_feedback('Warning', 'This user (' + alias + ') already exists.')
                return False

            elif result2 == []:
                logger.debug('This media type (%s) does not exist', mediatype)
                self.generate_feedback('Warning', 'This media type (' + mediatype + ') does not exist.')
                return False

            else:
                usergroup_objects = []
                for usergroup in usergroup_list:
                    usergroup_objects.append({"usrgrpid": usergroup})
                result = self.zapi.user.create(alias=alias,
                                               passwd=passwd,
                                               type=type,
                                               autologin=autologin,
                                               autologout=autologout,
                                               usrgrps=usergroup_objects,
                                               user_medias=[
                                                   {
                                                       'mediatypeid': result2[0]['mediatypeid'],
                                                       'sendto':sendto,
                                                       'active':0,
                                                       'severity':63,
                                                       'period':'1-7,00:00-24:00'
                                                   }
                                               ]
                                               )

                logger.info('User (%s) with ID: %s created', alias, str(result['userids'][0]))
                self.generate_feedback('Done', 'User (' + alias + ') with ID: ' + str(result['userids'][0]) + ' created.')

        except Exception as e:
            logger.error('Problems creating user (%s) - %s', alias, e)
            self.generate_feedback('Error', 'Problems creating user (' + alias + ')')
            return False

    def do_remove_user(self, args):
        '''
        DESCRIPTION:
        This command removes an user.

        COMMAND:
        remove_user [username]

        [username]
        ----------
        Username to remove

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print('--------------------------------------------------------')
                username = input('# Username: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 1:

            username = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if username == '':
            self.generate_feedback('Error', 'Username value is empty')
            return False

        try:

            if not username.isdigit():
                userid = str(self.get_user_id(username))
            else:
                userid = str(username)

            result = self.zapi.user.delete(userid)

            logger.info('User (%s) with IDs: %s removed', username, str(result['userids'][0]))
            self.generate_feedback('Done', 'User (' + username + ') with IDs: ' + str(result['userids'][0]) + ' removed')

        except Exception as e:
            logger.error('Problems removing username (%s) - %s', username, e)
            self.generate_feedback('Error', 'Problems removing username (' + username + ')')
            return False

    def do_create_hostgroup(self, args):
        '''
        DESCRIPTION:
        This command creates a hostgroup

        COMMAND:
        create_hostgroup [hostgroup]

        '''

        # Default values
        admin_usergroup_default = self.conf.default_admin_usergroup
        all_usergroup_default = self.conf.default_create_user_usergroup.strip()

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                hostgroup = input('# Name: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 1:
            hostgroup = arg_list[0].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroup == '':
            self.generate_feedback('Error', 'Hostgroup value is empty')
            return False

        #
        # Checking if hostgroup exists
        #

        try:
            result = self.hostgroup_exists(hostgroup.strip())
            logger.debug('Checking if hostgroup (%s) exists', hostgroup)

        except Exception as e:
            logger.error('Problems checking if hostgroup (%s) exists - %s', hostgroup, e)
            self.generate_feedback('Error', 'Problems checking if hostgroup (' + hostgroup + ') exists')
            return False

        try:

            #
            # Create hostgroup if it does not exist
            #

            if not result:
                data = self.zapi.hostgroup.create(name=hostgroup)
                hostgroupid = data['groupids'][0]
                logger.info('Hostgroup (%s) with ID: %s created', hostgroup, hostgroupid)

                #
                # Give RW access to the new hostgroup to the default admin usergroup
                # defined in zabbix-cli.conf
                #
                # Give RO access to the new hostgroup to the default all usergroup
                # defined in zabbix-cli.conf
                #

                try:

                    for group in admin_usergroup_default.strip().split(','):
                        usrgrpid = self.get_usergroup_id(group)
                        result = zabbix_cli.apiutils.update_usergroup(self.zapi, usrgrpid, rights=[{'id': hostgroupid, 'permission': 3}])
                        logger.info('Admin usergroup (%s) has got RW permissions on hostgroup (%s) ', group, hostgroup)

                    for group in all_usergroup_default.strip().split(','):
                        usrgrpid = self.get_usergroup_id(group)
                        result = zabbix_cli.apiutils.update_usergroup(self.zapi, usrgrpid, rights=[{'id': hostgroupid, 'permission': 2}])
                        logger.info('All users usergroup (%s) has got RO permissions on hostgroup (%s) ', group, hostgroup)

                except Exception as e:
                    logger.error('Problems giving the admin usergroup %s RW access to %s - %s', admin_usergroup_default, hostgroup, e)
                    self.generate_feedback('Error', 'Problems giving the admin usergroup ' + admin_usergroup_default + ' RW access to ' + hostgroup)
                    return False

                self.generate_feedback('Done', 'Hostgroup (' + hostgroup + ') with ID: ' + hostgroupid + ' created.')

            else:
                logger.debug('This hostgroup (%s) already exists', hostgroup)
                self.generate_feedback('Warning', 'This hostgroup (' + hostgroup + ') already exists.')
                return False

        except Exception as e:
            logger.error('Problems creating hostgroup (%s) - %s', hostgroup, e)
            self.generate_feedback('Error', 'Problems creating hostgroup (' + hostgroup + ')')
            return False

    def do_add_usergroup_permissions(self, args):
        '''
        DESCRIPTION:
        This command adds a permission for an usergroup
        on a hostgroup.

        If the usergroup already have permissions on the hostgroup,
        nothing will be changed.

        COMMAND:
        define_usergroup_permissions [usergroup]
                                     [hostgroups]
                                     [permission code]

        [usergroup]
        -----------
        Usergroup that will get a permission on a hostgroup

        [hostgroups]
        ------------
        Hostgroup names where the permission will apply.

        One can define several values in a comma separated list.

        [permission]
        ------------
        * deny: Deny [usergroup] all access to [hostgroups]
        * ro: Give [usergroup] read access to [hostgroups]
        * rw: Give [usergroup] read and write access to [hostgroups]

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                usergroup = input('# Usergroup: ').strip()
                hostgroups = input('# Hostgroup: ').strip()
                permission = input('# Permission: ').strip().lower()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 3:

            usergroup = arg_list[0].strip()
            hostgroups = arg_list[1].strip()
            permission = arg_list[2].strip().lower()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if usergroup == '':
            self.generate_feedback('Error', 'Usergroup value is empty')
            return False

        if hostgroups == '':
            self.generate_feedback('Error', 'Hostgroups value is empty')
            return False

        if permission not in ('deny', 'ro', 'rw'):
            self.generate_feedback('Error', 'Permission value is not valid')
            return False

        #
        # Define access permissions to the hostgroups
        #

        try:

            usrgrpid = self.get_usergroup_id(usergroup)
            permission_code = zabbix_cli.utils.get_permission_code(permission)

            for group in hostgroups.split(','):
                hostgroupid = self.get_hostgroup_id(group)
                zabbix_cli.apiutils.update_usergroup(self.zapi, usrgrpid, rights=[{'id': hostgroupid, 'permission': permission_code}])
                logger.info('Usergroup [%s] has got [%s] permission on hostgroup [%s] ', usergroup, permission, group)
                self.generate_feedback('Done', 'Usergroup [' + usergroup + '] has got [' + permission + '] permission on hostgroup [' + group + ']')

        except Exception as e:
            logger.error('Problems giving the usergroup [%s] [%s] access to the hostgroup [%s] - %s', usergroup, permission, hostgroups, e)
            self.generate_feedback('Error', 'Problems giving the usergroup [' + usergroup + '] [' + permission + '] access to the hostgroup [' + hostgroups + ']')
            return False

    def do_update_usergroup_permissions(self, args):
        '''
        DESCRIPTION:
        This command updates the permissions for an usergroup
        on a hostgroup.

        COMMAND:
        define_usergroup_permissions [usergroup]
                                     [hostgroups]
                                     [permission code]

        [usergroup]
        -----------
        Usergroup that will get a permission on a hostgroup

        [hostgroups]
        ------------
        Hostgroup names where the permission will apply.

        One can define several values in a comma separated list.

        [permission]
        ------------
        * deny: Deny [usergroup] all access to [hostgroups]
        * ro: Give [usergroup] read access to [hostgroups]
        * rw: Give [usergroup] read and write access to [hostgroups]

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                usergroup = input('# Usergroup: ').strip()
                hostgroups = input('# Hostgroup: ').strip()
                permission = input('# Permission: ').strip().lower()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 3:

            usergroup = arg_list[0].strip()
            hostgroups = arg_list[1].strip()
            permission = arg_list[2].strip().lower()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if usergroup == '':
            self.generate_feedback('Error', 'Usergroup value is empty')
            return False

        if hostgroups == '':
            self.generate_feedback('Error', 'Hostgroups value is empty')
            return False

        if permission not in ('deny', 'ro', 'rw'):
            self.generate_feedback('Error', 'Permission value is not valid')
            return False

        #
        # Define access permissions to the hostgroups
        #

        try:

            usrgrpid = self.get_usergroup_id(usergroup)
            permission_code = zabbix_cli.utils.get_permission_code(permission)

            for group in hostgroups.split(','):
                hostgroupid = self.get_hostgroup_id(group)
                zabbix_cli.apiutils.update_usergroup(self.zapi, usrgrpid, rights=[{'id': hostgroupid, 'permission': permission_code}])
                logger.info('Usergroup [%s] has got [%s] permission on hostgroup [%s] ', usergroup, permission, group)
                self.generate_feedback('Done', 'Usergroup [' + usergroup + '] has got [' + permission + '] permission on hostgroup [' + group + ']')

        except Exception as e:
            logger.error('Problems giving the usergroup [%s] [%s] access to the hostgroup [%s] - %s', usergroup, permission, hostgroups, e)
            self.generate_feedback('Error', 'Problems giving the usergroup [' + usergroup + '] [' + permission + '] access to the hostgroup [' + hostgroups + ']')
            return False

    def do_define_global_macro(self, args):
        '''
        DESCRIPTION:
        This command defines a global Zabbix macro

        COMMAND:
        define_global_macro [macro name]
                            [macro value]

        [macro name]
        ------------
        Name of the zabbix macro. The system will format this value to
        use the macro format definition needed by Zabbix.
        e.g. site_url will be converted to ${SITE_URL}

        [macro value]
        -------------
        Default value of the macro

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                global_macro_name = input('# Global macro name: ').strip()
                global_macro_value = input('# Global macro value: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            global_macro_name = arg_list[0].strip()
            global_macro_value = arg_list[1].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if global_macro_name == '':
            self.generate_feedback('Error', 'Global macro name is empty')
            return False

        else:
            global_macro_name = '{$' + global_macro_name.upper() + '}'

        if global_macro_value == '':
            self.generate_feedback('Error', 'Global macro value is empty')
            return False

        #
        # Checking if global macro exists
        #

        try:
            result = self.zapi.usermacro.get(search={'macro': global_macro_name},
                                             globalmacro=True,
                                             output='extend')
            logger.debug('Cheking if global macro (%s) exists', global_macro_name)

        except Exception as e:
            logger.error('Problems checking if global macro (%s) exists - %s', global_macro_name, e)
            self.generate_feedback('Error', 'Problems checking if global macro (' + global_macro_name + ') exists')
            return False

        try:
            if result == []:

                #
                # Create global macro if it does not exist
                #

                data = self.zapi.usermacro.createglobal(macro=global_macro_name, value=global_macro_value)
                globalmacroid = data['globalmacroids'][0]
                logger.info('Global macro (%s) with ID: %s created', global_macro_name, globalmacroid)
                self.generate_feedback('Done', 'Global macro (' + global_macro_name + ') with ID: ' + globalmacroid + ' created.')

            else:

                #
                # Update global macro if it does exist
                #

                data = self.zapi.usermacro.updateglobal(globalmacroid=result[0]['globalmacroid'],
                                                        value=global_macro_value)

                logger.info('Global macro (%s) already exists. Value (%s) updated to (%s)', global_macro_name, result[0]['value'], global_macro_value)
                self.generate_feedback('Done', 'Global macro (' + global_macro_name + ') already exists. Value (' + result[0]['value'] + ') updated to (' + global_macro_value + ')')
                return False

        except Exception as e:
            logger.error('Problems defining global macro (%s) - %s', global_macro_name, e)
            self.generate_feedback('Error', 'Problems defining global macro (' + global_macro_name + ')')
            return False

    def do_define_host_usermacro(self, args):
        '''
        DESCRIPTION:
        This command defines a host usermacro

        COMMAND:
        defines_host_usermacro [hostname]
                               [macro name]
                               [macro value]


        [hostname]
        ----------
        Hostname that will get the usermacro locally defined.

        [macro name]
        ------------
        Name of the zabbix macro. The system will format this value to
        use the macro format definition needed by Zabbix.
        e.g. site_url will be converted to ${SITE_URL}

        [macro value]
        -------------
        Default value of the macro

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                hostname = input('# Hostname: ').strip()
                host_macro_name = input('# Macro name: ').strip()
                host_macro_value = input('# Macro value: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 3:
            hostname = arg_list[0].strip()
            host_macro_name = arg_list[1].strip()
            host_macro_value = arg_list[2].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if host_macro_name == '':
            self.generate_feedback('Error', 'Host macro name is empty')
            return False

        else:
            host_macro_name = '{$' + host_macro_name.upper() + '}'

        if host_macro_value == '':
            self.generate_feedback('Error', 'Host macro value is empty')
            return False

        if hostname == '':
            self.generate_feedback('Error', 'Hostname is empty')
            return False

        if hostname.isdigit():
            hostid = hostname
        else:
            try:
                hostid = self.get_host_id(hostname.strip())

            except Exception:
                logger.info('Hostname %s does not exist', hostname)
                self.generate_feedback('Error', 'Hostname ' + hostname + ' does not exist')
                return False

        #
        # Checking if host macro exists
        #

        try:
            result = self.zapi.usermacro.get(search={'macro': host_macro_name},
                                             hostids=hostid,
                                             output='extend')
            logger.debug('Cheking if host macro (%s:%s) exists', hostname, host_macro_name)

        except Exception as e:
            logger.error('Problems checking if host macro (%s:%s) exists - %s', hostname, host_macro_name, e)
            self.generate_feedback('Error', 'Problems checking if host macro (' + hostname + ':' + host_macro_name + ') exists')
            return False

        try:

            if result == []:

                #
                # Create host macro if it does not exist
                #

                data = self.zapi.usermacro.create(hostid=hostid,
                                                  macro=host_macro_name,
                                                  value=host_macro_value)
                hostmacroid = data['hostmacroids'][0]

                logger.info('Host macro (%s:%s) with ID: %s created', hostname, host_macro_name, hostmacroid)
                self.generate_feedback('Done', 'Host macro (' + hostname + ':' + host_macro_name + ') with ID: ' + hostmacroid + ' created.')

            else:

                #
                # Update host macro if it does exist
                #

                data = self.zapi.usermacro.update(hostmacroid=result[0]['hostmacroid'],
                                                  value=host_macro_value)

                logger.info('Host macro (%s:%s) already exists. Value (%s) updated to (%s)', hostname, host_macro_name, result[0]['value'], host_macro_value)
                self.generate_feedback('Done', 'Host macro (' + hostname + ':' + host_macro_name + ') already exists. Value (' + result[0]['value'] + ') updated to (' + host_macro_value + ')')
                return False

        except Exception as e:
            logger.error('Problems defining host macro (%s:%s) - %s', hostname, host_macro_name, e)
            self.generate_feedback('Error', 'Problems defining host macro (' + hostname + ':' + host_macro_name + ')')
            return False

    def do_define_host_monitoring_status(self, args):
        '''
        DESCRIPTION:
        This command defines the monitoring status of a host

        COMMAND:
        defines_host_monitoring_status [hostname]
                                       [on/off]

        [hostname]
        ----------
        Hostname that will get the monitoring status updated.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                hostname = input('# Hostname: ').strip()
                monitoring_status = input('# Monitoring status[ON|OFF]: ').strip().lower()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            hostname = arg_list[0].strip().lower()
            monitoring_status = arg_list[1].strip().lower()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if monitoring_status == '' or monitoring_status not in ('on', 'off'):
            self.generate_feedback('Error', 'Monitoring status value is not valid')
            return False

        else:
            if monitoring_status == 'on':
                monitoring_status = 0
            elif monitoring_status == 'off':
                monitoring_status = 1

        if hostname == '':
            self.generate_feedback('Error', 'Hostname is empty')
            return False

        #
        # Checking if host exists
        #

        try:
            result = self.host_exists(hostname)
            logger.debug('Cheking if host (%s) exists', hostname,)

        except Exception as e:
            logger.error('Problems checking if host (%s) exists - %s', hostname, e)
            self.generate_feedback('Error', 'Problems checking if host (' + hostname + ') exists')
            return False

        try:
            if result:

                #
                # Update host monitoring status
                #

                hostid = self.get_host_id(hostname.strip())

                self.zapi.host.update(hostid=hostid,
                                      status=monitoring_status)

                logger.info('Monitoring status for hostname (%s) changed to (%s)', hostname, monitoring_status)
                self.generate_feedback('Done', 'Monitoring status for hostname (' + hostname + ') changed to (' + str(monitoring_status) + ')')

            else:
                logger.debug('Hostname (%s) does not exist', hostname)
                self.generate_feedback('Done', 'Hostname (' + hostname + ') does not exist')
                return False

        except Exception as e:
            logger.error('Problems updating monitoring status for hostname (%s) - %s', hostname, e)
            self.generate_feedback('Error', 'Problems updating monitoring status for hostname (' + hostname + ')')
            return False

    def do_update_host_proxy(self, args):
        '''
        DESCRIPTION:
        This command defines the proxy used to monitor a host

        COMMAND:
        update_host_proxy [hostname]
                          [proxy]

        [hostname]
        ----------
        Hostname to update

        [proxy]
        -------
        Zabbix proxy server that will monitor [hostname]

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                hostname = input('# Hostname: ').strip()
                proxy = input('# Proxy: ').strip().lower()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            hostname = arg_list[0].strip()
            proxy = arg_list[1].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error', 'Hostname is empty')
            return False

        if hostname.isdigit():
            hostid = hostname
        else:
            try:
                hostid = self.get_host_id(hostname.strip())

            except Exception:
                logger.error('Hostname %s does not exist', hostname)
                self.generate_feedback('Error', 'Hostname ' + hostname + ' does not exist')
                return False

        try:
            proxy_id = self.get_proxy_id(proxy)

        except Exception:
            logger.error('Proxy %s does not exist', proxy)
            self.generate_feedback('Error', 'Proxy ' + proxy + ' does not exist')
            return False

        #
        # Checking if host exists
        #

        try:
            result = self.host_exists(hostname)
            logger.debug('Cheking if host (%s) exists', hostname,)

        except Exception as e:
            logger.error('Problems checking if host (%s) exists - %s', hostname, e)
            self.generate_feedback('Error', 'Problems checking if host (' + hostname + ') exists')
            return False

        try:
            if result:

                #
                # Update proxy used to monitor the host
                #

                self.zapi.host.update(hostid=hostid,
                                      proxy_hostid=proxy_id)

                logger.info('Proxy for hostname (%s) changed to (%s)', hostname, proxy)
                self.generate_feedback('Done', 'Proxy for hostname (' + hostname + ') changed to (' + str(proxy) + ')')

            else:
                logger.debug('Hostname (%s) does not exist', hostname)
                self.generate_feedback('Done', 'Hostname (' + hostname + ') does not exist')
                return False

        except Exception as e:
            logger.error('Problems updating proxy for hostname (%s) - %s', hostname, e)
            self.generate_feedback('Error', 'Problems updating proxy for hostname (' + hostname + ')')
            return False

    def do_acknowledge_event(self, args):
        '''
        DESCRIPTION:
        This command acknowledges an event

        COMMAND:
        acknowledge_events [eventIDs]
                           [message]

        [eventIDs]
        ----------
        IDs of the events to acknowledge. One can define several
        values in a comma separated list.

        [message]
        ---------
        Text of the acknowledgement message.
        '''

        ack_message_default = '[Zabbix-CLI] Acknowledged via acknowledge_events'

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                event_ids = input('# EventIDs: ').strip()
                ack_message = input('# Message[' + ack_message_default + ']:').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            event_ids = arg_list[0].strip()
            ack_message = arg_list[1].strip()
        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        # Hotfix for Zabbix 4.0 compability
        api_version = distutils.version.StrictVersion(self.zapi.api_version())
        if api_version >= distutils.version.StrictVersion("4.0"):
            action = 6  # "Add message" and "Acknowledge"
        else:
            action = None  # Zabbix pre 4.0 does not have action

        #
        # Sanity check
        #

        if ack_message == '':
            ack_message = ack_message_default

        event_ids = event_ids.replace(' ', '').split(',')

        try:
            self.zapi.event.acknowledge(eventids=event_ids,
                                        message=ack_message,
                                        action=action)

            logger.info('Acknowledge message [%s] for eventID [%s] registered', ack_message, event_ids)
            self.generate_feedback('Done', 'Acknowledge message [' + ack_message + '] for eventID [' + ','.join(event_ids) + '] registered')

        except Exception as e:
            logger.error('Problems registering the acknowledge message [%s] for eventID [%s] - %s', ack_message, event_ids, e)
            self.generate_feedback('Error', 'Problems registering the acknowledge message [' + ack_message + '] for eventID [' + ','.join(event_ids) + ']')
            return False

    def do_acknowledge_trigger_last_event(self, args):
        '''
        DESCRIPTION:

        This command acknowledges the last event of a trigger.

        COMMAND:
        acknowledge_trigger_last_event [triggerIDs]
                                       [message]

        [triggerIDs]
        ------------
        IDs of the triggers to acknowledge. One can define several
        values in a comma separated list.

        [message]
        ---------
        Text of the acknowledgement message.

        '''

        event_ids = []
        ack_message_default = '[Zabbix-CLI] Acknowledged via acknowledge_trigger_last_event'

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                trigger_ids = input('# TriggerIDs: ').strip()
                ack_message = input('# Message[' + ack_message_default + ']:').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            trigger_ids = arg_list[0].strip()
            ack_message = arg_list[1].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if ack_message == '':
            ack_message = ack_message_default

        trigger_ids = trigger_ids.replace(' ', '').split(',')

        try:

            for trigger_id in trigger_ids:
                data = self.zapi.event.get(objectids=trigger_id, sortfield=['clock'], sortorder='DESC', limit=1)
                event_ids.append(data[0]['eventid'])

            # Hotfix for Zabbix 4.0 compability
            api_version = distutils.version.StrictVersion(self.zapi.api_version())
            if api_version >= distutils.version.StrictVersion("4.0"):
                action = 6  # "Add message" and "Acknowledge"
            else:
                action = None  # Zabbix pre 4.0 does not have action

            self.zapi.event.acknowledge(eventids=event_ids,
                                        message=ack_message,
                                        action=action)

            logger.info('Acknowledge message [%s] for last eventIDs [%s] on triggerIDs [%s] registered', ack_message, ','.join(event_ids), ','.join(trigger_ids))
            self.generate_feedback('Done', 'Acknowledge message [' + ack_message + '] for last eventIDs [' + ','.join(event_ids) + '] on triggerIDs [' + ','.join(trigger_ids) + '] registered')

        except Exception as e:
            logger.error('Problems registering acknowledge message [%s] for last eventIDs [%s] on triggerIDs [%s] - %s',
                         ack_message,
                         ','.join(event_ids),
                         ','.join(trigger_ids),
                         e)
            self.generate_feedback('Error', 'Problems registering acknowledge message [' + ack_message + '] for last eventIDs [' + ','.join(event_ids) + '] on triggerIDs [' + ','.join(trigger_ids) + ']')
            return False

    def do_show_trigger_events(self, args):
        '''
        DESCRIPTION:

        This command shows the events generated by a trigger.

        COMMAND:
        show_trigger_events [triggerID]
                            [count]

        [triggerID]
        ------------
        ID of the trigger we want tho show.

        [count]
        ---------
        Number of events to show (Default: 1)

        '''

        result_columns = {}
        result_columns_key = 0

        events_count_default = 1

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                trigger_id = input('# TriggerIDs: ').strip()
                events_count = input('# Events count[' + str(events_count_default) + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            trigger_id = arg_list[0].strip()
            events_count = arg_list[1].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if events_count == '':
            events_count = events_count_default

        try:

            result = self.zapi.event.get(objectids=trigger_id,
                                         sortfield=['clock'],
                                         sortorder='DESC',
                                         limit=events_count,
                                         output='extend')

        except Exception as e:
            logger.error('Problems getting events for triggerID [%s] - %s', str(trigger_id), e)
            self.generate_feedback('Error', 'Problems getting events for triggerID [' + str(trigger_id) + ']')
            return False

        #
        # Get the columns we want to show from result
        #
        for event in result:

            clock = datetime.datetime.fromtimestamp(int(event['clock']))
            age = datetime.datetime.now() - clock

            if self.output_format == 'json':

                result_columns[result_columns_key] = {'eventid': event['eventid'],
                                                      'triggerid': event['objectid'],
                                                      'clock': str(clock),
                                                      'age': str(age),
                                                      'acknowledged': zabbix_cli.utils.get_ack_status(int(event['acknowledged'])),
                                                      'value': zabbix_cli.utils.get_event_status(int(event['value']))}

            else:

                result_columns[result_columns_key] = {'1': event['eventid'],
                                                      '2': event['objectid'],
                                                      '3': str(clock),
                                                      '4': str(age),
                                                      '5': zabbix_cli.utils.get_ack_status(int(event['acknowledged'])),
                                                      '6': zabbix_cli.utils.get_event_status(int(event['value']))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['EventID', 'TriggerID', 'Last change', 'Age', 'Acknowledged', 'Status'],
                             ['Last change', 'Age'],
                             ['EventID', 'TriggerID'],
                             FRAME)

    def do_show_templates(self, args):
        '''
        DESCRIPTION:
        This command shows all templates defined in the system.

        COMMAND:
        show_templates
        '''

        cmd.Cmd.onecmd(self, 'show_template "*"')

    def do_show_template(self, args):
        '''
        DESCRITION
        This command show templates information

        COMMAND:
        show_template [Template name]

        [Template name]:
        ----------------
        One can search by template name. We can use wildcards.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                template = input('# Template: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            template = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if template == '':
            self.generate_feedback('Error', 'Template value is empty')
            return False

        #
        # Get template
        #

        try:
            result = self.zapi.template.get(output='extend',
                                            search={'host': template},
                                            searchWildcardsEnabled=True,
                                            sortfield='host',
                                            selectHosts=['host'],
                                            selectTemplates=['host'],
                                            sortorder='ASC')

        except Exception as e:
            logger.error('Problems getting the template list - %s', e)
            self.generate_feedback('Error', 'Problems getting the template list')
            return False

        #
        # Get the columns we want to show from result
        #

        for template in result:

            if self.output_format == 'json':
                result_columns[result_columns_key] = {'templateid': template['templateid'],
                                                      'name': template['host'],
                                                      'hosts': template['hosts'],
                                                      'templates': template['templates']}

            else:

                host_list = []
                for host in template['hosts']:
                    host_list.append(host['host'])

                host_list.sort()

                template_list = []
                for tpl in template['templates']:
                    template_list.append(tpl['host'])

                template_list.sort()

                result_columns[result_columns_key] = {'1': template['templateid'],
                                                      '2': template['host'],
                                                      '3': '\n'.join(host_list),
                                                      '4': '\n'.join(template_list)}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['TemplateID', 'Name', 'Hosts','Templates'],
                             ['Name', 'Hosts','Templates'],
                             ['TemplateID'],
                             ALL)

    def do_show_global_macros(self, args):
        '''
        DESCRITION:
        This command shows all global macros

        COMMAND:
        show global_macros
        '''

        result_columns = {}
        result_columns_key = 0

        try:
            result = self.zapi.usermacro.get(output='extend',
                                             globalmacro=True,
                                             sortfield='macro',
                                             sortorder='ASC')

        except Exception as e:
            logger.error('Problems getting globalmacros list - %s', e)
            self.generate_feedback('Error', 'Problems getting globalmacros list')
            return False

        #
        # Get the columns we want to show from result
        #

        for global_macro in result:

            if self.output_format == 'json':
                result_columns[result_columns_key] = {'globalmacroid': global_macro['globalmacroid'],
                                                      'name': global_macro['macro'],
                                                      'value': global_macro['value']}

            else:
                result_columns[result_columns_key] = {'1': global_macro['globalmacroid'],
                                                      '2': global_macro['macro'],
                                                      '3': global_macro['value']}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['MacroID', 'Name', 'Value'],
                             ['Name', 'Value'],
                             ['MacroID'],
                             FRAME)

    def do_show_host_usermacros(self, args):
        '''
        DESCRITION:
        This command shows all usermacros for a host

        COMMAND:
        show_host_usermacros [hostname]

        [hostname]
        ----------
        Hostname

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                hostname = input('# Hostname: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 1:
            hostname = arg_list[0].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error', 'Hostname is empty')
            return False

        if hostname.isdigit():
            hostid = hostname
        else:
            try:
                hostid = self.get_host_id(hostname.strip())

            except Exception:
                logger.info('Hostname %s does not exist', hostname)
                self.generate_feedback('Error', 'Hostname ' + hostname + ' does not exist')
                return False

        #
        # Get host macros
        #

        try:
            result = self.zapi.usermacro.get(output='extend',
                                             hostids=hostid,
                                             sortfield='macro',
                                             sortorder='ASC')

        except Exception as e:
            logger.error('Problems getting globalmacros list - %s', e)
            self.generate_feedback('Error', 'Problems getting globalmacros list')
            return False

        #
        # Get the columns we want to show from result
        #

        for host_macro in result:

            if self.output_format == 'json':
                result_columns[result_columns_key] = {'hostmacroid': host_macro['hostmacroid'],
                                                      'name': host_macro['macro'],
                                                      'value': host_macro['value']}

            else:
                result_columns[result_columns_key] = {'1': host_macro['hostmacroid'],
                                                      '2': host_macro['macro'],
                                                      '3': host_macro['value']}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['MacroID', 'Name', 'Value'],
                             ['Name', 'Value'],
                             ['MacroID'],
                             FRAME)

    def do_show_usermacro_host_list(self, args):
        '''
        DESCRITION:
        This command shows all host with a defined usermacro

        COMMAND:
        show_usermacro_host_list [usermacro]

        [usermacro]
        -----------
        Usermacro name. The system will format this value to use the
        macro format definition needed by Zabbix.  e.g. site_url will be
        converted to ${SITE_URL}

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                host_macro_name = input('# Host macro name: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 1:
            host_macro_name = arg_list[0].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if host_macro_name == '':
            self.generate_feedback('Error', 'Host macro name is empty')
            return False

        else:
            host_macro_name = '{$' + host_macro_name.upper() + '}'

        #
        # Get macro hostlist
        #

        try:
            result = self.zapi.usermacro.get(output='extend',
                                             selectHosts=['host'],
                                             search={'macro': host_macro_name},
                                             searchWildcardsEnabled=True,
                                             sortfield='macro')

        except Exception as e:
            logger.error('Problems getting host list for macro %s - %s', host_macro_name, e)
            self.generate_feedback('Error', 'Problems getting host list for macro ' + host_macro_name)
            return False

        #
        # Get the columns we want to show from result
        #

        for macro in result:

            if len(macro['hosts']) > 0:

                if self.output_format == 'json':
                    result_columns[result_columns_key] = {'macro': macro['macro'],
                                                          'value': macro['value'],
                                                          'hostid': macro['hosts'][0]['hostid'],
                                                          'host': macro['hosts'][0]['host']}

                else:

                    result_columns[result_columns_key] = {'1': macro['macro'],
                                                          '2': macro['value'],
                                                          '3': macro['hosts'][0]['hostid'],
                                                          '4': macro['hosts'][0]['host']}

                result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Macro', 'Value', 'HostID', 'Host'],
                             ['Macro', 'Value', 'Host'],
                             ['HostID'],
                             FRAME)

    def do_show_last_values(self, args):
        '''
        DESCRIPTION:
        Shows the last values of given item.

        COMMAND:
        show_last_values [item_name]
                         [group]

        [item_name]
        ----------
        Name of the items to get. Supports wildcard.

        [group]
        Whether the output should group items with the same values.

        0 - (default) Do not group items.
        1 - Group items.
        '''

        try:
            arg_list = [arg.strip() for arg in shlex.split(args)]
        except ValueError as e:
            print('\n[ERROR]: ', e, '\n')
            return False

        if len(arg_list) == 1:
            item_name = arg_list[0]
            group = '0'
        elif len(arg_list) == 2:
            item_name = arg_list[0]
            group = arg_list[1]
            if group not in ('1', '0'):
                group = '0'
        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if item_name == '':
            self.generate_feedback('Error', 'Item name is empty')
            return False

        #
        # Getting items
        #
        try:
            result = self.zapi.item.get(output='extend', monitored=True, search={'name': item_name}, searchWildcardsEnabled=True, sortfield='name', sortorder='ASC')
        except Exception as e:
            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting items - %s', e)

            self.generate_feedback('Error', 'Problems getting items')

            return False

        #
        # Get the columns we want to show from result
        #

        if group == '0':
            result_columns = {}
            result_columns_key = 0

            for item in result:
                if item['error'] != '':
                    continue
                host_name = self.get_host_name(item['hostid'])

                if self.output_format == 'json':
                    result_columns[result_columns_key] = {'itemid': item['itemid'],
                                                          'name': item['name'],
                                                          'key': item['key_'],
                                                          'lastvalue': item['lastvalue'],
                                                          'host': host_name}
                else:
                    result_columns[result_columns_key] = {'1': item['itemid'],
                                                          '2': item['name'],
                                                          '3': item['key_'],
                                                          '4': item['lastvalue'],
                                                          '5': host_name}

                result_columns_key = result_columns_key + 1
            #
            # Generate output
            #
            self.generate_output(result_columns,
                                 ['ItemID', 'Name', 'Key', 'Last value', 'Host name'],
                                 ['Name', 'Key', 'Host name'],
                                 ['ItemID', 'Last value'],
                                 FRAME)
        else:
            key_values = {}

            for item in result:
                if item['error'] != '':
                    continue
                if 'error' in item and item['error'] != '':
                    print(self.get_host_name(item['hostid']))
                    print(item)
                name = item['name']
                key = item['key_']
                lastvalue = item['lastvalue']
                host_name = self.get_host_name(item['hostid'])

                short_item = {'name': name,
                              'key': key,
                              'lastvalue': lastvalue,
                              'host': host_name}

                if key in key_values:
                    if lastvalue in key_values[key]:
                        key_values[key][lastvalue].append(short_item)
                    else:
                        key_values[key][lastvalue] = [short_item]
                else:
                    key_values[key] = {lastvalue: [short_item]}

            result_columns = {}
            result_columns_key = 0

            for key, values in key_values.iteritems():
                for value, short_items in values.iteritems():
                    if self.output_format == 'json':
                        result_columns[result_columns_key] = {'name': short_items[0]['name'],
                                                              'key': key,
                                                              'lastvalue': value,
                                                              'host': '\n'.join([item['host'] for item in short_items])}
                    else:
                        result_columns[result_columns_key] = {'1': short_items[0]['name'],
                                                              '2': key,
                                                              '3': value,
                                                              '4': '\n'.join([item['host'] for item in short_items])}

                    result_columns_key = result_columns_key + 1

            #
            # Generate output
            #
            self.generate_output(result_columns,
                                 ['Name', 'Key', 'Last value', 'Host name'],
                                 ['Name', 'Key', 'Host name'],
                                 ['Last value'],
                                 FRAME)

    def do_show_usermacro_template_list(self, args):
        '''
        DESCRITION:
        This command shows all templates with a defined macro

        COMMAND:
        show_usermacro_template_list [usermacro]

        [usermacro]
        -----------
        Usermacro name. The system will format this value to use the
        macro format definition needed by Zabbix.  e.g. site_url will be
        converted to ${SITE_URL}

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                template_macro_name = input('# Host macro name: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 1:
            template_macro_name = arg_list[0].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if template_macro_name == '':
            self.generate_feedback('Error', 'Host macro name is empty')
            return False

        else:
            template_macro_name = '{$' + template_macro_name.upper() + '}'

        #
        # Get macro hostlist
        #

        try:
            result = self.zapi.usermacro.get(output='extend',
                                             selectTemplates=['host'],
                                             search={'macro': template_macro_name},
                                             searchWildcardsEnabled=True,
                                             sortfield='macro')

        except Exception as e:
            logger.error('Problems getting template list for macro %s - %s', template_macro_name, e)
            self.generate_feedback('Error', 'Problems getting template list for macro ' + template_macro_name)
            return False

        #
        # Get the columns we want to show from result
        #

        for macro in result:

            if len(macro['templates']) > 0:

                if self.output_format == 'json':
                    result_columns[result_columns_key] = {'macro': macro['macro'],
                                                          'value': macro['value'],
                                                          'templateid': macro['templates'][0]['templateid'],
                                                          'template': macro['templates'][0]['host']}

                else:

                    result_columns[result_columns_key] = {'1': macro['macro'],
                                                          '2': macro['value'],
                                                          '3': macro['templates'][0]['templateid'],
                                                          '4': macro['templates'][0]['host']}

                result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Macro', 'Value', 'TemplateID', 'Template'],
                             ['Macro', 'Value', 'Template'],
                             ['TemplateID'],
                             FRAME)

    def do_show_items(self, args):
        '''
        DESCRIPTION:
        This command shows items that belong to a template

        COMMAND:
        show_items [template]

        [template]
        ----------
        Template name or zabbix-templateID

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                template = input('# Template: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            template = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if template == '':
            self.generate_feedback('Error', 'Template value is empty')
            return False

        #
        # Getting template ID
        #

        if not template.isdigit():

            try:
                templateid = self.get_template_id(template)

            except Exception as e:
                logger.error('%s', e)
                self.generate_feedback('Error', e)
                return False

        else:
            templateid = template

        #
        # Getting items
        #
        try:
            result = self.zapi.item.get(output='extend',
                                        templateids=templateid,
                                        sortfield='name',
                                        sortorder='ASC')

        except Exception as e:
            logger.error('Problems getting items list for template (%s) - %s', template, e)
            self.generate_feedback('Error', 'Problems getting items list for template (' + template + ')')
            return False

        #
        # Get the columns we want to show from result
        #

        for item in result:

            if self.output_format == 'json':
                result_columns[result_columns_key] = {'itemid': item['itemid'],
                                                      'name': item['name'],
                                                      'key': item['key_'],
                                                      'type': zabbix_cli.utils.get_item_type(int(item['type'])),
                                                      'interval': item['delay'],
                                                      'history': item['history'],
                                                      'description': '\n'.join(textwrap.wrap(item['description'], 60))}
            else:
                result_columns[result_columns_key] = {'1': item['itemid'],
                                                      '2': item['name'],
                                                      '3': item['key_'],
                                                      '4': zabbix_cli.utils.get_item_type(int(item['type'])),
                                                      '5': item['delay'],
                                                      '6': item['history'],
                                                      '7': '\n'.join(textwrap.wrap(item['description'], 60))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['ItemID', 'Name', 'Key', 'Type', 'Interval', 'History', 'Description'],
                             ['Name', 'Name', 'Key', 'Description'],
                             ['ItemID'],
                             FRAME)

    def do_show_triggers(self, args):
        '''
        DESCRIPTION:
        This command shows triggers that belong to a template

        COMMAND:
        show_triggers [template]

        [template]
        ----------
        Template name or zabbix-templateID

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                template = input('# Template: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            template = arg_list[0].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if template == '':
            self.generate_feedback('Error', 'Template value is empty')
            return False

        #
        # Getting template ID
        #

        if not template.isdigit():

            try:
                templateid = self.get_template_id(template)

            except Exception as e:
                logger.error('Problems getting templateID - %s', e)
                self.generate_feedback('Error', 'Problems getting templateID')
                return False

        else:
            templateid = template

        #
        # Getting triggers
        #
        try:
            result = self.zapi.trigger.get(output='triggerid',
                                           templateids=templateid,
                                           sortfield='triggerid',
                                           sortorder='ASC')

        except Exception as e:
            logger.error('Problems getting trigger list for template (%s) - %s', template, e)
            self.generate_feedback('Error', 'Problems getting trigger list for template (' + template + ')')
            return False

        #
        # Get the columns we want to show from result
        #

        for trigger in result:

            trigger_data = self.zapi.trigger.get(output='extend',
                                                 expandExpression=1,
                                                 triggerids=trigger['triggerid'])

            for data in trigger_data:

                if self.output_format == 'json':
                    result_columns[result_columns_key] = {'triggerid': data['triggerid'],
                                                          'expression': data['expression'],
                                                          'description': data['description'],
                                                          'priority': zabbix_cli.utils.get_trigger_severity(int(data['priority'])),
                                                          'status': zabbix_cli.utils.get_trigger_status(int(data['status']))}

                else:
                    result_columns[result_columns_key] = {'1': data['triggerid'],
                                                          '2': data['expression'],
                                                          '3': data['description'],
                                                          '4': zabbix_cli.utils.get_trigger_severity(int(data['priority'])),
                                                          '5': zabbix_cli.utils.get_trigger_status(int(data['status']))}

                result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['TriggerID', 'Expression', 'Description', 'Priority', 'Status'],
                             ['Expression', 'Description'],
                             ['TriggerID'],
                             FRAME)

    def do_export_configuration(self, args):
        '''
        DESCRIPTION:
        This command exports the configuration of different
        Zabbix components to a JSON or XML file. Several
        parameters in the zabbix-cli.conf configuration file
        can be used to control some export options.

        COMMAND:
        export_configuration [export_directory]
                             [object type]
                             [object name]

        [export directory]
        ------------------
        Directory where the export files will be saved.

        [object type]
        ------------------
        Possible values: groups, hosts, images, maps, screens, templates
        One can use the special value #all# to export all object type groups.

        [object name]
        -------------
        Object name or Zabbix-ID. One can define several values in a comma
        separated list.

        One can use the special value #ALL# to export all objects in a object
        type group. This parameter will be defined automatically as #all# if [object type] == #all#

        '''

        #
        # Default values
        #

        # Object type
        object_type_list = ['groups', 'hosts', 'images', 'maps', 'screens', 'templates']
        object_type_to_export = []

        # Default object type
        default_object_type = '#all#'

        # Default object name
        default_object_name = '#all#'

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                directory_exports = input('# Directory [' + self.conf.default_directory_exports + ']: ').strip()
                object_type = input('# Object type [' + default_object_type + ']: ').strip().lower()
                object_name = input('# Object name [' + default_object_name + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 3:
            directory_exports = arg_list[0].strip()
            object_type = arg_list[1].strip().lower()
            object_name = arg_list[2].strip()
        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if directory_exports == '':
            directory_exports = self.conf.default_directory_exports

        for obj_type in object_type_list:

            if not os.path.exists(directory_exports + '/' + obj_type):

                try:
                    os.makedirs(directory_exports + '/' + obj_type, mode=0o700)
                    logger.info('Export directory created: %s', directory_exports + '/' + obj_type)

                except OSError as e:
                    logger.error('OS error when creating export directory %s - %s', directory_exports + '/' + obj_type, e)
                    self.generate_feedback('Error', 'OS error when creating export directory ' + directory_exports + '/' + obj_type)
                    return False

        if object_type == '':
            object_type = default_object_type

        if object_type not in object_type_list + ['#all#']:
            self.generate_feedback('Error', 'Object type is not a valid value')
            return False

        if object_type.lower() == '#all#':
            object_type_to_export = object_type_list
        else:
            object_type_to_export.append(object_type)

        if object_name == '' or object_type.lower() == '#all#':
            object_name = default_object_name

        #
        # Generate export files for all defined object types
        #

        for obj_type in object_type_to_export:

            object_name_list = {}

            #
            # Generate object IDs list to export if the special value #all#
            # has been defined.
            #

            if object_name.lower() == '#all#':

                try:

                    if obj_type == 'groups':

                        data = self.zapi.hostgroup.get(output="extend")

                        for object in data:
                            object_name_list[object['groupid']] = object['name']

                    elif obj_type == 'hosts':

                        data = self.zapi.host.get(output="extend")

                        for object in data:
                            object_name_list[object['hostid']] = object['host']

                    elif obj_type == 'images':

                        data = self.zapi.image.get(output="extend")

                        for object in data:
                            object_name_list[object['imageid']] = object['name']

                    elif obj_type == 'maps':

                        data = self.zapi.map.get(output="extend")

                        for object in data:
                            object_name_list[object['sysmapid']] = object['name']

                    elif obj_type == 'screens':

                        data = self.zapi.screen.get(output="extend")

                        for object in data:
                            object_name_list[object['screenid']] = object['name']

                    elif obj_type == 'templates':

                        data = self.zapi.template.get(output="extend")

                        for object in data:
                            object_name_list[object['templateid']] = object['host']

                except Exception as e:
                    logger.error('Problems getting all [%s] objects - %s', obj_type, e)
                    self.generate_feedback('Error', 'Problems getting all [' + obj_type + '] objects')
                    return False

            #
            # Generate object IDs list to export for all defined
            # object names.
            #

            else:
                for name in object_name.split(','):

                    if name.strip().isdigit() and name.strip() != '':
                        object_name_list[str(name).strip()] = str(name).strip()

                    elif not name.strip().isdigit() and name.strip() != '':
                        try:
                            if obj_type == 'groups':
                                id = str(self.get_hostgroup_id(name.strip()))

                            elif obj_type == 'hosts':
                                id = str(self.get_host_id(name.strip()))

                            elif obj_type == 'images':
                                id = str(self.get_image_id(name.strip()))

                            elif obj_type == 'maps':
                                id = str(self.get_map_id(name.strip()))

                            elif obj_type == 'screens':
                                id = str(self.get_screen_id(name.strip()))

                            elif obj_type == 'templates':
                                id = str(self.get_template_id(name.strip()))

                            object_name_list[id] = name.strip()

                        except Exception as e:
                            logger.error('Problems getting ID for object type [%s] and object name [%s] - %s', obj_type, name, e)
                            self.generate_feedback('Error', 'Problems getting ID for object type [' + obj_type + '] and object name [' + name + ']')
                            return False

            #
            # Generate export files for all defined object names
            #

            for obj_name_key in object_name_list.keys():

                try:
                    data = self.zapi.configuration.export(format=self.conf.default_export_format.lower(),
                                                          options={obj_type: [obj_name_key]})

                    #
                    # Formating and indenting the export data
                    #

                    if self.conf.default_export_format.upper() == 'JSON':
                        output = json.dumps(json.JSONDecoder().decode(data), sort_keys=True, indent=2)
                    else:
                        '''
                        We have problems importing xml files that have been formatting with toprettyxml.
                        This has to be investigated.
                        xml_code = xml.dom.minidom.parseString(data)
                        output= xml_code.toprettyxml(indent='  ')
                        '''
                        output = data

                    #
                    # Writing to the export file
                    #
                    filename = self.generate_export_filename(directory_exports, obj_type, obj_name_key, object_name_list[obj_name_key])

                    with open(filename, 'wb') as export_filename:
                        export_filename.write(output.encode("utf8"))

                    logger.info('Export file/s for object type [%s] and object name [%s] generated', obj_type, object_name_list[obj_name_key])

                except Exception as e:
                    logger.error('Problems generating export file for object type [%s] and object name [%s] - %s', obj_type, object_name_list[obj_name_key], e)
                    self.generate_feedback('Error', 'Problems generating export file for object type [' + obj_type + '] and object name [' + object_name_list[obj_name_key] + ']')
                    return False

        logger.info('Export file/s for object type [%s] and object name [%s] generated', object_type, object_name)

        self.generate_feedback('Done', 'Export file/s for object type [' + object_type + '] and object name [' + object_name + '] generated')

    def do_import_configuration(self, args):
        '''DESCRIPTION:
        This command imports the configuration of a
        Zabbix component.

        We use the options createMissing=True and updateExisting=True
        when importing data. This means that new objects will be
        created if they do not exists and that existing objects will
        be updated if they exist.

        COMMAND:
        import_configuration [import file]
                             [dry run]

        [import file]
        -------------
        File with the JSON or XML code to import. This command will
        use the file extension (.json or .xml) to find out the import format.

        This command finds all the pathnames matching a specified
        pattern according to the rules used by the Unix shell.  Tilde
        expansion, *, ?, and character ranges expressed with [] will
        be correctly matched. For a literal match, wrap the
        meta-characters in brackets. For example, '[?]' matches the
        character '?'.

        [dry run]
        ---------
        If this parameter is used, the command will only show the
        files that would be imported without running the import
        process.

        0: Dry run deactivated
        1: Dry run activated [*]

        '''

        #
        # Default values
        #
        total_files_imported = 0
        total_files_not_imported = 0

        dry_run_default = '1'

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                files = input('# Import file []: ').strip()
                dry_run = input('# Dry run [' + dry_run_default + ']: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        #
        # Command with parameters
        #

        elif len(arg_list) == 1:
            files = arg_list[0].strip()
            dry_run = dry_run_default

        elif len(arg_list) == 2:
            files = arg_list[0].strip()
            dry_run = arg_list[1].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        if files == '':
            self.generate_feedback('Error', 'Files value is empty')
            return False

        if dry_run == '' or dry_run not in ('0', '1'):
            dry_run = dry_run_default

        #
        # Expand users HOME when using ~ or ~user
        #
        files = os.path.expanduser(files)

        # Normalized absolutized version of the pathname if
        # files does not include an absolute path

        if not os.path.isabs(files):
            files = os.path.abspath(files)

        #
        # Finds all the pathnames matching a specified pattern
        # according to the rules used by the Unix shell. No tilde
        # expansion is done, but *, ?, and character ranges expressed
        # with [] will be correctly matched. For a literal match, wrap
        # the meta-characters in brackets. For example, '[?]' matches
        # the character '?'.
        #

        expanded_files = glob.glob(files)

        if expanded_files == []:
            logger.error('Files %s do not exists', files)

        if dry_run == '1':

            #
            # Dry run. Show files that would be imported
            # without running the import process.
            #

            print('\n')
            print('# -----------------------------------------------')
            print('# Dry run: ON')
            print('# These files would be imported with dry run: OFF')
            print('# -----------------------------------------------')
            print('\n')

        for file in expanded_files:
            if os.path.exists(file):
                if os.path.isfile(file):

                    file_ext = os.path.splitext(file)[1]

                    if file_ext.lower() == '.json':
                        format = 'json'
                    elif file_ext.lower() == '.xml':
                        format = 'xml'
                    else:
                        total_files_not_imported = total_files_not_imported + 1
                        logger.error('The file %s is not a JSON or XML file', file)
                        # Get the next file if this one is not a JSON or XML file
                        continue

                    if dry_run == '1':

                        #
                        # Dry run. Show files that would be imported
                        # without running the import process.
                        #

                        print('# File: ' + file)

                    elif dry_run == '0':

                        #
                        # Import the file
                        #

                        try:
                            with open(file, 'r') as import_filename:
                                import_data = import_filename.read()

                                data = self.zapi.confimport(format=format,
                                                            source=import_data,
                                                            rules={
                                                                'applications': {'createMissing': True},
                                                                'discoveryRules': {'createMissing': True, 'updateExisting': True},
                                                                'graphs': {'createMissing': True, 'updateExisting': True},
                                                                'groups': {'createMissing': True},
                                                                'hosts': {'createMissing': True, 'updateExisting': True},
                                                                'images': {'createMissing': True, 'updateExisting': True},
                                                                'items': {'createMissing': True, 'updateExisting': True},
                                                                'maps': {'createMissing': True, 'updateExisting': True},
                                                                'screens': {'createMissing': True, 'updateExisting': True},
                                                                'templateLinkage': {'createMissing': True},
                                                                'templates': {'createMissing': True, 'updateExisting': True},
                                                                'templateScreens': {'createMissing': True, 'updateExisting': True},
                                                                'triggers': {'createMissing': True, 'updateExisting': True}
                                                            })

                                if data:
                                    total_files_imported = total_files_imported + 1
                                    logger.info('The file %s has been imported into Zabbix', file)

                                else:
                                    total_files_not_imported = total_files_not_imported + 1
                                    logger.info('The file %s could not been imported into Zabbix', file)

                        except Exception as e:
                            total_files_not_imported = total_files_not_imported + 1
                            logger.error('The file %s could not be imported into Zabbix - %s', file, e)
            else:
                logger.error('The file %s does not exists', file)

        self.generate_feedback('done', 'Total files Imported [' + str(total_files_imported) + '] / Not imported [' + str(total_files_not_imported) + ']')

    def do_move_proxy_hosts(self, args):
        '''
        DESCRIPTION:
        This command moves all hosts monitored by a proxy (src) to
        another proxy (dst).

        COMMAND:
        move_proxy_hosts [proxy_src]
                         [proxy_dst]

        [proxy_src]
        -----------
        Source proxy server.

        [proxy_dst]
        -----------
        Destination proxy server.

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                proxy_src = input('# SRC Proxy: ').strip()
                proxy_dst = input('# DST Proxy: ').strip().lower()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 2:
            proxy_src = arg_list[0].strip()
            proxy_dst = arg_list[1].strip()

        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        try:
            proxy_src_id = self.get_proxy_id(proxy_src)

        except Exception:
            logger.error('SRC Proxy %s does not exist', proxy_src)
            self.generate_feedback('Error', 'SRC Proxy ' + proxy_src + ' does not exist')
            return False

        try:
            proxy_dst_id = self.get_proxy_id(proxy_dst)

        except Exception:
            logger.error('DST Proxy %s does not exist', proxy_dst)
            self.generate_feedback('Error', 'DST Proxy ' + proxy_dst + ' does not exist')
            return False

        try:
            result = self.zapi.proxy.get(output='extend',
                                         proxyids=proxy_src_id,
                                         selectHosts=['hostid', 'name'])

        except Exception as e:
            logger.error('Problems getting host list from SRC proxy %s - %s', proxy_src, e)
            self.generate_feedback('Error', 'Problems getting host list from SRC proxy %s' + proxy_src)
            return False

        try:

            hostid_list_tmp = []
            hostid_list = []

            for host in result[0]['hosts']:
                hostid_list_tmp.append('{"hostid":"' + str(host['hostid']) + '"}')

            hostid_list = ','.join(hostid_list_tmp)
            query = ast.literal_eval("{\"hosts\":[" + hostid_list + "],\"proxy_hostid\":\"" + proxy_dst_id + "\"}")

            result = self.zapi.host.massupdate(**query)
            logger.info('Hosts from SRC Proxy %s have been moved to DST proxy %s', proxy_src, proxy_dst)
            self.generate_feedback('Done', 'Hosts from SRC Proxy ' + proxy_src + ' have been moved to DST proxy ' + proxy_dst)

        except Exception as e:
            logger.error('Problems moving hosts from SRC Proxy %s to DST proxy %s - %s', proxy_src, proxy_dst, e)
            self.generate_feedback('Error', 'Problems moving host from SRC Proxy ' + proxy_src + ' to DST proxy ' + proxy_dst)
            return False

    def do_load_balance_proxy_hosts(self, args):
        '''
        DESCRIPTION:
        This command will spread hosts evenly along a serie of proxies.

        COMMAND:
        load_balance_proxy_hosts [proxy list]

        [proxy list]:
        Comma delimited list with the proxies that will share the
        monitoring task for a group of hosts.

        The group of hosts is obtained from the hosts assigned to the
        proxies in [proxy list]

        '''
        proxy_list = []
        proxyid_list = []

        all_hosts = []
        host_proxy_relation = {}

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print('\n[ERROR]: ' + e + '\n')
            return False

        if len(arg_list) == 0:
            try:
                print('--------------------------------------------------------')
                proxies = input('# Proxies: ').strip()
                print('--------------------------------------------------------')

            except EOFError:
                print('\n--------------------------------------------------------')
                print('\n[Aborted] Command interrupted by the user.\n')
                return False

        elif len(arg_list) == 1:
            proxies = arg_list[0].strip()
        else:
            self.generate_feedback('Error', ' Wrong number of parameters used.\n          Type help or \\? to list commands')
            return False

        #
        # Sanity check
        #

        proxy_list = proxies.split(',')

        for proxy in proxy_list:

            try:
                proxyid = self.get_proxy_id(proxy.strip())
                proxyid_list.append(proxyid)

            except Exception as e:
                logger.error('Proxy [%s] does not exist - %s', proxy.strip(), e)
                self.generate_feedback('Error', 'Proxy [' + proxy.strip() + '] does not exist')
                return False

        #
        # Getting all host monitored by the proxies defined in
        # proxyid_list. These are the host that will get spreaded
        # evenly along the defined proxies.
        #

        try:

            for proxyid in proxyid_list:
                result = self.zapi.proxy.get(output='extend',
                                             proxyids=proxyid,
                                             selectHosts=['hostid'])

                for host in result[0]['hosts']:
                    all_hosts.append(host['hostid'])

        except Exception as e:
            logger.error('Problems getting affected hosts - %s', e)
            self.generate_feedback('Error', 'Problems getting affected hosts')
            return False

        #
        # Create a dicctionary with hostid:proxyid entries. The
        # proxyid value will be chosen randomly from the list of
        # defined proxies.
        #

        for hostid in all_hosts:
            host_proxy_relation[hostid] = proxyid_list[random.randint(0, len(proxyid_list) - 1)]

        try:

            for proxyid in proxyid_list:

                hostid_list_tmp = []
                hostid_list = []

                for hostid, proxyid2 in host_proxy_relation.iteritems():

                    if proxyid2 == proxyid:
                        hostid_list_tmp.append('{"hostid":"' + str(hostid) + '"}')

                hostid_list = ','.join(hostid_list_tmp)
                query = ast.literal_eval("{\"hosts\":[" + hostid_list + "],\"proxy_hostid\":\"" + proxyid + "\"}")

                result = self.zapi.host.massupdate(**query)

            logger.info('Balanced configuration of hosts along defined proxies done')
            self.generate_feedback('Done', 'Balanced configuration of hosts along defined proxies done')

        except Exception as e:
            logger.error('Problems assigning new proxy values for the affected hosts - %s', e)
            self.generate_feedback('Error', 'Problems assigning new proxy values for the affected hosts')
            return False

    def generate_export_filename(self, directory_exports, obj_type, obj_id, obj_name):
        '''
        Generate filename to export the configuration
        '''

        if self.conf.default_export_format.upper() == 'JSON':
            file_ext = 'json'

        elif self.conf.default_export_format.upper() == 'XML':
            file_ext = 'xml'

        else:
            file_ext = 'json'

        if self.conf.include_timestamp_export_filename.upper() == 'ON':
            timestamp = '_' + datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S%Z')

        elif self.conf.include_timestamp_export_filename.upper() == 'OFF':
            timestamp = ''

        else:
            timestamp = '_' + datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S%Z')

        filename = directory_exports + '/' + obj_type + '/zabbix_export_' + obj_type + '_' + obj_name.replace(' ', '_').replace('/', '_') + '_' + obj_id + timestamp + '.' + file_ext
        return filename

    def generate_output(self, result, colnames, left_col, right_col, hrules):
        '''
        Generate the result output
        '''

        try:

            if self.output_format == 'table':

                x = PrettyTable(colnames)
                x.header = True
                x.padding_width = 1

                # FRAME, ALL, NONE
                x.hrules = hrules

                for column in left_col:
                    x.align[column] = "l"

                for column in right_col:
                    x.align[column] = "r"

                for records in result:
                    columns = []

                    for column in sorted(result[records].keys()):
                        columns.append(result[records][column])

                    x.add_row(columns)

                print(x.get_string() + '\n')

            elif self.output_format == 'csv':

                print(",".join(colnames))

                for records in result:
                    columns = []

                    for column in sorted(result[records]):
                        columns.append(result[records][column])

                    print('"' + '","'.join(columns) + '"')

            elif self.output_format == 'json':

                print(json.dumps(result, sort_keys=True, indent=2))

        except Exception as e:
            print('\n[Error] Problems generating the output ' + e)
            logger.error('Problems generating the output', exc_info=True)

    def generate_feedback(self, return_code, message):
        '''
        Generate feedback messages
        '''

        if self.output_format == 'table':
            print('\n[' + return_code.title() + ']: ' + str(message) + '\n\n')

            if self.non_interactive or self.bulk_execution:

                if return_code.lower() == 'error':
                    sys.exit(1)

        elif self.output_format == 'csv':
            print('"' + return_code.lower() + '","' + str(message) + '"\n')

            if self.non_interactive or self.bulk_execution:

                if return_code.lower() == 'error':
                    sys.exit(1)

        elif self.output_format == 'json':
            output = {"return_code": return_code.lower(), "message": str(message)}
            print(json.dumps(output, sort_keys=True, indent=2))

            if self.non_interactive or self.bulk_execution:

                if return_code.lower() == 'error':
                    sys.exit(1)

    def do_clear(self, args):
        '''
        DESCRIPTION:
        Clears the screen and shows the welcome banner.

        COMMAND:
        clear

        '''

        os.system('clear')
        print(self.intro)

    def default(self, line):
        self.generate_feedback('Error', ' Unknown command: %s.\n          Type help or \\? to list commands' % line)

    def emptyline(self):
        pass

    def precmd(self, line_in):

        if line_in != '':
            split_line = line_in.split()

            if split_line[0] not in ['EOF', 'shell', 'SHELL', '\\!']:
                split_line[0] = split_line[0].lower()
                line_out = ' '.join(split_line)
            else:
                line_out = line_in

            if split_line[0] == '\\h':
                line_out = 'help'
            elif split_line[0] == '\\?':
                line_out = 'help'
            elif split_line[0] == '\\!':
                line_out = line_out.replace('\\!', 'shell')
            elif line_out == '\\s':
                line_out = 'show_history'
            elif line_out == '\\q':
                line_out = 'quit'

            self._hist += [line_out.strip()]

        else:
            line_out = ''

        return cmd.Cmd.precmd(self, line_out)

    def do_shell(self, line):
        '''
        DESCRIPTION:
        This command runs a command in the operative system

        COMMAND:
        shell [command]

        [command]:
        ----------
        Any command that can be run in the operative system.

        '''

        try:
            proc = subprocess.Popen([line], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
            output, errors = proc.communicate()
            print(output + errors + '\n')

        except Exception:
            self.generate_feedback('Error', 'Problems running %s' % line)

    def do_quit(self, args):
        '''
        DESCRIPTION:
        Quits/terminate the Zabbix-CLI shell.

        COMMAND:
        quit

        '''

        print('\nDone, thank you for using Zabbix-CLI')
        return True

    def do_EOF(self, line):
        '''
        DESCRIPTION:
        Quit/terminate the Zabbix-CLI shell.

        COMMAND:
        EOF

        '''

        print('\n\nDone, thank you for using Zabbix-CLI')
        return True

    def do_show_history(self, args):
        '''
        DESCRIPTION:
        This command shows the list of commands that have been entered
        during the Zabbix-CLI shell session.

        COMMAND:
        show_history

        '''

        cnt = 0
        print()

        for line in self._hist:
            print('[' + str(cnt) + ']: ' + line)
            cnt = cnt + 1

        print()

    def hostgroup_exists(self, hostgroup):
        '''
        DESCRIPTION:
        Find out if hostgroup exists
        '''

        data = self.zapi.hostgroup.get(filter={'name': hostgroup})

        if data != []:
            return True
        else:
            return False

    def get_hostgroup_id(self, hostgroup):
        '''
        DESCRIPTION:
        Get the hostgroup_id for a hostgroup
        '''

        if self.bulk_execution:

            if hostgroup in self.hostgroupname_cache:
                hostgroupid = self.hostgroupname_cache[hostgroup]

            else:
                raise Exception('Could not find hostgroupID for: ' + hostgroup)

        else:

            data = self.zapi.hostgroup.get(filter={'name': hostgroup})

            if data != []:
                hostgroupid = data[0]['groupid']
            else:
                raise Exception('Could not find hostgroupID for: ' + hostgroup)

        return str(hostgroupid)

    def host_exists(self, host):
        '''
        DESCRIPTION:
        Find out if a hostname exists in zabbix
        '''

        if self.bulk_execution:

            if host in self.hostid_cache.values():
                return True
            else:
                return False

        else:

            data = self.zapi.host.get(filter={"host": host})

            if data != []:
                return True
            else:
                return False

    def get_host_id(self, host):
        '''
        DESCRIPTION:
        Get the hostid for a host
        '''

        data = self.zapi.host.get(filter={"host": host})

        if data != []:
            hostid = data[0]['hostid']
        else:
            raise Exception('Could not find hostID for:' + host)

        return str(hostid)

    def get_host_name(self, hostid):
        '''
        DESCRIPTION:
        Get the host name for a hostID
        '''

        #
        # Return the value if it exists from the dictionary
        # hostid_cache.
        #

        if hostid in self.hostid_cache:
            host_name = self.hostid_cache[hostid]

        else:

            data = self.zapi.host.get(output=['host'],
                                      hostids=hostid)

            if data != []:
                host_name = data[0]['host']
                self.hostid_cache[hostid] = host_name

            else:
                raise Exception('Could not find hostname for ID:' + hostid)

        return str(host_name)

    def get_template_name(self, templateid):
        '''
        DESCRIPTION:
        Get the template name for a templateID
        '''

        data = self.zapi.template.get(output='extend',
                                      templateids=templateid)

        if data != []:
            template_name = data[0]['name']
        else:
            raise Exception('Could not find template for ID:' + templateid)

        return str(template_name)

    def get_image_id(self, image):
        '''
        DESCRIPTION:
        Get the imageid for a image
        '''

        print(image)

        data = self.zapi.image.get(filter={"name": image})

        print(data)

        if data != []:
            imageid = data[0]['imageid']
        else:
            raise Exception('Could not find imageID for:' + image)

        return str(imageid)

    def get_map_id(self, map):
        '''
        DESCRIPTION:
        Get the mapid for a map
        '''

        data = self.zapi.map.getobjects(name=map)

        if data != []:
            mapid = data[0]['sysmapid']
        else:
            raise Exception('Could not find mapID for:' + map)

        return str(mapid)

    def get_screen_id(self, screen):
        '''
        DESCRIPTION:
        Get the screenid for a screen
        '''

        data = self.zapi.screen.get(filter={"name": screen})

        if data != []:
            screenid = data[0]['screenid']
        else:
            raise Exception('Could not find screenID for:' + screen)

        return str(screenid)

    def get_template_id(self, template):
        '''
        DESCRIPTION:
        Get the templateid for a template
        '''

        data = self.zapi.template.get(filter={"host": template})

        if data != []:
            templateid = data[0]['templateid']
        else:
            raise Exception('Could not find TemplateID for:' + template)

        return str(templateid)

    def usergroup_exists(self, usergroup):
        '''
        DESCRIPTION:
        Find out if usergroups exists
        '''

        data = self.zapi.usergroup.get(output=['usrgrpid'],
                                       filter={"name": usergroup})

        if data != []:
            return True
        else:
            return False

    def get_usergroup_id(self, usergroup):
        '''
        DESCRIPTION:
        Get the usergroupid for a usergroup
        '''

        data = self.zapi.usergroup.get(output=['usrgrpid'],
                                       filter={"name": usergroup})

        if data != []:
            usergroupid = data[0]['usrgrpid']
        else:
            raise Exception('Could not find usergroupID for: ' + usergroup)

        return str(usergroupid)

    def get_user_id(self, user):
        '''
        DESCRIPTION:
        Get the userid for a user
        '''

        data = self.zapi.user.get(filter={'alias': user})

        if data != []:
            userid = data[0]['userid']
        else:
            raise Exception('Could not find userID for: ' + user)

        return str(userid)

    def get_proxy_id(self, proxy):
        '''
        DESCRIPTION:
        Get the proxyid for a proxy server
        '''

        if proxy != '':

            data = self.zapi.proxy.get(filter={"host": proxy})

            if data != []:
                proxyid = data[0]['proxyid']
            else:
                raise Exception('Could not find proxyID for:' + proxy)

        else:
            raise Exception('Cannot get the proxyID of an empty proxy value')

        return str(proxyid)

    def get_random_proxyid(self, proxy_pattern):
        '''
        Return a random proxyID from the list of proxies that match the
        regular expression sent as a parameter to this funtion

        '''

        proxy_list = []
        match_pattern = re.compile(proxy_pattern)

        if self.bulk_execution:

            for proxyid, proxy_name in self.proxyid_cache.iteritems():
                if match_pattern.match(proxy_name):
                    proxy_list.append(proxyid)

        else:

            data = self.zapi.proxy.get(output=['proxyid', 'host'])

            for proxy in data:
                if match_pattern.match(proxy['host']):
                    proxy_list.append(proxy['proxyid'])

        proxy_list_len = len(proxy_list)

        if proxy_list_len > 0:
            get_random_index = random.randint(0, proxy_list_len - 1)
            return proxy_list[get_random_index]

        else:
            raise Exception('The proxy list is empty. Using the zabbix server to monitor this host.')

    def populate_hostid_cache(self):
        '''
        DESCRIPTION:
        Populate hostid cache
        '''

        # This method initializes a dictionary when we start
        # zabbix-cli with all hostid:hostname from hosts that are
        # defined in zabbix. We use this as a cache to get hostname
        # information for a hostid.
        #
        # This cache is necessary e.g. by the show_alarms to avoid an
        # API call per active trigger to get the hostname of the host
        # with the associated trigger because this is a very expensive
        # operation on big systems with many active triggers.
        #
        # This has to be done this way now because with zabbix 3.0 the
        # API has changed and it is not possible to get the hostname
        # value via trigger.get(). expandData parameter got
        # deprecated in 2.4 and removed in 3.0.
        #

        temp_dict = {}

        data = self.zapi.host.get(output=['hostid', 'host'])

        for host in data:
            temp_dict[host['hostid']] = host['host']

        return temp_dict

    def populate_hostgroupname_cache(self):
        '''
        DESCRIPTION:
        Populate hostgroupname cache
        '''

        # This method initializes a dictionary with all hostgroups in
        # the system.
        #
        # This will help the performance of creating a host via bulk
        # executions because we avoid an extra call to the zabbix-API.
        #

        temp_dict = {}

        data = self.zapi.hostgroup.get(output=['groupid', 'name'])

        for hostgroup in data:
            temp_dict[hostgroup['name']] = hostgroup['groupid']

        return temp_dict

    def populate_proxyid_cache(self):
        '''
        DESCRIPTION:
        Populate proxyid cache
        '''

        # This method initializes a dictionary with all active proxies
        # in the system.
        #
        # This will help the performance of creating a host via bulk
        # executions because we avoid an extra call to the zabbix-API.
        #

        temp_dict = {}

        data = self.zapi.proxy.get(output=['proxyid', 'host'])

        for proxy in data:
            temp_dict[proxy['proxyid']] = proxy['host']

        return temp_dict

    def preloop(self):
        '''
        Initialization before prompting user for commands.
        '''
        cmd.Cmd.preloop(self)  # sets up command completion
        self._hist = []        # No history yet
        self._locals = {}      # Initialize execution namespace for user
        self._globals = {}

    def help_shortcuts(self):
        '''
        Help information about shortcuts in Zabbix-CLI
        '''

        print('''
        Shortcuts in Zabbix-CLI:

        \\s - display history
        \\q - quit Zabbix-CLI shell

        \\! [COMMAND] - Execute a command in shell
        !  [COMMAND] - Execute a command in shell

        ''')

    def help_support(self):
        '''
        Help information about Zabbix-CLI support
        '''

        print('''
        The latest information and versions of Zabbix-CLI can be obtained
        from: https://github.com/usit-gd/zabbix-cli

        The Zabbix-CLI documentation is available from:
        https://github.com/usit-gd/zabbix-cli/blob/master/docs/manual.rst

        Zabbix documentation:
        http://www.zabbix.com/documentation.php
        ''')

    def signal_handler_sigint(self, signum, frame):
        cmd.Cmd.onecmd(self, 'quit')
        sys.exit(0)

    def get_version(self):
        '''
        Get Zabbix-CLI version
        '''

        try:
            return zabbix_cli.__version__

        except Exception:
            return 'Unknown'


if __name__ == '__main__':
    cli = zabbix_cli()
    signal.signal(signal.SIGINT, cli.signal_handler_sigint)
    signal.signal(signal.SIGTERM, cli.signal_handler_sigint)
    cli.cmdloop()
