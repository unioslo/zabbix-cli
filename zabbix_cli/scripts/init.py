# Authors:
# Mustafa Ocak
# muo@uio.no
#
# Copyright (c) 2015 USIT-University of Oslo
#
# This script initialize zabbix-cli environment. it will copy
# /etc/zabbix-cli/zabbix-cli.conf to $HOME/.zabbix-cli/ and change log
# configuration in zabbix-cli.conf so that zabbix-cli logs to
# $HOME/.zabbix-cli/
#
##############################################################################
import logging
import os

from tempfile import mkstemp
from shutil import move, copy2
import sys
import argparse

from zabbix_cli.config import (
    CONFIG_FILENAME,
    CONFIG_USER_DIR,
    get_config,
    validate_config,
)

logger = logging.getLogger('zabbix-cli-init')
description = 'zabbix-cli-init - Zabbix-cli initialization program'


def assert_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)


def main():
    logging.basicConfig(level=logging.INFO,
                        format='[%(levelname)s]: %(message)s')

    if os.getenv('HOME') is None:
        logger.error("Unable to write configuration: "
                     "no $HOME environment variable set")
        raise SystemExit(1)

    parser = argparse.ArgumentParser(description=description)
    # TODO: Required 'option' - should be positional argument ...
    parser.add_argument(
        '--zabbix-url', '-z',
        metavar='<zabbix URL>',
        required=True,
        dest='zabbix_api_url')
    args = parser.parse_args()

    # creating ~/.zabbix-cli folder if not exists
    try:
        assert_directory(CONFIG_USER_DIR)
    except:
        logger.error('unable to create directory %r',
                     CONFIG_USER_DIR,
                     exc_info=True)

    # building config from defaults + system configs
    config = get_config()
    logging.debug('building config from %r', config.loaded_files)

    config.zabbix_api_url = args.zabbix_api_url
    if config.log_file:
        config.log_file = os.path.join(CONFIG_USER_DIR, 'zabbix-cli.log')

    try:
        validate_config(config)
    except Exception as e:
        logger.error('invalid configuration', exc_info=True)

    with open(os.path.join(CONFIG_USER_DIR, CONFIG_FILENAME), 'w') as stream:
        config.write(stream)
        logger.info('wrote config to %r', stream.name)
