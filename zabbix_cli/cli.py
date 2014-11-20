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
#

import cmd
import sys
import os
import time
import signal
import shlex
import datetime
import subprocess
import ast
import ldap
import random
import hashlib
import textwrap
import json
import xml.dom.minidom
import glob

from zabbix_cli.config import *
from zabbix_cli.logs import *

from zabbix_cli.prettytable import *
import zabbix_cli.version

from zabbix_cli.pyzabbix import ZabbixAPI, ZabbixAPIException


# ############################################
# class zabbix_cli
# ############################################


class zabbix_cli(cmd.Cmd):
    '''
    This class implements the Zabbix shell. It is based on the python module cmd
    '''
  
    # ###############################
    # Constructor
    # ###############################

    def __init__(self,username,password,logs):
        cmd.Cmd.__init__(self)
        
        self.version = self.get_version()

        self.intro =  '\n#############################################################\n' + \
                      'Welcome to the Zabbix command-line interface (v.' + self.version + ')\n' + \
                      '#############################################################\n' + \
                      'Type help or \? to list commands.\n'
        
        self.prompt = '[zabbix-CLI]$ '
        self.file = None

        self.conf = configuration()
        self.logs = logs

        self.api_username = username
        self.api_password = password
        self.output_format = 'table'

        if self.conf.logging == 'ON':
            self.logs.logger.debug('Zabbix API url: %s',self.conf.zabbix_api_url)

        try:

            #
            # Connecting to the Zabbix JSON-API
            #

            self.zapi = ZabbixAPI(self.conf.zabbix_api_url)
            self.zapi.session.verify = False

            self.zapi.login(self.api_username,self.api_password)
        
            if self.conf.logging == 'ON':
                self.logs.logger.debug('Connected to Zabbix JSON-API')

        except Exception as e:        
            print '\n[ERROR]: ',e
            print
        
            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems logging to %s',self.conf.zabbix_api_url)
            
            sys.exit(1)


    # ############################################                                                                                                                                    
    # Method show_hostgroups
    # ############################################

    def do_show_hostgroups(self,args):
        '''
        DESCRIPTION:
        This command shows all hostgroups defined in the system.

        COMMAND:
        show_hostgroups
        '''

        cmd.Cmd.onecmd(self,'show_hostgroup "*"')


    # ############################################  
    # Method show_hostgroup
    # ############################################  

    def do_show_hostgroup(self,args):
        '''
        DESCRIPTION: 
        This command show hostgroups information

        COMMAND:
        show_hostgroup [Hostgroup name]

        [Hostgroup name]:
        ----------------
        One can search by hostgroup name. We can use wildcards.

        '''

        result_columns = {}
        result_columns_key = 0

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                hostgroup = raw_input('# Hostgroup: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroup == '':
            self.generate_feedback('Error','Template value is empty')
            return False

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.hostgroup.get(output='extend',
                                             search={'name':hostgroup},
                                             searchWildcardsEnabled=True,
                                             selectHosts=['host'],
                                             sortfield='name',
                                             sortorder='ASC')

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_hostgroups executed')

        except Exception as e: 

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting hostgroups information - %s',e)

            self.generate_feedback('Error','Problems getting hostgroups information')

            return False   

        #
        # Get the columns we want to show from result 
        #
        for group in result:
            
            if self.output_format == 'json':
                result_columns [result_columns_key] = {'groupid':group['groupid'],
                                                       'name':group['name'],
                                                       'flags':self.get_hostgroup_flag(int(group['flags'])),
                                                       'type':self.get_hostgroup_type(int(group['internal'])),
                                                       'hosts':group['hosts']}
            
            else:

                host_list = []
                group['hosts'].sort()
                
                for host in group['hosts']:
                    host_list.append(host['host'])

                result_columns [result_columns_key] = {'1':group['groupid'],
                                                       '2':group['name'],
                                                       '3':self.get_hostgroup_flag(int(group['flags'])),
                                                       '4':self.get_hostgroup_type(int(group['internal'])),
                                                       '5':'\n'.join(host_list)}
    

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['GroupID','Name','Flag','Type','Hosts'],
                             ['Name','Hosts'],
                             ['GroupID'],
                             ALL)


    # ############################################                                                                                                                                    
    # Method show_hosts
    # ############################################

    def do_show_hosts(self,args):
        '''
        DESCRIPTION:
        This command shows all hosts defined in the system.

        COMMAND:
        show_hosts
        '''

        cmd.Cmd.onecmd(self,'show_host "*"')


    # ############################################                                                                                                                                    
    # Method show_host
    # ############################################
    
    def do_show_host(self,args):
        '''
        DESCRIPTION:
        This command shows hosts information

        COMMAND:
        show_host [HostID / Hostname]
                  [Filter]

        [HostID / Hostname]:
        -------------------
        One can search by HostID or by Hostname. We can use wildcards 
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                host = raw_input('# Host: ').strip()
                filter = raw_input('# Filter: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
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
            query=ast.literal_eval("{'output':'extend'," + search_host  + ",'selectParentTemplates':['templateid','name'],'selectGroups':['groupid','name'],'selectApplications':['name'],'sortfield':'host','sortorder':'ASC','searchWildcardsEnabled':'True','filter':{" + filter + "}}")
        
        except Exception as e:
            
            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems generating show_host query - %s',e)

            self.generate_feedback('Error','Problems generating show_host query')
            return False

        #
        # Get result from Zabbix API
        #

        try:
            result = self.zapi.host.get(**query)
        
            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_host executed.')

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting host information - %s',e)

            self.generate_feddback('Error','Problems getting host information')
            return False   

        #
        # Get the columns we want to show from result 
        #

        for host in result:
        
            if self.output_format == 'json':
                result_columns [result_columns_key] = {'hostid':host['hostid'],
                                                       'host':host['host'],
                                                       'groups':host['groups'],
                                                       'templates':host['parentTemplates'],
                                                       'applications':host['applications'],
                                                       'zabbix_agent':self.get_zabbix_agent_status(int(host['available'])),
                                                       'maintenance_status':self.get_maintenance_status(int(host['maintenance_status'])),
                                                       'status':self.get_monitoring_status(int(host['status']))}

            else:
                
                hostgroup_list = []
                template_list = []
                application_list = []
                
                host['groups'].sort()
                host['parentTemplates'].sort()
                host['applications'].sort()
                
                for hostgroup in host['groups']:
                    hostgroup_list.append(hostgroup['name'])
                    
                for template in host['parentTemplates']:
                    template_list.append(template['name'])
                        
                for application in host['applications']:
                    application_list.append(application['name'])

                result_columns [result_columns_key] = {'1':host['hostid'],
                                                       '2':host['host'],
                                                       '3':'\n'.join(hostgroup_list),
                                                       '4':'\n'.join(template_list),
                                                       '5':'\n'.join(application_list),
                                                       '6':self.get_zabbix_agent_status(int(host['available'])),
                                                       '7':self.get_maintenance_status(int(host['maintenance_status'])),
                                                       '8':self.get_monitoring_status(int(host['status']))}



            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['HostID','Name','Hostgroups','Templates','Applications','Zabbix agent','Maintenance','Status'],
                             ['Name','Hostgroups','Templates','Applications'],
                             ['HostID'],
                             ALL)


    # ############################################ 
    # Method update_host_inventory
    # ############################################
    
    def do_update_host_inventory(self,args):
        '''
        DESCRIPTION:
        This command updates one hosts' inventory 

        COMMAND:
        update_host_inventory hostname inventory_key "inventory value"

        Inventory key is not the same as seen in web-gui. To
        look at possible keys and their current values, use 
        "zabbix-cli --use-json-format show_host_inventory <hostname>"  

            
        '''

        result_columns = {}
        result_columns_key = 0

        try: 
            arg_list = shlex.split(args)
            
        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                host = raw_input('# Host: ')
                inventory_key = raw_input('# Inventory key: ')
                inventory_value = raw_input('# Inventory value: ')
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
                return False   

        #
        # Command without inventory_key and inventory value  attributes
        #

        elif len(arg_list) == 1:

            host = arg_list[0]
            inventory_key = raw_input('# Inventory key: ')
            inventory_value = raw_input('# Inventory value: ')

        #
        # Command cithout inventory value attribute
        #
            
        elif len(arg_list) == 2:
            
            host = arg_list[0]
            inventory_key = arg_list[1]
            inventory_value = raw_input('# Inventory value: ')

        elif len(arg_list) == 3:
            
            host = arg_list[0]
            inventory_key = arg_list[1]
            inventory_value = arg_list[2]

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False


        try:
            host_id = str(self.get_host_id(host))

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False
        
        #
        # Generate query
        #

        if host_id == '0':
            self.generate_feedback('Error','Host id for "' + host + '" not found')
            return False

        update_id = "'hostid': '" + host_id +"'"
        update_value = "'inventory':  {'" + inventory_key + "':'" + inventory_value +"'}" 

        try:
          query = ast.literal_eval("{" + update_id + "," + update_value + "}")

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems generating query - %s',e)

            self.generate_feedback('Error','Problems generating query')
            return False

        #
        # Get result from Zabbix API
        #

        try:
            result = self.zapi.host.update(**query)
        
            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_host_inventory executed.')
            
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems updating host inventory information - %s',e)
                
            self.generate_feedback('Error','Problems updating host inventory information')
            return False



    # ############################################
    # Method show_host_inventory
    # ############################################
    
    def do_show_host_inventory(self,args):
        '''
        DESCRIPTION:
        This command shows hosts inventory as json data

        COMMAND:
        show_host [HostID / Hostname]

        [HostID / Hostname]:
        -------------------
        One can search by HostID or by Hostname. We can use wildcards 
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                host = raw_input('# Host: ').strip()
                filter = raw_input('# Filter: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
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
            query=ast.literal_eval("{'output':'extend'," + search_host  + ",'selectInventory':'extend','sortfield':'host','sortorder':'ASC','searchWildcardsEnabled':'True','filter':{" + filter + "}}")
        
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems generating query - %s',e)

            self.generate_feedback('Error','Problems generating query')
            return False

        #
        # Get result from Zabbix API
        #

        try:
            result = self.zapi.host.get(**query)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_host_inventory executed.')
            
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting host inventory information - %s',e)
                
            self.generate_feedback('Error','Problems getting host inventory information')
            return False   

        #
        # Get the columns we want to show from result if the host has
        # some inventory data
        #

        for host in result:

            if host['inventory'] != []:
            
                if self.output_format == 'json':
                    result_columns [result_columns_key] = dict({"host":host['host']}.items() + host['inventory'].items()) 
                
                else:
                    result_columns [result_columns_key] = {'1':host['host'],
                                                           '2':host['inventory']['vendor'],
                                                           '3':host['inventory']['chassis'],
                                                           '4':host['inventory']['macaddress_a'],
                                                           '5':host['inventory']['host_networks'],
                                                           '6':host['inventory']['poc_1_email']}
                
                result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Hostname','Vendor','Chassis','MAC address','Networks','Contact'],
                             ['Hostname','Chassis','MAC address','Contact'],
                             [],
                             FRAME)

        
    # ############################################  
    # Method show_usergroups
    # ############################################  

    def do_show_usergroups(self,args):
        '''
        DESCRIPTION:
        This command shows user groups information.
        
        COMMAND:
        show_usergroups
        '''

        result_columns = {}
        result_columns_key = 0

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.usergroup.get(output='extend',
                                             sortfield='name',
                                             sortorder='ASC',
                                             selectUsers=['alias'])

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_usergroups executed')
                     
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting usergroup information - %s',e)

            self.generate_feedback('Error','Problems getting usergroup information')
            return False   
       
        #
        # Get the columns we want to show from result 
        #
        for group in result:

            if self.output_format == 'json':
                result_columns [result_columns_key] ={'usrgrpid':group['usrgrpid'],
                                                      'name':group['name'],
                                                      'gui_access':self.get_gui_access(int(group['gui_access'])),
                                                      'user_status':self.get_usergroup_status(int(group['users_status'])),
                                                      'users':group['users']}
            
            else:

                users = []

                for user in group['users']:
                    users.append(user['alias'])

                result_columns [result_columns_key] ={'1':group['usrgrpid'],
                                                      '2':group['name'],
                                                      '3':self.get_gui_access(int(group['gui_access'])),
                                                      '4':self.get_usergroup_status(int(group['users_status'])),
                                                      '5':'\n'.join(textwrap.wrap(', '.join(users),60))}
            
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['GroupID','Name','GUI access','Status','Users'],
                             ['Name','Users'],
                             ['GroupID'],
                             FRAME)


    # ############################################  
    # Method show_users
    # ############################################  

    def do_show_users(self,args):
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

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_users executed')
                     
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting users information - %s',e)

            self.generate_feedback('Error','Problems getting users information')
            return False   
       
        #
        # Get the columns we want to show from result 
        #

        for user in result:

            if self.output_format == 'json':
                result_columns [result_columns_key] ={'userid':user['userid'],
                                                      'alias':user['alias'],
                                                      'name':user['name'] + ' ' + user['surname'],
                                                      'autologin':self.get_autologin_type(int(user['autologin'])),
                                                      'autologout':user['autologout'],
                                                      'type':self.get_user_type(int(user['type'])),
                                                      'usrgrps':user['usrgrps']}

            else:
                
                usrgrps = []

                for group in user['usrgrps']:
                    usrgrps.append(group['name'])
                              
                result_columns [result_columns_key] ={'1':user['userid'],
                                                      '2':user['alias'],
                                                      '3':user['name'] + ' ' + user['surname'],
                                                      '4':self.get_autologin_type(int(user['autologin'])),
                                                      '5':user['autologout'],
                                                      '6':self.get_user_type(int(user['type'])),
                                                      '7':'\n'.join(textwrap.wrap(', '.join(usrgrps),60))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['UserID','Alias','Name','Autologin','Autologout','Type','Usrgrps'],
                             ['Name','Type','Usrgrps'],
                             ['UserID'],
                             FRAME)


    # ############################################  
    # Method show_alarms
    # ############################################  

    def do_show_alarms(self,args):
        '''
        DESCRIPTION:
        This command shows all active alarms.

        COMMAND:
        show_alarms
        '''

        result_columns = {}
        result_columns_key = 0

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.trigger.get(only_true=1,
                                           skipDependent=1,
                                           monitored=1,
                                           active=1,
                                           output='extend',
                                           expandDescription=1,
                                           expandData='host',
                                           sortfield='lastchange',
                                           sortorder='DESC')

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Command show_alarms executed')

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting alarm information - %s',e)

            self.generate_feedback('Error','Problems getting alarm information')
            return False   

        #
        # Get the columns we want to show from result 
        #
        for trigger in result:

            lastchange = datetime.datetime.fromtimestamp(int(trigger['lastchange']))
            age = datetime.datetime.now() - lastchange

            if self.output_format == 'json':

                result_columns [result_columns_key] = {'triggerid':trigger['triggerid'],
                                                       'hostname':trigger['hostname'],
                                                       'description':trigger['description'],
                                                       'severity':self.get_trigger_severity(int(trigger['priority'])),
                                                       'lastchange':str(lastchange),
                                                       'age':str(age)}
            
            else:
                
                result_columns [result_columns_key] = {'1':trigger['triggerid'],
                                                       '2':trigger['hostname'],
                                                       '3':trigger['description'],
                                                       '4':self.get_trigger_severity(int(trigger['priority'])),
                                                       '5':str(lastchange),
                                                       '6':str(age)}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['TriggerID','Host','Description','Severity','Last change', 'Age'],
                             ['Host','Description','Last change','Age'],
                             ['TriggerID'],
                             FRAME)


    # ############################################
    # Method do_add_host_to_hostgroup
    # ############################################

    def do_add_host_to_hostgroup(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                hostnames = raw_input('# Hostnames: ').strip()
                hostgroups = raw_input('# Hostgroups: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroups == '':
            self.generate_feedback('Error','Hostgroups information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error','Hostnames information is empty')
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
   
            query=ast.literal_eval("{\"groups\":[" + hostgroup_ids + "],\"hosts\":[" + host_ids + "]}")
   
            #
            # Add hosts to hostgroups
            #

            result = self.zapi.hostgroup.massadd(**query)

            self.generate_feedback('Done','Hosts ' + hostnames + ' (' + host_ids + ') added to these groups: ' + hostgroups + ' (' + hostgroup_ids + ')')

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Hosts: %s (%s) added to these groups: %s (%s)',hostnames,host_ids,hostgroups,hostgroup_ids)

        except Exception as e:

            if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems adding hosts %s (%s) to groups %s (%s) - %s',hostnames,host_ids,hostgroups,hostgroup_ids,e)
           
            self.generate_feedback('Error','Problems adding hosts ' + hostnames + ' (' + host_ids + ') to groups ' + hostgroups + ' (' + hostgroup_ids + ')')
            return False   
            

    # ############################################
    # Method do_remove_host_from_hostgroup
    # ############################################

    def do_remove_host_from_hostgroup(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                hostnames = raw_input('# Hostnames: ').strip()
                hostgroups = raw_input('# Hostgroups: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('ERROR',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroups == '':
            
            self.generate_feedback('Error','Hostgroups information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error','Hostnames information is empty')
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
            query=ast.literal_eval("{\"groupids\":[" + hostgroup_ids + "],\"hostids\":[" + host_ids + "]}")
        
            #
            # Remove hosts from hostgroups
            #
            
            result = self.zapi.hostgroup.massremove(**query)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Hosts: %s (%s) removed from these groups: %s (%s)',hostnames,host_ids,hostgroups,hostgroup_ids)

            self.generate_feedback('Done','Hosts ' + hostnames + ' (' + host_ids + ') removed from these groups: ' + hostgroups + ' (' + hostgroup_ids + ')')

        except Exception as e:
           
            if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems removing hosts %s (%s) from groups %s (%s) - %s',hostnames,host_ids,hostgroups,hostgroup_ids,e)

            self.generate_feedback('Error','Problems removing hosts ' + hostnames + ' (' + host_ids + ') from groups (' + hostgroups + ' (' + hostgroup_ids + ')' )
            return False   


    # ############################################
    # Method do_add_user_to_usergroup
    # ############################################

    def do_add_user_to_usergroup(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                usernames = raw_input('# Usernames: ').strip()
                usergroups = raw_input('# Usergroups: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if usergroups == '':
            
            self.generate_feedback('Error','Usergroups information is empty')
            return False

        if usernames == '':
            self.generate_feedback('Error','Usernames information is empty')
            return False
        
        try:
            
            #
            # Generate users and usergroups IDs
            #
        
            usergroups_list = []
            usernames_list = []
            
            for usergroup in usergroups.split(','):

                if usergroup.isdigit():
                    usergroups_list.append(str(usergroup).strip())
                else:
                    usergroups_list.append(str(self.get_usergroup_id(usergroup.strip())))

            for username in usernames.split(','):

                if username.isdigit():
                    usernames_list.append(str(username).strip())
                else:
                    usernames_list.append(str(self.get_user_id(username.strip())))
        

            #
            # Add users to usergroups
            #

            result = self.zapi.usergroup.massadd(usrgrpids=usergroups_list,userids=usernames_list)

            self.generate_feedback('Done','Users ' + usernames + ' added to these usergroups: ' + usergroups)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Users: %s added to these usergroups: %s',usernames,usergroups)

        except Exception as e:

            if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems adding users %s to usergroups %s - %s',usernames,usergroups,e)
           
            self.generate_feedback('Error','Problems adding users ' + usernames + ' to usergroups ' + usergroups)
            return False   
            

    # ############################################
    # Method do_link_template_to_host
    # ############################################

    def do_link_template_to_host(self,args):
        '''
        DESCRIPTION:
        This command links one/several templates to
        one/several hosts

        COMMAND:
        add_host_to_hostgroup [templates]
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                templates = raw_input('# Templates: ').strip()
                hostnames = raw_input('# Hostnames: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('ERROR',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if templates == '':            
            self.generate_feedback('Error','Templates information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error','Hostnames information is empty')
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

            query=ast.literal_eval("{\"templates\":[" + template_ids + "],\"hosts\":[" + host_ids + "]}")
        
            #
            # Link templates to hosts
            #

            result = self.zapi.template.massadd(**query)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Templates: %s (%s) linked to these hosts: %s (%s)',templates,template_ids,hostnames,host_ids)

            self.generate_feedback('Done','Templates ' + templates + ' (' + template_ids + ') linked to these hosts: ' + hostnames + ' (' + host_ids + ')')

        except Exception as e:

            if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems linking templates %s (%s) to hosts %s (%s) - %s',templates,template_ids,hostnames,host_ids,e)
           
            self.generate_feedback('Error','Problems linking templates ' + templates + ' (' + template_ids + ') to hosts ' + hostnames + ' (' + host_ids + ')')
            return False   


    # ############################################
    # Method do_unlink_template_from_host
    # ############################################

    def do_unlink_template_from_host(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                templates = raw_input('# Templates: ').strip()
                hostnames = raw_input('# Hostnames: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if templates == '':
            self.generate_feedback('Error','Templates information is empty')
            return False

        if hostnames == '':
            self.generate_feedback('Error','Hostnames information is empty')
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
            
            query=ast.literal_eval("{\"templateids\":[" + template_ids + "],\"hostids\":[" + host_ids + "]}")
        
            #
            # Unlink templates from hosts
            #

            result = self.zapi.template.massremove(**query)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Templates: %s (%s) unlinked from these hosts: %s (%s)',templates,template_ids,hostnames,host_ids)

            self.generate_feedback('Done','Templates ' + templates + ' (' + template_ids + ') unlinked from these hosts: ' + hostnames + ' (' + host_ids + ')')

        except Exception as e:
            
            if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems unlinking templates %s (%s) from hosts %s (%s) - %s',templates,template_ids,hostnames,host_ids,e)
           
            self.generate_feedback('Error','Problems unlinking templates ' + templates + ' (' + template_ids + ') from hosts ' + hostnames + ' (' + host_ids + ')')
            return False   
            

    # ############################################
    # Method do_create_usergroup
    # ############################################

    def do_create_usergroup(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                groupname = raw_input('# Name: ').strip()
                gui_access = raw_input('# GUI access ['+ gui_access_default + ']: ').strip()
                users_status = raw_input('# Status ['+ users_status_default + ']: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False


        #
        # Sanity check
        #

        if gui_access == '' or gui_access not in ('0','1','2'):
            gui_access = gui_access_default

        if users_status == '' or users_status not in ('0','1'):
            users_status = users_status_default

        #
        # Check if usergroup exists
        #

        try:
            
            result = self.zapi.usergroup.exists(name=groupname)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Cheking if usergroup (%s) exists',groupname)

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems checking if usergroup (%s) exists - %s',groupname,e)
                
            self.generate_feedback('Error','Problems checking if usergroup (' + groupname + ') exists')
            return False   
        
        #
        # Create usergroup if it does not exist
        #

        try:

            if result == True:
                
                if self.conf.logging == 'ON':
                    self.logs.logger.debug('Usergroup (%s) already exists',groupname)

                self.generate_feedback('Warning','This usergroup (' + groupname + ') already exists.')
                return False   
                
            elif result == False:
                result = self.zapi.usergroup.create(name=groupname,
                                                    gui_access=gui_access,
                                                    users_status=users_status)
                

                if self.conf.logging == 'ON':
                    self.logs.logger.info('Usergroup (%s) with ID: %s created',groupname,str(result['usrgrpids'][0]))

                self.generate_feedback('Done','Usergroup (' + groupname + ') with ID: ' + str(result['usrgrpids'][0]) + ' created.')
        
        except Exception as e:

            if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems creating Usergroup (%s) - %s',groupname,e)

            self.generate_feedback('Error','Problems creating usergroup (' + groupname + ')')
            return False   
            

    # ############################################
    # Method do_create_host
    # ############################################

    def do_create_host(self,args):
        '''
        DESCRIPTION:
        This command creates a host.

        COMMAND:
        create_host [hostname]
                    [hostgroups]
                    [proxy]
                    [status]

        [hostname]
        ----------
        Hostname

        [hostgroups]
        ------------
        Hostgroup names or IDs.
        One can define several values in a comma 
        separated list.

        [proxy]
        -------
        Proxy server used to monitor this host. One can use wildcards
        to define a group of proxy servers from where the system
        will choose a random proxy. 
        Default: random proxy from all proxies defined in the system.

        [Status]
        --------
        0:'Monitored' [*]
        1:'Unmonitored'

        '''
        
        #
        # All host get a default Agent type interface
        # with DNS information
        #
        
        # We use DNS not IP
        interface_ip_default = ''
        
        # This interface is the default one
        interface_main_default = '1'

        # Port used by the interface
        interface_port_default = '10050'

        # Interface type. 1:agent
        interface_type_default = '1'
        
        # Interface connection. 0:DNS
        interface_useip_default = '0'

        # Default hostgroup
        hostgroup_default = self.conf.default_hostgroup.strip()

        # Proxy server to use to monitor this host        
        proxy_default = '*'

        # Default 0: Enable
        host_status_default = '0'

        try: 
            arg_list = shlex.split(args)
            
        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                hostname = raw_input('# Hostname: ').strip()
                hostgroups = raw_input('# Hostgroups[' + hostgroup_default + ']: ').strip()
                proxy = raw_input('# Proxy ['+ proxy_default + ']: ').strip()
                host_status = raw_input('# Status ['+ host_status_default + ']: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
                return False   

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 4:

            hostname = arg_list[0].strip()
            hostgroups = arg_list[1].strip()
            proxy = arg_list[2].strip()
            host_status = arg_list[3].strip()

        #
        # Command with the wrong number of parameters
        #

        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error','Hostname value is empty')
            return False

        if proxy == '':
            proxy = proxy_default

        if host_status == '' or host_status not in ('0','1'):
            host_status = host_status_default

        # Generate interface definition

        interfaces_def = '"interfaces":[{"type":' + interface_type_default + \
                         ',"main":' + interface_main_default + \
                         ',"useip":' + interface_useip_default + \
                         ',"ip":"' + interface_ip_default + \
                         '","dns":"' + hostname + \
                         '","port":"' + interface_port_default + '"}]'

        #
        # Generate hostgroups and proxy IDs
        #

        try:
            hostgroups_list = []
            hostgroup_ids = ''

            hostgroups_list.append('{"groupid":"' + str(self.get_hostgroup_id(hostgroup_default)) + '"}')
            
            for hostgroup in hostgroups.split(','):

                if hostgroup.isdigit():
                    hostgroups_list.append('{"groupid":"' + str(hostgroup).strip() + '"}')
                else:
                    hostgroups_list.append('{"groupid":"' + str(self.get_hostgroup_id(hostgroup.strip())) + '"}')

            hostgroup_ids = ','.join(hostgroups_list)

            proxy_id = str(self.get_random_proxyid(proxy.strip()))
            
        except Exception as e:
 
            if self.conf.logging == 'ON':
                self.logs.logger.error('%s',e)
                
            self.generate_feedback('Error',e)
            return False

        #
        # Checking if hostname exists
        #

        try:
            result = self.zapi.host.exists(name=hostname)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Cheking if host (%s) exists',hostname)

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems checking if host (%s) exists - %s',hostname,e)

            self.generate_feedback('Error','Problems checking if host (' + hostname + ') exists')
            return False   
        
        #
        # Create host if it does not exist
        #

        try:

            if result == True:

                if self.conf.logging == 'ON':
                    self.logs.logger.debug('Host (%s) already exists',hostname)

                self.generate_feedback('Warning','This host (' + hostname + ') already exists.')
                return False   
                
            elif result == False:

                query=ast.literal_eval("{\"host\":\"" + hostname + "\"," + "\"groups\":[" + hostgroup_ids + "]," + "\"proxy_hostid\":\"" + proxy_id + "\"," + "\"status\":" + host_status + "," + interfaces_def + ",\"inventory_mode\":1}")
                
                result = self.zapi.host.create(**query)

                if self.conf.logging == 'ON':
                    self.logs.logger.info('Host (%s) with ID: %s created',hostname,str(result['hostids'][0]))
                
                self.generate_feedback('Done','Host (' + hostname + ') with ID: ' + str(result['hostids'][0]) + ' created')

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems creating host (%s) - %s',hostname,e)

            self.generate_feedback('Error','Problems creating host (' + hostname + ')')
            return False   

            
    # ############################################
    # Method do_remove_host
    # ############################################

    def do_remove_host(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                hostname = raw_input('# Hostname: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error','Hostname value is empty')
            return False

        try:

            #
            # Generate hostnames IDs
            #
        
            if hostname.isdigit() == False:
                hostid = str(self.get_host_id(hostname))
            else:
                hostid = str(hostname)
            
            result = self.zapi.host.delete(hostid)
            
            if self.conf.logging == 'ON':
                self.logs.logger.info('Hosts (%s) with IDs: %s removed',hostname,str(result['hostids'][0]))

            self.generate_feedback('Done','Hosts (' + hostname + ') with IDs: ' + str(result['hostids'][0]) + ' removed')

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems removing hosts (%s) - %s',hostname,e)

            self.generate_feedback('Error','Problems removing hosts (' + hostname + ')')
            return False   
            

    # ############################################
    # Method do_create_user
    # ############################################

    def do_create_user(self,args):
        '''
        DESCRIPTION:
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
        User groups ID

        '''
        
        # Default: md5 value of a random int >1 and <1000000 
        x = hashlib.md5()
        x.update(str(random.randint(1,1000000)))
        passwd_default = x.hexdigest()
        
        # Default: 1: Zabbix user
        type_default = '1'

        # Default: 0: Disable
        autologin_default = '0'

        # Default: 1 day: 86400s
        autologout_default = '86400'

        try: 
            arg_list = shlex.split(args)
            
        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:

            try:
                print '--------------------------------------------------------'
                alias = raw_input('# Alias []: ').strip()
                name = raw_input('# Name []: ').strip()
                surname = raw_input('# Surname []: ').strip()
                passwd = raw_input('# Password []: ').strip()
                type = raw_input('# User type [' + type_default + ']: ').strip()
                autologin = raw_input('# Autologin [' + autologin_default + ']: ').strip()
                autologout = raw_input('# Autologout [' + autologout_default + ']: ').strip()
                usrgrps = raw_input('# Usergroups []: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if alias == '':
            self.generate_feedback('Error','User Alias is empty')
            return False

        if passwd == '':
            passwd = passwd_default

        if type == '' or type not in ('1','2','3'):
            type = type_default

        if autologin == '':
            autologin = autologin_default

        if autologout == '':
            autologout = autologout_default
        
        if usrgrps == '':
            self.generate_feedback('Error','Group list is empty')
            return False

        #
        # Check if user exists
        #

        try:
            
            result = self.zapi.user.get(search={'alias':alias},output='extend',searchWildcardsEnabled=True)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Checking if user (%s) exists',alias)

        except Exception as e:
            
            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems checking if user (%s) exists - %s',alias,e)

            self.generate_feedback('Error','Problems checking if user (' + alias + ') exists')
            return False   

        #
        # Create user
        #

        try:

            if result != []:

                if self.conf.logging == 'ON':
                    self.logs.logger.debug('This user (%s) already exists',alias)

                self.generate_feedback('Warning','This user (' + alias + ') already exists.')
                return False   
                
            else:
                result = self.zapi.user.create(alias=alias,
                                               name=name,
                                               surname=surname,
                                               passwd=passwd,
                                               type=type,
                                               autologin=autologin,
                                               autologout=autologout,
                                               usrgrps=usrgrps.strip().split(','))
                
                if self.conf.logging == 'ON':
                    self.logs.logger.info('User (%s) with ID: %s created',alias,str(result['userids'][0]))
                
                self.generate_feedback('Done','User (' + alias + ') with ID: ' + str(result['userids'][0]) + ' created.')

        except Exception as e:
            
            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems creating user (%s) - %s',alias,e)

            self.generate_feedback('Error','Problems creating user (' + alias + ')')
            return False   

            
    # ############################################
    # Method do_create_hostgroup
    # ############################################

    def do_create_hostgroup(self, args):
        '''
        DESCRIPTION:
        This command creates a hostgroup
    
        COMMAND:
        create_hostgroup [hostgroup]

        '''

        # Default values
        admin_usergroup_default = self.conf.default_admin_usergroup

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                hostgroup = raw_input('# Name: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
                return False

        elif len(arg_list) == 1:
            hostgroup = arg_list[0].strip()
        
        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostgroup == '':
            self.generate_feedback('Error','Hostgroup value is empty')
            return False

        #
        # Checking if hostgroup exists
        #

        try:
            
            result = self.zapi.hostgroup.exists(name=hostgroup)

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Cheking if hostgroup (%s) exists',hostgroup)

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems checking if hostgroup (%s) exists - %s',hostgroup,e)

            self.generate_feedback('Error','Problems checking if hostgroup (' + hostgroup + ') exists')
            return False   
        
        try:

            #
            # Create hostgroup if it does not exist
            #
            
            if result == False:

                data = self.zapi.hostgroup.create(name=hostgroup)
                hostgroupid = data['groupids'][0]
                
                if self.conf.logging == 'ON':
                    self.logs.logger.info('Hostgroup (%s) with ID: %s created',hostgroup,hostgroupid)

                self.generate_feedback('Done','Hostgroup (' + hostgroup + ') with ID: ' + hostgroupid + ' created.')

                
                #
                # Give RW access to the new group to the default admin usergroup
                # defined in zabbix-cli.conf
                #

                try:
                    usrgrpid = self.get_usergroup_id(admin_usergroup_default)

                    result = self.zapi.usergroup.massadd(usrgrpids=[usrgrpid],rights={'id':hostgroupid,'permission':3})
                    
                    if self.conf.logging == 'ON':
                        self.logs.logger.debug('Admin usergroup (%s) has got RW permissions on hostgroup (%s) ',admin_usergroup_default,hostgroup)
                        
                except Exception as e:

                    if self.conf.logging == 'ON':
                        self.logs.logger.error('Problems giving the admin usergroup %s RW access to %s - %s',admin_usergroup_default,hostgroup,e)
            
                    self.generate_feedback('Error','Problems giving the admin usergroup ' + admin_usergroup_default +' RW access to ' + hostgroup)
                    return False 
            else:

                if self.conf.logging == 'ON':
                    self.logs.logger.debug('This hostgroup (%s) already exists',hostgroup)

                self.generate_feedback('Warning','This hostgroup (' + hostgroup + ') already exists.')
                return False

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems creating hostgroup (%s) - %s',hostgroup,e)
            
            self.generate_feedback('Error','Problems creating hostgroup (' + hostgroup + ')')
            return False 


    # ############################################
    # Method do_define_global_macro
    # ############################################

    def do_define_global_macro(self, args):
        '''
        DESCRIPTION:
        This command defines a global macro
    
        COMMAND:
        define_global_macro [macro name]
                            [macro value]

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                global_macro_name = raw_input('# Global macro name: ').strip()
                global_macro_value = raw_input('# Global macro value: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
                return False

        elif len(arg_list) == 1:
            global_macro_name = arg_list[0].strip()
            global_macro_value = arg_list[1].strip()
        
        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if global_macro_name == '':
            self.generate_feedback('Error','Global macro name is empty')
            return False
        
        else:
            global_macro_name = '{$' + global_macro_name.upper() + '}'

        if global_macro_value == '':
            self.generate_feedback('Error','Global macro value is empty')
            return False

        #
        # Checking if global macro exists
        #

        try:
            
            result = self.zapi.usermacro.get(search={'macro':global_macro_name},
                                             globalmacro=True,
                                             output='extend')

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Cheking if global macro (%s) exists',global_macro_name)
                
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems checking if global macro (%s) exists - %s',global_macro_name,e)

            self.generate_feedback('Error','Problems checking if global macro (' + global_macro_name + ') exists')
            return False   
        
        try:

            #
            # Create/update global macro if it does not exist
            #
            
            if result == []:

                data = self.zapi.usermacro.createglobal(macro=global_macro_name,value=global_macro_value)
                globalmacroid = data['globalmacroids'][0]
                
                if self.conf.logging == 'ON':
                    self.logs.logger.info('Global macro (%s) with ID: %s created',global_macro_name,globalmacroid)

                self.generate_feedback('Done','Global macro (' + global_macro_name + ') with ID: ' + globalmacroid + ' created.')

            else:
                data = self.zapi.usermacro.updateglobal(globalmacroid=result[0]['globalmacroid'],
                                                        value=global_macro_value)

                if self.conf.logging == 'ON':
                    self.logs.logger.info('Global macro (%s) already exists. Value (%s) updated to (%s)',global_macro_name,result[0]['value'],global_macro_value)

                self.generate_feedback('Done','Global macro (' + global_macro_name + ') already exists. Value (' + result[0]['value'] + ') updated to (' + global_macro_value + ')')
                return False

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems defining global macro (%s) - %s',global_macro_name,e)
            
            self.generate_feedback('Error','Problems defining global macro (' + global_macro_name + ')')
            return False 


    # ############################################
    # Method do_define_host_macro
    # ############################################

    def do_define_host_macro(self, args):
        '''
        DESCRIPTION:
        This command defines a host macro
    
        COMMAND:
        defines_host_macro [hostname] 
                           [macro name]
                           [macro value]

        '''

        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                hostname = raw_input('# Hostname: ').strip()
                host_macro_name = raw_input('# Macro name: ').strip()
                host_macro_value = raw_input('# Macro value: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
                return False

        elif len(arg_list) == 1:
            hostname = arg_list[0].strip()
            host_macro_name = arg_list[1].strip()
            host_macro_value = arg_list[2].strip()
        
        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        
        if host_macro_name == '':
            self.generate_feedback('Error','Host macro name is empty')
            return False
        
        else:
            host_macro_name = '{$' + host_macro_name.upper() + '}'

        if host_macro_value == '':
            self.generate_feedback('Error','Host macro value is empty')
            return False

        if hostname == '':
            self.generate_feedback('Error','Hostname is empty')
            return False

        if hostname.isdigit() == True:
            hostid = hostname
        else:
            try:
                hostid = self.get_host_id(hostname.strip())
            
            except Exception as e:
                if self.conf.logging == 'ON':
                    self.logs.logger.info('Hostname %s does not exist',hostname)

                self.generate_feedback('Error','Hostname ' + hostname + ' does not exist')
                return False
                

        #
        # Checking if host macro exists
        #

        try:
            
            result = self.zapi.usermacro.get(search={'macro':host_macro_name},
                                             hostids=hostid,
                                             output='extend')

            if self.conf.logging == 'ON':
                self.logs.logger.debug('Cheking if host macro (%s:%s) exists',hostname,host_macro_name)
                
        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems checking if host macro (%s:%s) exists - %s',hostname,host_macro_name,e)

            self.generate_feedback('Error','Problems checking if host macro (' + hostname + ':' + host_macro_name + ') exists')
            return False   
        
        try:

            #
            # Create / update host macro if it does not exist
            #
            
            if result == []:

                data = self.zapi.usermacro.create(hostid=hostid,
                                                  macro=host_macro_name,
                                                  value=host_macro_value)
                
                hostmacroid = data['hostmacroids'][0]
                
                if self.conf.logging == 'ON':
                    self.logs.logger.info('Host macro (%s:%s) with ID: %s created',hostname,host_macro_name,hostmacroid)

                self.generate_feedback('Done','Host macro (' + hostname + ':' + host_macro_name + ') with ID: ' + hostmacroid + ' created.')

            else:
                
                data = self.zapi.usermacro.update(hostmacroid=result[0]['hostmacroid'],
                                                  value=host_macro_value)
                
                if self.conf.logging == 'ON':
                    self.logs.logger.debug('Host macro (%s:%s) already exists. Value (%s) updated to (%s)',hostname,host_macro_name,result[0]['value'],host_macro_value)

                self.generate_feedback('Done','Host macro (' + hostname + ':' + host_macro_name + ') already exists. Value (' + result[0]['value'] + ') updated to (' + host_macro_value+ ')')
                return False

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems defining host macro (%s:%s) - %s',hostname,host_macro_name,e)
            
            self.generate_feedback('Error','Problems defining host macro (' + hostname + ':' + global_macro_name + ')')
            return False 



    # ############################################                                                                                                                                    
    # Method show_templates
    # ############################################

    def do_show_templates(self,args):
        '''
        DESCRIPTION:
        This command shows all templates defined in the system.

        COMMAND:
        show_templates
        '''

        cmd.Cmd.onecmd(self,'show_template "*"')


    # ########################################
    # do_show_template
    # ########################################
    
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                template = raw_input('# Template: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if template == '':
            self.generate_feedback('Error','Template value is empty')
            return False

        #
        # Get template 
        #
            
        try:
            result = self.zapi.template.get(output='extend',
                                            search={'host':template},
                                            searchWildcardsEnabled=True,
                                            sortfield='host',
                                            selectHosts=['host'],
                                            sortorder='ASC')

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting the template list - %s',e)

            self.generate_feedback('Error','Problems getting the template list')
            return False
        
        #
        # Get the columns we want to show from result 
        #

        for template in result:
            
            if self.output_format == 'json':
                result_columns [result_columns_key] ={'templateid':template['templateid'],
                                                      'name':template['host'],
                                                      'hosts':template['hosts']}
            
            else:

                host_list = []
                template['hosts'].sort()
                
                for host in template['hosts']:
                    host_list.append(host['host'])

                result_columns [result_columns_key] ={'1':template['templateid'],
                                                      '2':template['host'],
                                                      '3':'\n'.join(host_list)}
            
                
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['TemplateID','Name','Hosts'],
                             ['Name','Hosts'],
                             ['TemplateID'],
                             ALL)


    # ########################################
    # do_show_global_macros 
    # ########################################
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

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting globalmacros list - %s',e)
                
            self.generate_feedback('Error','Problems getting globalmacros list')
            return False

        #
        # Get the columns we want to show from result 
        #

        for global_macro in result:

            if self.output_format == 'json':
                result_columns [result_columns_key] ={'globalmacroid':global_macro['globalmacroid'],
                                                      'name':global_macro['macro'],
                                                      'value':global_macro['value']}

            else:
                result_columns [result_columns_key] ={'1':global_macro['globalmacroid'],
                                                      '2':global_macro['macro'],
                                                      '3':global_macro['value']}
                
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['MacroID','Name','Value'],
                             ['Name','Value'],
                             ['MacroID'],
                             FRAME)


    # ########################################
    # do_show_host_macros 
    # ########################################
    def do_show_host_macros(self, args):
        '''
        DESCRITION:
        This command shows host macros

        COMMAND:
        show_host_macros [hostname]
        '''

        result_columns = {}
        result_columns_key = 0


        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                hostname = raw_input('# Hostname: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
                return False

        elif len(arg_list) == 1:
            hostname = arg_list[0].strip()
        
        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if hostname == '':
            self.generate_feedback('Error','Hostname is empty')
            return False

        if hostname.isdigit() == True:
            hostid = hostname
        else:
            try:
                hostid = self.get_host_id(hostname.strip())
            
            except Exception as e:
                if self.conf.logging == 'ON':
                    self.logs.logger.info('Hostname %s does not exist',hostname)

                self.generate_feedback('Error','Hostname ' + hostname + ' does not exist')
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

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting globalmacros list - %s',e)
                
            self.generate_feedback('Error','Problems getting globalmacros list')
            return False

        #
        # Get the columns we want to show from result 
        #

        for host_macro in result:

            if self.output_format == 'json':
                result_columns [result_columns_key] ={'hostmacroid':host_macro['hostmacroid'],
                                                      'name':host_macro['macro'],
                                                      'value':host_macro['value']}

            else:
                result_columns [result_columns_key] ={'1':host_macro['hostmacroid'],
                                                      '2':host_macro['macro'],
                                                      '3':host_macro['value']}
                
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['MacroID','Name','Value'],
                             ['Name','Value'],
                             ['MacroID'],
                             FRAME)


    # ########################################
    # do_show_macro_hostlist 
    # ########################################
    def do_show_macro_hostlist(self, args):
        '''
        DESCRITION:
        This command shows all host with a defined macro

        COMMAND:
        show_macro_hostlist [macro name]
        '''

        result_columns = {}
        result_columns_key = 0


        try:
            arg_list = shlex.split(args)

        except ValueError as e:
            print '\n[ERROR]: ',e,'\n'
            return False

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                host_macro_name= raw_input('# Host macro name: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
                return False

        elif len(arg_list) == 1:
            host_macro_name = arg_list[0].strip()
        
        else:
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #
        
        if host_macro_name == '':
            self.generate_feedback('Error','Host macro name is empty')
            return False
        
        else:
            host_macro_name = '{$' + host_macro_name.upper() + '}'


        #
        # Get macro hostlist
        #

        try:
            result = self.zapi.usermacro.get(output='extend',
                                             selectHosts=['host'],
                                             search={'macro':host_macro_name},
                                             searchWildcardsEnabled=True,
                                             sortfield='macro')

        except Exception as e:

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting host list for macro %s - %s',host_macro_name,e)
                
            self.generate_feedback('Error','Problems getting host list for macro ' + host_macro_name)
            return False

        #
        # Get the columns we want to show from result 
        #


        for macro in result:

            if self.output_format == 'json':
                result_columns [result_columns_key] ={'macro':macro['macro'],
                                                      'value':macro['value'],
                                                      'hostid':macro['hosts'][0]['hostid'],
                                                      'host':macro['hosts'][0]['host']}


            else:

                result_columns [result_columns_key] ={'1':macro['macro'],
                                                      '2':macro['value'],
                                                      '3':macro['hosts'][0]['hostid'],
                                                      '4':macro['hosts'][0]['host']}
                
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['Macro','Value','HostID','Host'],
                             ['Macro','Host'],
                             ['HostID'],
                             FRAME)



    # #######################################
    # do_show_items
    # #######################################
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                template = raw_input('# Template: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if template == '':
            self.generate_feedback('Error','Template value is empty')
            return False

        #
        # Getting template ID
        #

        if template.isdigit() == False:

            try:
                templateid = self.get_template_id(template)
            
            except Exception as e:

                if self.conf.logging == 'ON':
                    self.logs.logger.error('%s',e)
                    
                self.generate_feedback('Error',e)
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

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting items list for template (%s) - %s',template,e)

            self.generate_feedback('Error','Problems getting items list for template (' + template + ')')
            return False

        #
        # Get the columns we want to show from result 
        #
        
        for item in result:
                
            if self.output_format == 'json':
                result_columns [result_columns_key] ={'itemid':item['itemid'],
                                                      'name':item['name'],
                                                      'key':item['key_'],
                                                      'type':self.get_item_type(int(item['type'])),
                                                      'interval':item['delay'],
                                                      'history':item['history'],
                                                      'description':'\n'.join(textwrap.wrap(item['description'],60))}
            else:
                result_columns [result_columns_key] ={'1':item['itemid'],
                                                      '2':item['name'],
                                                      '3':item['key_'],
                                                      '4':self.get_item_type(int(item['type'])),
                                                      '5':item['delay'],
                                                      '6':item['history'],
                                                      '7':'\n'.join(textwrap.wrap(item['description'],60))}

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['ItemID','Name','Key','Type','Interval','History','Description'],
                             ['Name','Name','Key','Description'],
                             ['ItemID'],
                             FRAME)
        


    # ##########################################
    # do_show_triggers
    # ##########################################

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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                template = raw_input('# Template: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if template == '':
            self.generate_feedback('Error','Template value is empty')
            return False

        #
        # Getting template ID
        #

        if template.isdigit() == False:

            try:
                templateid = self.get_template_id(template)
            
            except Exception as e:

                if self.conf.logging == 'ON':
                    self.logs.logger.error('Problems getting templateID - %s',e)

                self.generate_feedback('Error','Problems getting templateID')
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
            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems getting trigger list for template (%s) - %s',template,e)

            self.generate_feedback('Error','Problems getting trigger list for template (' + template + ')')
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
                    result_columns [result_columns_key] = {'triggerid':data['triggerid'],
                                                           'expression':data['expression'],
                                                           'description':data['description'],
                                                           'priority':self.get_trigger_severity(int(data['priority'])),
                                                           'status':self.get_trigger_status(int(data['status']))}
                
                else:
                    result_columns [result_columns_key] = {'1':data['triggerid'],
                                                           '2':data['expression'],
                                                           '3':data['description'],
                                                           '4':self.get_trigger_severity(int(data['priority'])),
                                                           '5':self.get_trigger_status(int(data['status']))}

                result_columns_key = result_columns_key + 1
                
        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['TriggerID','Expression','Description','Priority','Status'],
                             ['Expression','Description'],
                             ['TriggerID'],
                             FRAME)



    # ############################################
    # Method export_configuration
    # ############################################

    def do_export_configuration(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                directory_exports = raw_input('# Directory [' + self.conf.default_directory_exports + ']: ').strip()
                object_type = raw_input('# Object type [' + default_object_type + ']: ').strip().lower()
                object_name = raw_input('# Object name [' + default_object_name + ']: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        if directory_exports == '':
            directory_exports = self.conf.default_directory_exports

        
        for obj_type in object_type_list:
        
            if os.path.exists(directory_exports + '/' + obj_type) == False:

                try:
                    os.makedirs(directory_exports + '/' + obj_type,0700)

                    if self.conf.logging == 'ON':
                        self.logs.logger.info('Export directory created: %s',directory_exports + '/' + obj_type)
                
                except OSError as e:

                    if self.conf.logging == 'ON':
                        self.logs.logger.error('OS error when creating export directory %s - %s',directory_exports + '/' + obj_type,e)

                    self.generate_feedback('Error','OS error when creating export directory ' + directory_exports + '/' + obj_type)
                    return False

        if object_type == '':
            object_type = default_object_type

        if object_type not in object_type_list + ['#all#']:
            self.generate_feedback('Error','Object type is not a valid value')
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

                    if self.conf.logging == 'ON':
                        self.logs.logger.error('Problems getting all [%s] objects - %s',obj_type,e)
                        
                    self.generate_feedback('Error','Problems getting all [' + obj_type + '] objects')
                    return False
             
            #
            # Generate object IDs list to export for all defined
            # object names.
            #
   
            else:
                for name in object_name.split(','):
                    
                    if name.strip().isdigit() == True and name.strip() != '':
                        object_name_list[str(name).strip()] = str(name).strip()

                    elif name.strip().isdigit() == False and name.strip() != '':
    
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

                            if self.conf.logging == 'ON':
                                self.logs.logger.error('Problems getting ID for object type [%s] and object name [%s] - %s',obj_type,name,e)

                            self.generate_feedback('Error','Problems getting ID for object type [' + obj_type + '] and object name [' + name + ']')
                            return False

            
            #
            # Generate export files for all defined object names
            #
                                         
            for obj_name_key in object_name_list.keys():

                try:
                    data = self.zapi.configuration.export(format=self.conf.default_export_format.lower(), 
                                                          options={obj_type:[obj_name_key]})

                    #
                    # Formating and indenting the export data 
                    #

                    if self.conf.default_export_format.upper() == 'JSON':
                        output= json.dumps(json.JSONDecoder().decode(data),sort_keys=True,indent=2)
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

                    filename = self.generate_export_filename(directory_exports,obj_type,obj_name_key,object_name_list[obj_name_key])
                    
                    with open(filename,'w') as export_filename:
                        export_filename.write(output)

                    if self.conf.logging == 'ON':
                        self.logs.logger.info('Export file/s for object type [%s] and object name [%s] generated',obj_type,object_name_list[obj_name_key])

                except Exception as e:
                    
                    if self.conf.logging == 'ON':
                        self.logs.logger.error('Problems generating export file for object type [%s] and object name [%s] - %s',obj_type,object_name_list[obj_name_key],e)
                        
                    self.generate_feedback('Error','Problems generating export file for object type [' + obj_type+ '] and object name [' + object_name_list[obj_name_key] + ']')
                    return False

        if self.conf.logging == 'ON':
            self.logs.logger.info('Export file/s for object type [%s] and object name [%s] generated',object_type,object_name)
            
        self.generate_feedback('Done','Export file/s for object type [' + object_type+ '] and object name [' + object_name + '] generated')
 

    # ############################################
    # Method import_configuration
    # ############################################

    def do_import_configuration(self,args):
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
            print '\n[ERROR]: ',e,'\n'
            return False

        #
        # Command without parameters
        #

        if len(arg_list) == 0:
            try:
                print '--------------------------------------------------------'
                files = raw_input('# Import file []: ').strip()
                dry_run = raw_input('# Dry run [' + dry_run_default + ']: ').strip()
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------'
                print '\n[Aborted] Command interrupted by the user.\n'
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
            self.generate_feedback('Error',' Wrong number of parameters used.\n          Type help or \? to list commands')
            return False

        #
        # Sanity check
        #

        files_orig = files

        if files == '':
            self.generate_feedback('Error','Files value is empty')
            return False

        if dry_run == '' or dry_run not in ('0','1'):
            dry_run = dry_run_default

        #
        # Expand users HOME when using ~ or ~user
        #
        files = os.path.expanduser(files)

        # Normalized absolutized version of the pathname if
        # files does not include an absolute path

        if os.path.isabs(files) == False:
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
            if self.conf.logging == 'ON':
                self.logs.logger.error('Files %s do not exists',files)

                
        if dry_run == '1':
                        
            #
            # Dry run. Show files that would be imported
            # without running the import process.
            #
            
            print 
            print '# -----------------------------------------------'
            print '# Dry run: ON'
            print '# These files would be imported with dry run: OFF'
            print '# -----------------------------------------------'
            print

        for file in expanded_files:
            if os.path.exists(file):
                if os.path.isfile(file):

                    file_ext = os.path.splitext(file)[1]

                    if file_ext.lower() == '.json':
                        format = 'json'
                    elif file_ext.lower() == '.xml':
                        format = 'xml'
                    else:
                        total_files_not_imported = total_files_not_imported +1
                        
                        if self.conf.logging == 'ON':
                            self.logs.logger.error('The file %s is not a JSON or XML file',file)
                            
                        # Get the next file if this one is not a JSON or XML file 
                        continue

                    if dry_run == '1':
                        
                        #
                        # Dry run. Show files that would be imported
                        # without running the import process.
                        #

                        print '# File: ' + file

                    elif dry_run == '0':
                    
                        #
                        # Import the file
                        #

                        try:
                            with open(file,'r') as import_filename:
                                import_data = import_filename.read()
                        
                                data = self.zapi.confimport(format=format,
                                                            source=import_data,
                                                            rules={
                                                                'applications':{'createMissing':'true','updateExisting':'true'},
                                                                'discoveryRules':{'createMissing':'true','updateExisting':'true'},
                                                                'graphs':{'createMissing':'true','updateExisting':'true'},
                                                                'groups':{'createMissing':'true'},
                                                                'hosts':{'createMissing':'true','updateExisting':'true'},
                                                                'images':{'createMissing':'true','updateExisting':'true'},
                                                                'items':{'createMissing':'true','updateExisting':'true'},
                                                                'maps':{'createMissing':'true','updateExisting':'true'},
                                                                'screens':{'createMissing':'true','updateExisting':'true'},
                                                                'templateLinkage':{'createMissing':'true'},
                                                                'templates':{'createMissing':'true','updateExisting':'true'},
                                                                'templateScreens':{'createMissing':'true','updateExisting':'true'},
                                                                'triggers':{'createMissing':'true','updateExisting':'true'}
                                                            })    
                                
                                if data == True:
                            
                                    total_files_imported = total_files_imported + 1
                                    
                                    if self.conf.logging == 'ON':
                                        self.logs.logger.info('The file %s has been imported into Zabbix',file)
    
                                elif data == False:

                                    total_files_not_imported = total_files_not_imported +1

                                    if self.conf.logging == 'ON':
                                        self.logs.logger.info('The file %s could not been imported into Zabbix',file)

                        except Exception as e:

                            total_files_not_imported = total_files_not_imported + 1

                            if self.conf.logging == 'ON':
                                self.logs.logger.error('The file %s could not be imported into Zabbix - %s',file,e)
            else:
                if self.conf.logging == 'ON':
                    self.logs.logger.error('The file %s does not exists',file)
              
        self.generate_feedback('done','Total files Imported ['+ str(total_files_imported) +'] / Not imported [' + str(total_files_not_imported) +']')
            

    # ############################################
    # Method generate_export_filename
    # ############################################
    def generate_export_filename(self,directory_exports,obj_type, obj_id, obj_name):
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

        filename = directory_exports + '/' + obj_type + '/zabbix_export_' + obj_type + '_' + obj_name.replace(' ','_') + '_' + obj_id + timestamp + '.' + file_ext
        return filename


    # ############################################
    # Method get_trigger_severity
    # ############################################
    
    def get_trigger_severity(self,code):
        '''
        Get trigger severity from code
        '''

        trigger_severity = {0:'Not classified',1:'Information',2:'Warning',3:'Average',4:'High',5:'Disaster'}

        if code in trigger_severity:
            return trigger_severity[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_trigger_status
    # ############################################
    
    def get_trigger_status(self,code):
        '''
        Get trigger status from code
        '''

        trigger_status = {0:'Enable',1:'Disable'}

        if code in trigger_status:
            return trigger_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_maintenance_status
    # ############################################
    
    def get_maintenance_status(self,code):
        '''
        Get maintenance status from code
        '''

        maintenance_status = {0:'No maintenance',1:'In progress'}

        if code in maintenance_status:
            return maintenance_status[code]  + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"

    
    # ############################################
    # Method get_monitoring_status
    # ############################################
    
    def get_monitoring_status(self,code):
        '''
        Get monitoring status from code
        '''

        monitoring_status = {0:'Monitored',1:'Not monitored'}

        if code in monitoring_status:
            return monitoring_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_monitoring_status
    # ############################################
    
    def get_zabbix_agent_status(self,code):
        '''
        Get zabbix agent status from code
        '''

        zabbix_agent_status = {1:'Available',2:'Unavailable'}

        if code in zabbix_agent_status:
            return zabbix_agent_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_gui_access
    # ############################################
    
    def get_gui_access(self,code):
        '''
        Get GUI access from code
        '''

        gui_access = {0:'System default',1:'Internal',2:'Disable'}

        if code in gui_access:
            return gui_access[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"

    # ############################################
    # Method get_usergroup_status
    # ############################################
    
    def get_usergroup_status(self,code):
        '''
        Get usergroup status from code
        '''

        usergroup_status = {0:'Enable',1:'Disable'}

        if code in usergroup_status:
            return usergroup_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_hostgroup_flag
    # ############################################
    
    def get_hostgroup_flag(self,code):
        '''
        Get hostgroup flag from code
        '''

        hostgroup_flag = {0:'Plain',4:'Discover'}

        if code in hostgroup_flag:
            return hostgroup_flag[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_hostgroup_type
    # ############################################
    
    def get_hostgroup_type(self,code):
        '''
        Get hostgroup type from code
        '''

        hostgroup_type = {0:'Not internal',1:'Internal'}

        if code in hostgroup_type:
            return hostgroup_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_user_type
    # ############################################
    
    def get_user_type(self,code):
        '''
        Get user type from code
        '''

        user_type = {1:'User',2:'Admin',3:'Super admin'}

        if code in user_type:
            return user_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_autologin_type
    # ############################################
    
    def get_autologin_type(self,code):
        '''
        Get autologin type from code
        '''

        autologin_type = {0:'Disable',1:'Enable'}

        if code in autologin_type:
            return autologin_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_item_type
    # ############################################
    
    def get_item_type(self,code):
        '''
        Get item type from code
        '''
        item_type = {0:'Zabbix agent',
                     1:'SNMPv1 agent',
                     2:'Zabbix trapper',
                     3:'simple check',
                     4:'SNMPv2 agent',
                     5:'Zabbix internal',
                     6:'SNMPv3 agent',
                     7:'Zabbix agent (active)',
                     8:'Zabbix aggregate',
                     9:'web item',
                     10:'external check',
                     11:'database monitor',
                     12:'IPMI agent',
                     13:'SSH agent',
                     14:'TELNET agent',
                     15:'calculated',
                     16:'JMX agent',
                     17:'SNMP trap'}
        
        if code in item_type:
            return item_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method generate_output
    # ############################################

    def generate_output(self,result,colnames,left_col,right_col,hrules):
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

                    for column in sorted(result[records]):
                        columns.append(result[records][column])
                    
                    x.add_row(columns)
            
                print x.get_string()
                print

            elif self.output_format == 'csv':

                print ",".join(colnames)

                for records in result:
                    columns = []

                    for column in sorted(result[records]):
                        columns.append(result[records][column])

                    print '"' +  '","'.join(columns) + '"'
             
            elif self.output_format == 'json':
                
                print json.dumps(result,sort_keys=True,indent=2)

        except Exception as e: 
            print '\n[Error] Problems generating the output ',e

            if self.conf.logging == 'ON':
                self.logs.logger.error('Problems generating the output')


    # ############################################
    # Method generate_feedback
    # ############################################

    def generate_feedback(self,return_code,message):
        '''
        Generate feedback messages
        '''
        
        if self.output_format == 'table':
            print '\n[' + return_code.title() + ']: ' + str(message) + '\n'   
            print 

        elif self.output_format == 'csv':
            print '"' + return_code.lower() + '","' + str(message) + '"\n'   
            
            if return_code.lower() == 'done':
                sys.exit(0)
            elif return_code.lower() == 'error':
                sys.exit(1)
    
        elif self.output_format == 'json':
            output = {"return_code":return_code.lower(),"message":str(message)}
            print json.dumps(output,sort_keys=True,indent=2)

            if return_code.lower() == 'done':
                sys.exit(0)
            elif return_code.lower() == 'error':
                sys.exit(1)


    # ############################################
    # Method do_clear
    # ############################################

    def do_clear(self,args):
        '''
        DESCRIPTION: 
        Clears the screen and shows the welcome banner.

        COMMAND: 
        clear
        
        '''
        
        os.system('clear')
        print self.intro


    # ############################################
    # Method default
    # ############################################

    def default(self,line):
        self.generate_feedback('Error',' Unknown command: %s.\n          Type help or \? to list commands' % line)


    # ############################################
    # Method emptyline
    # ############################################

    def emptyline(self):
        pass


    # ############################################
    # Method precmd
    # ############################################

    def precmd(self, line_in):

        if line_in != '':
            split_line = line_in.split()
            
            if split_line[0] not in ['EOF','shell','SHELL','\!']:
                line_out = split_line[0].lower() + ' ' + ' '.join(split_line[1:])
            else:
                line_out = line_in

            if split_line[0] == '\h ':
                line_out = line_out.replace('\h','help')
            elif split_line[0] == '\? ':
                line_out = line_out.replace('\?','help')
            elif split_line[0] == '\! ':
                line_out = line_out.replace('\!','shell')
            elif line_out == '\s ':
                line_out = 'show_history'    
            elif line_out == '\q ':
                line_out = 'quit' 

            self._hist += [ line_out.strip() ]
          
        else:
            line_out = ''
       
        return cmd.Cmd.precmd(self, line_out)


    # ############################################
    # Method do_shell
    # ############################################

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
            proc = subprocess.Popen([line],stdout=subprocess.PIPE,stderr=subprocess.PIPE,shell=True)
            output, errors = proc.communicate()
            print output,errors
            print

        except Exception as e:
            self.generate_feedback('Error','Problems running %s' % line)


    # ############################################
    # Method do_quit
    # ############################################

    def do_quit(self, args):
        '''
        DESCRIPTION: 
        Quits/terminate the Zabbix-CLI shell.

        COMMAND: 
        quit
        
        '''
        
        print '\nDone, thank you for using Zabbix-CLI'
        return True


    # ############################################
    # Method do_EOF
    # ############################################

    def do_EOF(self, line):
        '''
        DESCRIPTION: 
        Quit/terminate the Zabbix-CLI shell.

        COMMAND: 
        EOF
        
        '''

        print
        print '\nDone, thank you for using Zabbix-CLI'
        return True


    # ############################################
    # Method do_hist
    # ############################################

    def do_show_history(self, args):
        '''
        DESCRIPTION: 
        This command shows the list of commands that have been entered
        during the Zabbix-CLI shell session.

        COMMAND: 
        show_history

        '''

        cnt = 0
        print

        for line in self._hist:
            print '[' + str(cnt) + ']: ' + line
            cnt = cnt +1

        print


    # ########################################################
    # Method get_hostgroupid
    # ########################################################

    def get_hostgroup_id(self, hostgroup):
        '''
        DESCRIPTION:
        Get the hostgroup_id for a hostgroup
        '''

        try:
            data = self.zapi.hostgroup.get(output='extend', filter={'name':hostgroup})
            
            if data != []:
                hostgroupid = data[0]['groupid']
            else:
                raise Exception('Could not find hostgroupID for: ' + hostgroup)

        except Exception as e:
            raise e

        return str(hostgroupid)


    # #################################################
    # Method get_host_id
    # #################################################
    
    def get_host_id(self, host):
        '''
        DESCRIPTION:
        Get the hostid for a host
        '''

        try:
            data = self.zapi.host.get(output='extend', filter={"host":host})

            if data != []:
                hostid = data[0]['hostid']
            else:
                raise Exception('Could not find hostID for:' + host)

        except Exception as e:
            raise e

        return str(hostid)
    

    # #################################################
    # Method get_image_id
    # #################################################
    
    def get_image_id(self, image):
        '''
        DESCRIPTION:
        Get the imageid for a image
        '''

        print image

        try:
            data = self.zapi.image.get(output='extend', filter={"name":image})

            print data

            if data != []:
                imageid = data[0]['imageid']
            else:
                raise Exception('Could not find imageID for:' + image)

        except Exception as e:
            raise e

        return str(imageid)


    # #################################################
    # Method get_map_id
    # #################################################
    
    def get_map_id(self, map):
        '''
        DESCRIPTION:
        Get the mapid for a map
        '''

        try:
            data = self.zapi.map.getobjects(name=map)

            if data != []:
                mapid = data[0]['sysmapid']
            else:
                raise Exception('Could not find mapID for:' + map)

        except Exception as e:
            raise e

        return str(mapid)



    # #################################################
    # Method get_screen_id
    # #################################################
    
    def get_screen_id(self, screen):
        '''
        DESCRIPTION:
        Get the screenid for a screen
        '''

        try:
            data = self.zapi.screen.get(output='extend', filter={"name":screen})

            if data != []:
                screenid = data[0]['screenid']
            else:
                raise Exception('Could not find screenID for:' + screen)

        except Exception as e:
            raise e

        return str(screenid)



    # ###############################################
    # Method get_template_id
    # ###############################################
    
    def get_template_id(self, template):
        '''
        DESCRIPTION:
        Get the templateid for a template
        '''

        try:
            data = self.zapi.template.get(output='extend', filter={"host":template})
            
            if data != []:
                templateid = data[0]['templateid']
            else:
                raise Exception('Could not find TemplateID for:' + template)

        except Exception as e:
            raise e

        return str(templateid)


    # ##########################################
    # Method get_usergroup_id
    # ##########################################
    
    def get_usergroup_id(self, usergroup):
        '''
        DESCRIPTION:
        Get the usergroupid for a usergroup
        '''

        try:
            data = self.zapi.usergroup.getobjects(name=usergroup)

            if data != []:
                usergroupid = data[0]['usrgrpid']
            else:
                raise Exception('Could not find usergroupID for: ' + usergroup)

        except Exception as e:
            raise e

        return str(usergroupid)


    # ##########################################
    # Method get_user_id
    # ##########################################
    
    def get_user_id(self, user):
        '''
        DESCRIPTION:
        Get the userid for a user
        '''

        try:
            data = self.zapi.user.get(search={'alias':user})

            if data != []:
                userid = data[0]['userid']
            else:
                raise Exception('Could not find userID for: ' + user)

        except Exception as e:
            raise e

        return str(userid)

    
    # ##########################################
    # Method get_proxy_id
    # ##########################################
    
    def get_proxy_id(self, proxy):
        '''
        DESCRIPTION:
        Get the proxyid for a proxy server
        '''

        try:
            data = self.zapi.proxy.get(output='extend', filter={"host":proxy})

            if data != []:
                proxyid = data[0]['proxyid']
            else:
                raise Exception('Could not find proxyID for:' + proxy)

        except Exception as e:
            raise e

        return str(proxyid)


    # ##########################################
    # Method get_random_proxy
    # ##########################################
    
    def get_random_proxyid(self,proxy):
        '''
        Return a random proxyID from the list of existing proxies 
        '''

        proxy_list = []

        try:
            search_proxy = '\'search\':{\'host\':\'' + proxy + '\'}' 
            query=ast.literal_eval("{'output':'extend'," + search_proxy  + ",'searchWildcardsEnabled':'True'}")

            data = self.zapi.proxy.get(**query)
            
            for proxy in data:
                proxy_list.append(proxy['proxyid'])
            
        except Exception as e:
            raise e

        proxy_list_len = len(proxy_list)

        if proxy_list_len > 0:
            get_random_index = random.randint(0,proxy_list_len - 1)
            return proxy_list[get_random_index]

        else:
            raise Exception('The proxy list is empty')
            

    # ############################################
    # Method preloop
    # ############################################

    def preloop(self):
        '''
        Initialization before prompting user for commands.
        '''
        
        cmd.Cmd.preloop(self)   ## sets up command completion
        self._hist    = []      ## No history yet
        self._locals  = {}      ## Initialize execution namespace for user
        self._globals = {}


    # ############################################
    # Method help_shortcuts
    # ############################################

    def help_shortcuts(self):
        '''
        Help information about shortcuts in Zabbix-CLI
        '''
        
        print '''
        Shortcuts in Zabbix-CLI:

        \h [COMMAND] - Help on syntax of Zabbix-CLI commands
        \? [COMMAND] - Help on syntax of Zabbix-CLI commands
        
        \s - display history 
        \q - quit Zabbix-CLI shell

        \! [COMMAND] - Execute command in shell
          
        '''


    # ############################################
    # Method help_shortcuts
    # ############################################

    def help_support(self):
        '''
        Help information about Zabbix-CLI support
        '''
        
        print '''
        The latest information and versions of Zabbix-CLI can be obtained 
        from: http://
          
        '''


    # ############################################
    # Method handler
    # ############################################

    def signal_handler_sigint(self,signum, frame):
        cmd.Cmd.onecmd(self,'quit')
        sys.exit(0)


    # ############################################
    # Method get_version
    # ############################################

    def get_version(self):
        '''
        Get Zabbix-CLI version
        '''
        
        try:
            return zabbix_cli.version.__version__

        except Exception as e:
            return 'Unknown'


if __name__ == '__main__':

    signal.signal(signal.SIGINT, zabbix_cli().signal_handler_sigint)
    signal.signal(signal.SIGTERM,zabbix_cli().signal_handler_sigint)
    zabbix_cli().cmdloop()

