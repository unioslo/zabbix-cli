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
| Carl  
|
| Source: https://github.com/usit-gd/zabbix-cli
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

TODO

Installation
============

System requirements
-------------------

* Linux/Unix
* Python 2.6 or 2.7
* Python modules: ldap, request
     
Before you install Zabbix-CLI you have to install the software needed
by this tool

In systems using ``yum``, e.g. Centos, RHEL, ...::

  yum install python-ldap python-requests

In system using ``apt-get``, e.g. Debian, Ubuntu, ...::

  apt-get install python-ldap python-requests

If you are going to install from source, you need to install also
these packages: ``python-dev(el), python-setuptools, git, make, python-docutils``

In systems using ``yum``::

  yum install python-devel python-setuptools git make python-docutils

In system using ``apt-get``::

  apt-get install python-dev python-setuptools git make python-docutils


Installing from source
----------------------

The easiest way to install zabbix-cli from source is to get the
lastest version from the master branch at the GitHub repository.

::

 [root@server]# cd
 [root@server]# git clone https://github.com/usit-gd/zabbix-cli.git

 [root@server]# cd zabbix-cli
 [root@server]# ./setup.py install
 .....


Installing via RPM packages
---------------------------

TODO

Installing via Deb packages
----------------------------

TODO

Configuration
=============

Configuration file
------------------

Zabbix-CLI needs a configuration file to work. It will look for the
file in this order:

* ``$HOME/.zabbix-cli/zabbix-cli.conf``
* ``/etc/zabbix-cli/zabbix-cli.conf``
* ``/etc/zabbix-cli.conf``

A default configuration file can be found in ``etc/zabbix-cli.conf``
in the source code.

The parameter ``zabbix_api_url`` must be defined in the configuration
file. Without this parameter, ``zabbix-cli`` will not know where to
connect.

Remember to define the ``log_file`` parameter with a valid value if
you activate logging with ``logging=ON``. The user running
``zabbix-cli`` must have read/write access to the log file defined
with ``log_file``.


Authentication file
-------------------

You can define the file ``$HOME/.zabbix-cli_auth`` if you want to
avoid to write your username and password everytime you use
``zabbix-cli``. This can be useful if you are running ``zabbix-cli``
in non-interactive modus from scripts or automated jobs.

The format of this file is a line with this information::

  USERNAME::PASSWORD

**NOTE:** The password will be saved in clear text so be carefull with
the information saved here and restrict access to this file only to
your user. ``chmod 400 ~/.zabbix-cli_auth`` will be defined by
``zabbix-cli`` on this file the first time it uses it.


Zabbix-CLI shell
================

The Zabbix-CLI interactive shell can be started by running the program
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
   clear             shell         show_hostgroups  
   create_user       show_alarms   show_hosts     
   create_usergroup  show_history  show_usergroups
   
   Miscellaneous help topics:
   ==========================
   shortcuts  support

   Undocumented commands:
   ======================
   help

**NOTE:** It is possible to use Zabbix-CLI in a non-interactive modus
by running ``/usr/bin/zabbix-cli`` with a command as a parameter in
the OS shell. This can be used to run ``zabbix-cli`` commands from shell
scripts or other programs .e.g.

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
   |      49 | testgroup                 | System default (0) |  Enable (0) |
   |      15 | Test users                | System default (0) |  Enable (0) |
   |      16 | Test users intern         |    Internal (1)    |  Enable (0) |
   |       7 | Zabbix administrators     |    Internal (1)    |  Enable (0) |
   |      14 | Zabbix core               | System default (0) |  Enable (0) |
   +---------+---------------------------+--------------------+-------------+

You can also use the parameter ``--use-csv-format`` when running
``zabbix-cli`` in non-interactive modus to generate an output in CSV
format.

::

   [user@host ~]# zabbix-cli --use-csv-format show_usergroups

   "13","DBA","System default (0)","Enable (0)"
   "9","Disabled","System default (0)","Disable (1)"
   "11","Enabled debug mode","System default (0)","Enable (0)"
   "8","Guests","Disable (2)","Disable (1)"
   "12","No access to the frontend","Disable (2)","Enable (0)"
   "49","testgroup","System default (0)","Enable (0)"
   "15","Test users","System default (0)","Enable (0)"
   "16","Test users intern","Internal (1)","Enable (0)"
   "7","Zabbix administrators","Internal (1)","Enable (0)"
   "14","Zabbix core","System default (0)","Enable (0)"


Remember that you have to use ``""`` or escape some characters if
running commands in non-interactive modus with parameters that have spaces
or special characters for the shell.e.g.

