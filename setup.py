#!/usr/bin/env python
#
# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014 USIT-University of Oslo 
#
# This file is part of Zabbix-Cli
# https://github.com/rafaelma/zabbix-cli
#
# Zabbix-Cli is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Zabbix-Cli is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zabbix-Cli.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import platform
import shutil
import sys
import os
import pwd
import grp
from setuptools import setup

'''
setup.py installation file
'''
try:
    zabbix_cli = {}
    with open('zabbix_cli/version.py', 'r') as version_file:
        exec (version_file.read(), zabbix_cli)
        
    if sys.version_info < (2, 6):
        raise SystemExit('ERROR: zabbix-cli needs at least python 2.6 to work')
    else:
        install_requires = ['argparse','requests']

                
    #
    # Setup
    #

    setup(name='zabbix_cli',
          version=zabbix_cli['__version__'],
          description='ZABBIX-CLI - Zabbix terminal client',
          author='Rafael Martinez Guerrero',
          author_email='rafael@postgresql.org.es',
          url='https://github.com/usit-gd/zabbix-cli',
          packages=['zabbix_cli',],
          scripts=['bin/zabbix-cli','bin/zabbix-cli-bulk-execution','bin/zabbix-cli-init'],
          data_files=[('/etc/zabbix-cli', ['etc/zabbix-cli.conf']),
                      ('/usr/share/zabbix-cli', ['etc/zabbix-cli.conf'])],
          install_requires=install_requires,
          platforms=['Linux'],
          classifiers=[
            'Environment :: Console',
            'Development Status :: 5 - Production/Stable',
            'Topic :: System :: Monitoring',
            'Intended Audience :: System Administrators',
            'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
            'Programming Language :: Python',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            ],
          )

except Exception as e:
    print e
