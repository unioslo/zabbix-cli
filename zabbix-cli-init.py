#!/usr/bin/env python
#
# Authors:
# Mustafa Ocak
# muo@uio.no
#
# Copyright (c) 2015 USIT-University of Oslo
###########################################################################################
# This script initialize zabbix-cli environment. it will copy /etc/zabbix-cli.conf to 
# $HOME/.zabbix-cli/ 
# and change log configuration in zabbix-cli.conf so that zabbix-cli logs to 
# $HOME/.zabbix-cli/ 
###########################################################################################

from os import getenv,path,remove,close,makedirs
from tempfile import mkstemp
from shutil import move, copy2



def replace(file_path, pattern, subst):

    #
    #  changing the line having log configuration option 
    #  replacing 
    #  log_file=/var/log/zabbix-cli/zabbix-cli.log
    #  to log_file=~/.zabbix-cli/zabbix-cli.log
    
    #Create temp file
    fh, abs_path = mkstemp()
    with open(abs_path,'w') as new_file:
        with open(file_path) as old_file:
            for line in old_file:
                new_file.write(line.replace(pattern, subst))
    close(fh)
    #Remove original file
    remove(file_path)
    #Move new file
    move(abs_path, file_path)

if __name__ == "__main__":

#    file_path=getenv('HOME')+"/testenv/test.log"
    pattern="log_file=/var/log/zabbix-cli/zabbix-cli.log"
    subst="log_file="+getenv('HOME')+"/.zabbix-cli/zabbix-cli.log"

    zabbixconfdir = getenv('HOME')+"/.zabbix-cli/"
    defconf="/etc/zabbix-cli.conf"
    filename="zabbix-cli.conf"

    file_path=path.join(zabbixconfdir,filename)

#    option="log_file=/var/log/zabbix-cli/zabbix-cli.log$"
#    changedto="log_file="+zabbixconfdir+"zabbix-cli.log"
    
    
    #
    # creating ~/.zabbix-cli folder if not exists
    #

    if not path.exists(zabbixconfdir):
        makedirs(zabbixconfdir)

    #
    # /etc/zabbix-cli.conf will be created under installation of zabbix-cli package. 
    # copying /etc/zabbix-cli.conf file to ~/.zabbix-cli/zabbix-cli.conf
    # 

    if path.isfile(defconf):
        copy2(defconf,zabbixconfdir)


    #
    #  changing the line having log configuration option 
    #   
    #

    replace(file_path,pattern,subst)

