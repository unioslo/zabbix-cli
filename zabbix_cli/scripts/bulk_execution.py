# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014-2015 USIT-University of Oslo
#
# This file is part of Zabbix-cli
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
import logging
import sys
import os
import argparse
import subprocess

from zabbix_cli.config import get_config, validate_config
from zabbix_cli.logs import configure_logging


logger = logging.getLogger('zabbix-cli-bulk-execution')


def main():

    parser = argparse.ArgumentParser(prog=sys.argv[0])
    parser.add_argument(
        '--input-file', '-f',
        metavar='FILE',
        type=argparse.FileType('r'),
        default='-',
        dest='input',
        help='Read commands from %(metavar)s, defaults to stdin'),
    parser.add_argument(
        '--config', '-c',
        metavar='<config file>',
        required=False,
        dest='config_file')

    args = parser.parse_args()

    conf = get_config(args.config_file)
    validate_config(conf)
    configure_logging(conf)

    # Make a sub-logger that outputs to stdout
    messages = logger.getChild('messages')
    messages.propagate = True
    messages.setLevel(logging.INFO)
    messages_output = logging.StreamHandler(sys.stdout)
    messages_output.setFormatter(
        logging.Formatter("[%(levelname)s]: %(message)s"))
    messages.addHandler(messages_output)

    #
    # If logging is activated, start logging to the file defined
    # with log_file in the config file.
    #

    logger.debug('**** Zabbix-cli-bulk-execution started. ****')
    messages.info('Reading commands from %r', args.input.name)

    for lineno, line in enumerate(args.input, 1):
        try:
            zabbix_cli_command = line.strip()

            command = 'zabbix-cli -o json -C "' + zabbix_cli_command + '"'

            DEVNULL = open(os.devnull, 'w')
            proc = subprocess.Popen([command], stdout=DEVNULL, stderr=DEVNULL,
                                    shell=True)
            proc.wait()

            if proc.returncode == 0:
                logger.info('Zabbix-cli command %r executed', command)
            else:
                logger.warning('Zabbix-cli command %r could not be executed',
                               command)
        except Exception as e:
            messages.error('Encoutered an error on line %i: %r', lineno, line)
            logger.error('Error in file=%r lineno=%d line=%r',
                         args.input.name, lineno, line, exc_info=True)
            logger.debug('**** Zabbix-cli-bulk-execution aborted. ****')
            break

    if args.input is not sys.stdin:
        args.input.close()
    logger.debug('**** Zabbix-cli-bulk-execution finished. ****')
