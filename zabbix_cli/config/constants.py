from __future__ import annotations

from pathlib import Path

from strenum import StrEnum

from zabbix_cli.dirs import CONFIG_DIR
from zabbix_cli.dirs import SITE_CONFIG_DIR

# Config file basename
CONFIG_FILENAME = "zabbix-cli.toml"
DEFAULT_CONFIG_FILE = CONFIG_DIR / CONFIG_FILENAME

CONFIG_PRIORITY = (
    Path() / CONFIG_FILENAME,  # current directory
    DEFAULT_CONFIG_FILE,  # local config directory
    SITE_CONFIG_DIR / CONFIG_FILENAME,  # system config directory
)


# Environment variable names
class ConfigEnvVars:
    USERNAME = "ZABBIX_CLI_USERNAME"
    PASSWORD = "ZABBIX_CLI_PASSWORD"


class OutputFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    TABLE = "table"
