=====================================
Zabbix-CLI
=====================================

|
| Version-1.1.0
|
| Authors: 
| .....
| .....
|
| .....
| .....
|
| Rafael Martinez Guerrero (University of Oslo)
| E-mail: rafael@postgresql.org.es
|
| Source: https://github.com/rafaelma/zabbix-cli
|

.. contents::


Introduction
============

Zabbix-cli is a tool for managing some Zabbix administration task via
the zabbix-API.

The zabbix-cli code is distributed under the GNU General Public
License 3 and it is written in Python and PL/PgSQL. It has been
developed and tested by members of the Department for IT
Infrastructure at the Center for Information Technology at the
University of Oslo.


Main features
=============

The main features of zabbix-cli are:


Installation
============

System requirements
-------------------

* Linux/Unix
* Python 2.6 or 2.7
* Python modules:
     
Before you install zabbix-cli you have to install the software needed
by this tool

In systems using ``yum``, e.g. Centos, RHEL, ...::

  yum install 

In system using ``apt-get``, e.g. Debian, Ubuntu, ...::

  apt-get install 

If you are going to install from source, you need to install also
these packages: ``python-dev(el), python-setuptools, git, make, rst2pdf``

In systems using ``yum``::

  yum install python-devel python-setuptools git make rst2pdf

In system using ``apt-get``::

  apt-get install python-dev python-setuptools git make rst2pdf


Installing from source
----------------------

The easiest way to install zabbix-cli from source is to get the last
version from the master branch at the GitHub repository.

::

 [root@server]# cd
 [root@server]# git clone https://github.com/rafaelma/zabbix-cli.git

 [root@server]# cd zabbix-cli
 [root@server]# ./setup.py install
 .....


Installing via RPM packages
---------------------------


Installing via Deb packages
----------------------------

Configuration
=============



Zabbix-CLI shell
================

The zabbix-cli interactive shell can be started by running the program
``/usr/bin/zabbix-cli``

::

   [user@host]# zabbix-cli

   #############################################################
   Welcome to the Zabbix command-line interface (v.Unknown)
   #############################################################
   Type help or \? to list commands.
   
   [zabbix-CLI]$ help
   
   Documented commands (type help <topic>):
   ========================================
   EOF               quit          show_host        show_users            
   clear             shell         show_hostgroups  synchronize_usergroups
   create_user       show_alarms   show_hosts     
   create_usergroup  show_history  show_usergroups
   
   Miscellaneous help topics:
   ==========================
   shortcuts  support

   Undocumented commands:
   ======================
   help

**NOTE:** It is possible to use the zabbix-cli shell in a
non-interactive modus by running ``/usr/bin/zabbix-cli`` with a
command as a parameter in the OS shell. This can be used to run
zabbix-cli commands from shell scripts.e.g.

::

   [user@host]# zabbix-cli show_usergroups

   +---------+---------------------------+--------------------+-------------+
   | GroupID | Name                      |     GUI access     |    Status   |
   +---------+---------------------------+--------------------+-------------+
   |      13 | DBA                       | System default (0) |  Enable (0) |
   |       9 | Disabled                  | System default (0) | Disable (1) |
   |      11 | Enabled debug mode        | System default (0) |  Enable (0) |
   |       8 | Guests                    |    Disable (2)     | Disable (1) |
   |      12 | No access to the frontend |    Disable (2)     |  Enable (0) |
   |      43 | sapp-dba                  | System default (0) |  Enable (0) |
   |      49 | testgroup                 | System default (0) |  Enable (0) |
   |      15 | Test users                | System default (0) |  Enable (0) |
   |      16 | Test users intern         |    Internal (1)    |  Enable (0) |
   |       7 | Zabbix administrators     |    Internal (1)    |  Enable (0) |
   |      14 | Zabbix core               | System default (0) |  Enable (0) |
   +---------+---------------------------+--------------------+-------------+


clear
-----

This command clears the screen and shows the welcome banner

::

   clear

This command can be run only without parameters. e.g.:

::

   [zabbix-CLI]$ clear

   #############################################################
   Welcome to the Zabbix command-line interface (v.Unknown)
   #############################################################
   Type help or \? to list commands.
   
   [zabbix-CLI]$ 


quit
----

This command quits/terminates the zabbix-CLI shell.

::

  quit

A shortcut to this command is ``\q``.

This command can be run only without parameters. e.g.:

::

   [zabbix-CLI]$ quit
   Done, thank you for using Zabbix-CLI

   [zabbix-CLI]$ \q
   Done, thank you for using Zabbix-CLI


shell
-----

This command runs a command in the operative system.

::

   shell [command]

Parameters:

* **[command]:** Any command that can be run in the operative system.

It exists a shortcut ``[!]`` for this command that can be used insteed
of ``shell``. This command can be run only with parameters. e.g.:

::

   [pgbackman]$ ! ls -l
   total 88
   -rw-rw-r--. 1 vagrant vagrant   135 May 30 10:04 AUTHORS
   drwxrwxr-x. 2 vagrant vagrant  4096 May 30 10:03 bin
   drwxrwxr-x. 4 vagrant vagrant  4096 May 30 10:03 docs
   drwxrwxr-x. 2 vagrant vagrant  4096 May 30 10:03 etc
   -rw-rw-r--. 1 vagrant vagrant     0 May 30 10:04 INSTALL
   -rw-rw-r--. 1 vagrant vagrant 35121 May 30 10:04 LICENSE
   drwxrwxr-x. 4 vagrant vagrant  4096 May 30 10:03 vagrant


show_history
------------

Show the list of commands that have been entered during the zabbix-cli
shell session.

::

   show_history

A shortcut to this command is ``\s``. One can also use the *Emacs
Line-Edit Mode Command History Searching* to get previous commands
containing a string. Hit ``[CTRL]+[r]`` in the zabbix-CLI shell followed by
the search string you are trying to find in the history.

This command can be run only without parameters. e.g.:

::

   [pgbackman]$ show_history

   [0]: help
   [1]: help show_history
   [2]: show_history
   [3]: help
   [4]: show_history



Authors
=======

In alphabetical order:

|
| Rafael Martinez Guerrero
| E-mail: rafael@postgresql.org.es / rafael@usit.uio.no
| PostgreSQL-es / University Center for Information Technology (USIT), University of Oslo, Norway
|

License and Contributions
=========================

Zabbix-CLI is the property of USIT-University of Oslo, and its code is
distributed under GNU General Public License 3.

| Copyright © 2014 USIT-University of Oslo.
