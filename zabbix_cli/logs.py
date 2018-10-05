# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014-2015 USIT-University of Oslo
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

import logging
import sys

from zabbix_cli.config import configuration


class log(logging.Logger):

    # ############################################
    # Constructor
    # ############################################

    def __init__(self, logger_name, config_file):
        """ The Constructor."""

        self.logger_name = logger_name
        self.conf = configuration(config_file)

        self.logger = logging.getLogger(logger_name)
        level = logging.getLevelName(self.conf.log_level.upper())

        self.logger.setLevel(level)

        try:

            self.fh = logging.FileHandler(self.conf.log_file)
            self.fh.setLevel(level)

            self.formatter = logging.Formatter("%(asctime)s [%(name)s][None][%(process)d][%(levelname)s]: %(message)s")
            self.fh.setFormatter(self.formatter)
            self.logger.addHandler(self.fh)

        except Exception as e:
            print("ERROR: Problems with the log configuration needed by Zabbix-CLI: %s" % e)
            sys.exit(1)
