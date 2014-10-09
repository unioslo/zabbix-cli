#!/usr/bin/env python
#
# Copyright (c) 2014 Rafael Martinez Guerrero / PostgreSQL-es
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

    def __init__(self,username,password):
        cmd.Cmd.__init__(self)
        
        self.version = self.get_version()

        self.intro =  '\n#############################################################\n' + \
            'Welcome to the Zabbix command-line interface (v.' + self.version + ')\n' + \
            '#############################################################\n' + \
            'Type help or \? to list commands.\n'
        
        self.prompt = '[zabbix-CLI]$ '
        self.file = None

        self.conf = configuration() 
        self.logs = logs('zabbix-cli')

        self.api_username = username
        self.api_password = password
        self.output_format = 'table'

        try:
            self.zapi = ZabbixAPI(self.conf.zabbix_api_url)
            self.zapi.session.verify = False
            self.zapi.login(self.api_username,self.api_password)
        
        except Exception as e:        
            print '\n[ERROR]: ',e
            print
            sys.exit(1)

    # ############################################  
    # Method show_hostgroups
    # ############################################  

    def do_show_hostgroups(self,args):
        '''
        show_hostgroups
        '''

        result_columns = {}
        result_columns_key = 0

        #
        # Get result from Zabbix API
        #
        try:
            result = self.zapi.hostgroup.get(output='extend',
                                             sortfield='name',
                                             sortorder='ASC')
             
        except Exception as e: 
            print '\n[Error] Problems getting hostgroup information - ',e
            return False   

        #
        # Get the columns we want to show from result 
        #
        for group in result:
            
            result_columns [result_columns_key] = [group['groupid'],
                                                   group['name'],
                                                   self.get_hostgroup_flag(int(group['flags'])),
                                                   self.get_hostgroup_type(int(group['internal']))]

            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['GroupID','Name','Flag','Type'],
                             ['Name'],
                             ['GroupID'],
                             FRAME)


    # ############################################                                                                                                                                    
    # Method show_host
    # ############################################

    def do_show_hosts(self,args):
        '''
        show_hosts
        '''

        cmd.Cmd.onecmd(self,'show_host "*"')


    # ############################################                                                                                                                                    
    # Method show_host
    # ############################################
    
    def do_show_host(self,args):
        '''
        DESCRIPTION:
        This command shows host information

        COMMAND:
        show_host [HostID / Hostname]
                  [Filter]

        [HostID / Hostname]:
        -------------------
        One can search by HostID or by Hostname. We can use wildcards 
        if we search by Hostname
            
        [Filter]:
        --------
        * Zabbix agent ('available'): 0=Unknown / 1=Available / 2=Unavailable
        * Maintenance ('maintenance_status'): 0:No maintenance / 1:In progress
        * Status ('status'): 0:Monitored/ 1: Not monitored
        
        e.g.: Show all hosts with Zabbix agent: Available AND Status: Monitored:
              show_host * "'available':'1','status':'0'"
        
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
                host = raw_input('# Host: ')
                filter = raw_input('# Filter: ')
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
                return False   

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 1:

            host = arg_list[0]
            filter = ''

        #
        # Command tith filters attributes
        #
            
        elif len(arg_list) == 2:
            
            host = arg_list[0]
            filter = arg_list[1]

        #
        # Command with the wrong number of parameters
        #

        else:
            print '\n[ERROR] - Wrong number of parameters used.\n          Type help or \? to list commands\n'
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
            print '\n[ERROR]: Problems generating query - ',e
            print
            return False

        #
        # Generate output
        #

        if self.output_format == 'table':

            x = PrettyTable(['HostID','Name','Hostgroups','Templates','Applications','Zabbix agent','Maintenance','Status'],header = True)
            x.align['GroupID'] = 'r'
            x.align['Name'] = 'l'
            x.align['Hostgroups'] = 'l'
            x.align['Templates'] = 'l'
            x.align['Applications'] = 'l'
            x.padding_width = 1
            x.hrules = ALL

        try:
            result = self.zapi.host.get(**query)
        
        except Exception as e:
            print '\n[Error] Problems getting host information - ',e
            return False   

        for host in result:
        
            hostgroup_list = ''
            template_list = ''
            application_list = ''

            host['groups'].sort()
            host['parentTemplates'].sort()
            host['applications'].sort()
                        
            for hostgroup in host['groups']:

                if self.output_format == 'table':
                    hostgroup_list = hostgroup_list + '[' + hostgroup['groupid'] + '] ' + hostgroup['name'] + '\n'
                    
                elif self.output_format == 'csv':
                    hostgroup_list = hostgroup_list + '[' + hostgroup['groupid'] + '] ' + hostgroup['name'] + ','

            for template in host['parentTemplates']:
                
                if self.output_format == 'table':
                    template_list = template_list + '[' + template['templateid'] + '] ' + template['name'] + '\n'

                elif self.output_format == 'csv':
                    template_list = template_list + '[' + template['templateid'] + '] ' + template['name'] + ','
            
            for application in host['applications']:
                
                if self.output_format == 'table':
                    application_list = application_list + application['name'] + '\n'

                elif self.output_format == 'csv':
                    application_list = application_list + '[' + application['name'] + ','
                                        
            if self.output_format == 'table':
                x.add_row([host['hostid'],
                           host['name'],
                           hostgroup_list[:-1],
                           template_list[:-1],
                           application_list[:-1],
                           self.get_zabbix_agent_status(int(host['available'])),
                           self.get_maintenance_status(int(host['maintenance_status'])),
                           self.get_monitoring_status(int(host['status']))
                       ])
                
            elif self.output_format == 'csv':
                print '"' + str(host['hostid']) + \
                      '","' + host['name'] + \
                      '","' + hostgroup_list[:-1] + \
                      '","' + template_list[:-1] + \
                      '","' + application_list[:-1] + \
                      '","' + self.get_zabbix_agent_status(int(host['available'])) + \
                      '","' + self.get_maintenance_status(int(host['maintenance_status'])) + \
                      '","' + self.get_monitoring_status(int(host['status'])) + '"'

        if self.output_format == 'table':
            print x
            print


    # ############################################  
    # Method show_usergroups
    # ############################################  

    def do_show_usergroups(self,args):
        '''
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
                     
        except Exception as e:
            print '\n[Error] Problems getting usergroup information - ',e
            return False   
       
        #
        # Get the columns we want to show from result 
        #
        for group in result:

            result_columns [result_columns_key] =[group['usrgrpid'],
                                                  group['name'],
                                                  self.get_gui_access(int(group['gui_access'])),
                                                  self.get_usergroup_status(int(group['users_status']))]
            
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['GroupID','Name','GUI access','Status'],
                             ['Name'],
                             ['GroupID'],
                             FRAME)


    # ############################################  
    # Method show_users
    # ############################################  

    def do_show_users(self,args):
        '''
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
                                         sortfield='alias',
                                         sortorder='ASC')
                     
        except Exception as e:
            print '\n[Error] Problems getting users information - ',e
            return False   
       
        #
        # Get the columns we want to show from result 
        #
        for user in result:

            result_columns [result_columns_key] =[user['userid'],
                                                  user['alias'],
                                                  user['name'] + ' ' + user['surname'],
                                                  self.get_autologin_type(int(user['autologin'])),
                                                  user['autologout'],
                                                  self.get_user_type(int(user['type']))]

                                                  
            
            result_columns_key = result_columns_key + 1

        #
        # Generate output
        #
        self.generate_output(result_columns,
                             ['UserID','Alias','Name','Autologin','Autologout','Type'],
                             ['Name','Type'],
                             ['UserID'],
                             FRAME)


    # ############################################  
    # Method show_alarms
    # ############################################  

    def do_show_alarms(self,args):
        '''
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
                                           sortorder='DESC'
                                         )
        except Exception as e:
            print '\n[Error] Problems getting alarm information - ',e
            return False   


        #
        # Get the columns we want to show from result 
        #
        for trigger in result:

            lastchange = datetime.datetime.fromtimestamp(int(trigger['lastchange']))
            age = datetime.datetime.now() - lastchange

            result_columns [result_columns_key] = [trigger['triggerid'],
                                                   trigger['hostname'],
                                                   trigger['description'],
                                                   self.get_trigger_severity(int(trigger['priority'])),
                                                   str(lastchange),
                                                   str(age)]
            
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
    # Method synchronize_usergroups
    # ############################################
    
    def do_synchronize_usergroups(self,args):
        '''
        DESCRIPTION:
        This command synchronize a list og usergroups
        defined in the zabbix-cli.conf file between LDAP
        and Zabbix internal.

        COMMAND:
        synchronize_usergroups
        '''

        usergroups =  self.conf.usergroups_to_sync.split(' ')
        print usergroups
        
        #
        # Connect abd bind to LDAP server
        #
        try:
            print self.conf.ldap_uri
            ld = ldap.initialize(self.conf.ldap_uri)
            ld.protocol_version = ldap.VERSION3

            ld.simple_bind_s()
            print "# Connected to ldap server"

        except Exception as e:
            print '[ERROR]: ',e
            return False

        for usergroup in usergroups:

            ldap_users = []
            zabbix_users = []

            #
            # Create usergroup if they do not exist in Zabbix.
            # They are created with "System default (0)" GUI access
            #
            cmd.Cmd.onecmd(self,'create_usergroup "' + usergroup + '" "0"')

            #
            # Get LDAP users in usergroup
            #

            basedn = 'cn=' + usergroup + ',' + self.conf.ldap_usergroups_tree
            filter = "(objectClass=*)"

            results = ld.search_s(basedn,ldap.SCOPE_SUBTREE,filter)
            
            for dn,entry in results:
                for values in entry['nisNetgroupTriple']:
                    ldap_users.append(values.replace('(','').replace(',','').replace(')',''))
                         
            #
            # Get Zabbix users in usergroup
            #

            #
            # Create Zabbix user if it does not exist
            #

            #
            # Update Zabbix group with information from LDAP
            #
            
            #
            # Delete users from Zabbix group if they do not exist in
            # the LDAP group.
            #







    # ############################################
    # Method do_create_usergroup
    # ############################################

    def do_create_usergroup(self,args):
        '''
        COMMAND
        create_usergroup [group name]
                         [GUI access]
                         [Status]

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
                groupname = raw_input('# Name: ')
                gui_access = raw_input('# GUI access ['+ gui_access_default + ']: ')
                users_status = raw_input('# Status ['+ users_status_default + ']: ')
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
                return False   

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 3:

            groupname = arg_list[0]
            gui_access = arg_list[1]
            users_status = arg_list[2]

        #
        # Command with the wrong number of parameters
        #

        else:
            print '\n[ERROR] - Wrong number of parameters used.\n          Type help or \? to list commands\n'
            return False


        if gui_access == '' or gui_access not in ('0','1','2'):
            gui_access = gui_access_default

        if users_status == '' or users_status not in ('0','1'):
            users_status = users_status_default

        #
        # Check if usergroup exists
        #

        try:
            
            result = self.zapi.usergroup.exists(name=groupname)

        except Exception as e:
            print '\n[ERROR] Problems checking if usergroup (' + groupname + ') exists \n',e
            return False   
        
        #
        # Create usergroup if it does not exist
        #

        try:

            if result == True:
                print '\n[Warning] This usergroup (' + groupname + ') already exists.\n'
                return False   
                
            elif result == False:
                result = self.zapi.usergroup.create(name=groupname,
                                                    gui_access=gui_access,
                                                    users_status=users_status)
                
                print '\n[Done]: Usergroup (' + groupname + ') with ID: ' + str(result['usrgrpids'][0]) + ' created.\n'
        
        except Exception as e:
            print '\n[Error] Problems creating usergroup (' + groupname + ')\n',e
            return False   
            


    # ############################################
    # Method do_create_user
    # ############################################

    def do_create_user(self,args):
        '''
        COMMAND
        create_user [alias]
                    [name]
                    [surname]
                    [passwd]
                    [type]
                    [autologout]
                    [groups]
                    

        '''
        
        # Default md5 value of a random int >1 and <1000000 
        x = hashlib.md5()
        x.update(str(random.randint(1,1000000)))
        passwd_default = x.hexdigest()
        
        # Default 1: Zabbix user
        type_default = '1'

        # Default 1 day: 86400s
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
                alias = raw_input('# Alias []: ')
                name = raw_input('# Name []: ')
                surname = raw_input('# Surname []: ')
                passwd = raw_input('# Password []: ')
                type = raw_input('# User type [' + type_default + ']: ')
                autologout = raw_input('# Autologout [' + autologout_default + ']: ')
                usrgrps = raw_input('# Usergroups []: ')
                print '--------------------------------------------------------'

            except Exception as e:
                print '\n--------------------------------------------------------' 
                print '\n[Aborted] Command interrupted by the user.\n'
                return False   

        #
        # Command without filters attributes
        #

        elif len(arg_list) == 7:

            alias = arg_list[0]
            name = arg_list[1]
            surname = arg_list[2]
            passwd = arg_list[3]
            type = arg_list[4]
            autologout = arg_list[5]
            usrgrps = arg_list[6]

        #
        # Command with the wrong number of parameters
        #

        else:
            print '\n[Error] - Wrong number of parameters used.\n          Type help or \? to list commands\n'
            return False

        if alias == '':
            print '\n[Error]: User Alias is empty\n'
            return False

        if passwd == '':
            passwd = passwd_default

        if type == '' or type not in ('1','2','3'):
            type = type_default

        if autologout == '':
            autologout = autologout_default
        
        if usrgrps == '':
            print '\n[Error]: Group list is empty\n'
            return False

        #
        # Check if user exists
        #

        try:
            
            result = self.zapi.user.get(search={'alias':alias},output='extend',searchWildcardsEnabled=True)

        except Exception as e:
            print '\n[ERROR] Problems checking if user (' + alias + ') exists \n',e
            return False   

        #
        # Create user
        #

        try:

            if result != []:

                print '\n[Warning] This user (' + alias + ') already exists.\n'
                return False   
                
            else:
                result = self.zapi.user.create(alias=alias,
                                               name=name,
                                               surname=surname,
                                               passwd=passwd,
                                               type=type,
                                               autologout=autologout,
                                               usrgrps=usrgrps.strip().split(','))
                
                print '\n[Done]: User (' + alias + ') with ID: ' + str(result['userids'][0]) + ' created.\n'

        except Exception as e:
            print '\n[Error] Problems creating user (' + alias + '\n',e
            return False   
            

    # ############################################
    # Method get_trigger_severity
    # ############################################
    
    def get_trigger_severity(self,code):

        trigger_severity = {0:'Not classified',1:'Information',2:'Warning',3:'Average',4:'High',5:'Disaster'}

        if code in trigger_severity:
            return trigger_severity[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_maintenance_status
    # ############################################
    
    def get_maintenance_status(self,code):

        maintenance_status = {0:'No maintenance',1:'In progress'}

        if code in maintenance_status:
            return maintenance_status[code]  + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"

    
    # ############################################
    # Method get_monitoring_status
    # ############################################
    
    def get_monitoring_status(self,code):

        monitoring_status = {0:'Monitored',1:'Not monitored'}

        if code in monitoring_status:
            return monitoring_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_monitoring_status
    # ############################################
    
    def get_zabbix_agent_status(self,code):

        zabbix_agent_status = {1:'Available',2:'Unavailable'}

        if code in zabbix_agent_status:
            return zabbix_agent_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_gui_access
    # ############################################
    
    def get_gui_access(self,code):

        gui_access = {0:'System default',1:'Internal',2:'Disable'}

        if code in gui_access:
            return gui_access[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"

    # ############################################
    # Method get_usergroup_status
    # ############################################
    
    def get_usergroup_status(self,code):

        usergroup_status = {0:'Enable',1:'Disable'}

        if code in usergroup_status:
            return usergroup_status[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_hostgroup_flag
    # ############################################
    
    def get_hostgroup_flag(self,code):

        hostgroup_flag = {0:'Plain',4:'Discover'}

        if code in hostgroup_flag:
            return hostgroup_flag[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_hostgroup_type
    # ############################################
    
    def get_hostgroup_type(self,code):

        hostgroup_type = {0:'Not internal',1:'Internal'}

        if code in hostgroup_type:
            return hostgroup_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"




    # ############################################
    # Method get_user_type
    # ############################################
    
    def get_user_type(self,code):

        user_type = {1:'User',2:'Admin',3:'Super admin'}

        if code in user_type:
            return user_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method get_autologin_type
    # ############################################
    
    def get_autologin_type(self,code):

        autologin_type = {0:'Disable',1:'Enable'}

        if code in autologin_type:
            return autologin_type[code] + " (" + str(code) +")"

        else:
            return 'Unknown' + " (" + str(code) +")"


    # ############################################
    # Method generate_output
    # ############################################


    def generate_output(self,result,colnames,left_col,right_col,hrules):
        '''A function to generate the result output'''

        try:
        
            if self.output_format == 'table':
            
                x = PrettyTable(colnames)
                x.header = True
                x.padding_width = 1
                x.hrules = hrules
            
                for column in left_col:
                    x.align[column] = "l"
        
                for column in right_col:
                    x.align[column] = "r"

                for records in result:
                    x.add_row(result[records])
            
                print x.get_string()
                print

            elif self.output_format == 'csv':
            
                for records in result:
                    print '"' +  '","'.join(result[records]) + '"'
             
        except Exception as e: 
            print '\n[Error] Problems generating the output ',e



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
        print '\n[ERROR] - Unknown command: %s.\n          Type help or \? to list commands\n' % line


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
                line_out = line_in.lower()
            else:
                line_out = line_in

            if split_line[0] == '\h':
                line_out = line_out.replace('\h','help')
            elif split_line[0] == '\?':
                line_out = line_out.replace('\?','help')
            elif split_line[0] == '\!':
                line_out = line_out.replace('\!','shell')
            elif line_out == '\s':
                line_out = 'show_history'    
            elif line_out == '\q':
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
            print '\n[ERROR]: Problems running %s' % line


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
        Quits/terminate the Zabbix-CLI shell.

        COMMAND: 
        EOF
        
        '''

        print
        print '\nDone, thank you for using PgBackMan'
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
        '''Help information about shortcuts in Zabbix-CLI'''
        
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
        '''Help information about Zabbix-CLI support'''
        
        print '''
        The latest information and versions of Zabbix-CLI can be obtained 
        from: http:///

          
        '''

    # ############################################
    # Method 
    # ############################################
            
    def print_results_table(self,cur,colnames,left_columns):
        '''A function to print a table with command results'''
        
        if self.output_format == 'table':
        
            x = PrettyTable(colnames)
            x.padding_width = 1
            
            for column in left_columns:
                x.align[column] = "l"
        
            for records in cur:
                columns = []

                for index in range(len(colnames)):
                    columns.append(records[index])

                x.add_row(columns)
            
            print x.get_string()
            print

        elif self.output_format == 'csv':
            
            for records in cur:
                columns = []
                
                for index in range(len(colnames)):
                    columns.append(str(records[index]))
                    
                print ','.join(columns)




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
        '''Get Zabbix-CLI version'''
        
        try:
            return zabbix_cli.version.__version__

        except Exception as e:
            return 'Unknown'


if __name__ == '__main__':

    signal.signal(signal.SIGINT, zabbix_cli().signal_handler_sigint)
    signal.signal(signal.SIGTERM,zabbix_cli().signal_handler_sigint)
    zabbix_cli().cmdloop()