::

   [user@host ~]# zabbix-cli show_host "*" "\'available\':\'2\',\'maintenance_status\':\'1\'"

   +--------+----------------------+-------------------------+-----------------------------------+--------------------+-----------------+-----------------+---------------+
   | HostID | Name                 | Hostgroups              | Templates                         | Applications       |   Zabbix agent  |   Maintenance   |     Status    |
   +--------+----------------------+-------------------------+-----------------------------------+--------------------+-----------------+-----------------+---------------+
   |  10110 | test01.uio.no        | [8] Database servers    | [10102] Template App SSH Service  | CPU                | Unavailable (2) | In progress (1) | Monitored (0) |
   |        |                      |                         | [10104] Template ICMP Ping        | Filesystems        |                 |                 |               |
   |        |                      |                         | [10001] Template OS Linux         | General            |                 |                 |               |
   |        |                      |                         |                                   | ICMP               |                 |                 |               |
   |        |                      |                         |                                   | Memory             |                 |                 |               |
   |        |                      |                         |                                   | Network interfaces |                 |                 |               |
   |        |                      |                         |                                   | OS                 |                 |                 |               |
   |        |                      |                         |                                   | Performance        |                 |                 |               |
   |        |                      |                         |                                   | Processes          |                 |                 |               |
   |        |                      |                         |                                   | SSH service        |                 |                 |               |
   |        |                      |                         |                                   | Security           |                 |                 |               |
   |        |                      |                         |                                   | Zabbix agent       |                 |                 |               |
   +--------+----------------------+-------------------------+-----------------------------------+--------------------+-----------------+-----------------+---------------+
   |  10484 | test02.uio.no        | [12] Web servers        | [10094] Template App HTTP Service | HTTP service       | Unavailable (2) | In progress (1) | Monitored (0) |
   |        |                      | [13] PostgreSQL servers | [10073] Template App MySQL        | ICMP               |                 |                 |               |
   |        |                      | [17] MySQL servers      | [10102] Template App SSH Service  | MySQL              |                 |                 |               |
   |        |                      | [21] ssh servers        | [10104] Template ICMP Ping        | SSH service        |                 |                 |               |
   |        |                      | [5] Discovered hosts    |                                   |                    |                 |                 |               |
   |        |                      | [8] Database servers    |                                   |                    |                 |                 |               |
   +--------+----------------------+-------------------------+-----------------------------------+--------------------+-----------------+-----------------+---------------+
   |  10427 | test03.uio.no        | [12] Web servers        | [10094] Template App HTTP Service | HTTP service       | Unavailable (2) | In progress (1) | Monitored (0) |
   |        |                      | [17] MySQL servers      | [10073] Template App MySQL        | ICMP               |                 |                 |               |
   |        |                      | [21] ssh servers        | [10102] Template App SSH Service  | MySQL              |                 |                 |               |
   |        |                      | [5] Discovered hosts    | [10104] Template ICMP Ping        | SSH service        |                 |                 |               |
   |        |                      | [8] Database servers    |                                   |                    |                 |                 |               |
   +--------+----------------------+-------------------------+-----------------------------------+--------------------+-----------------+-----------------+---------------+


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


create_user
-----------

This command creates a user.

::

   create_user [alias]
               [name]
               [surname]
               [passwd]
               [type]
               [autologin]
               [autologout]
               [groups]

Parameters:

* **[alias]:** User alias (account name)
* **[name]:** Name of the user
* **[surname]:** Surname of the user
* **[passwd]:** Password
* **[type]:** Type of the user. 

  Possible values: 
  1 - (default) Zabbix user; 
  2 - Zabbix admin; 
  3 - Zabbix super admin.

* **[autologin]:** Whether to enable auto-login. 

  Possible values: 
  0 - (default) auto-login disabled; 
  1 - auto-login enabled.

* **[autologout]:** User session life time in seconds. If set to 0,
  the session will never expire. Default: 86400

* **[groups]:** User groups to add the user to. 
 
The default value for a parameter is shown between brackets []. If the
user does not define any value, the default value will be used. This
command can be run with or without parameters. e.g.:

::

   [zabbix-CLI]$ create_user
   --------------------------------------------------------
   # Alias []: user-test
   # Name []: Test
   # Surname []: User
   # Password []: 
   # User type [1]: 
   # Autologin [0]: 
   # Autologout [86400]: 
   # Usergroups []: 16
   --------------------------------------------------------
   
   [Done]: User (user-test) with ID: 19 created.


   [zabbix-CLI]$ create_user user-test2 Test User2 "" "" "" 600 16
   
   [Done]: User (user-test2) with ID: 20 created.



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
