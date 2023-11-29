"""Compatibility functions going from Zabbix-CLI v2 to v3.

The functions in this module are intended to ease the transition by
providing fallbacks to deprecated functionality in Zabbix-CLI v2.
"""
from __future__ import annotations

import os
from pathlib import Path

CONFIG_FILENAME = "zabbix-cli.conf"
CONFIG_FIXED_NAME = "zabbix-cli.fixed.conf"

# Config file locations
CONFIG_DEFAULT_DIR = "/usr/share/zabbix-cli"
CONFIG_SYSTEM_DIR = "/etc/zabbix-cli"
CONFIG_USER_DIR = os.path.expanduser("~/.zabbix-cli")

# Any item will overwrite values from the previous
CONFIG_PRIORITY = tuple(
    Path(os.path.join(d, f))
    for d, f in (
        (CONFIG_DEFAULT_DIR, CONFIG_FILENAME),
        (CONFIG_SYSTEM_DIR, CONFIG_FILENAME),
        (CONFIG_USER_DIR, CONFIG_FILENAME),
        (CONFIG_SYSTEM_DIR, CONFIG_FIXED_NAME),
        (CONFIG_DEFAULT_DIR, CONFIG_FIXED_NAME),
    )
)


AUTH_FILE = Path.home() / ".zabbix-cli.auth"
AUTH_TOKEN_FILE = Path.home() / ".zabbix-cli_auth_token"
