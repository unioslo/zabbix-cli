from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple

from zabbix_cli.config.constants import CONFIG_PRIORITY
from zabbix_cli.config.constants import DEFAULT_CONFIG_FILE
from zabbix_cli.exceptions import ConfigError

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config


def load_config_toml(filename: Path) -> Dict[str, Any]:
    """Load a TOML configuration file."""
    import tomli

    try:
        return tomli.loads(filename.read_text())
    except tomli.TOMLDecodeError as e:
        raise ConfigError(f"Error decoding TOML file {filename}: {e}") from e
    except OSError as e:
        raise ConfigError(f"Error reading TOML file {filename}: {e}") from e


def load_config_conf(filename: Path) -> Dict[str, Any]:
    """Load a conf configuration file with ConfigParser."""
    import configparser

    config = configparser.ConfigParser()
    try:
        config.read_file(filename.open())
        return {s: dict(config.items(s)) for s in config.sections()}
    except (configparser.Error, OSError) as e:
        raise ConfigError(
            f"Error reading legacy configuration file {filename}: {e}"
        ) from e


def find_config(
    filename: Optional[Path] = None,
    priority: Tuple[Path, ...] = CONFIG_PRIORITY,
) -> Optional[Path]:
    """Find all available configuration files.

    :param filename: An optional user supplied file to throw into the mix
    """
    # FIXME: this is a mess.
    #        If we have a file, just try to load it and call it a day?
    filename_prio = list(priority)
    if filename:
        filename_prio.insert(
            0, filename
        )  # TODO: append last when we implement multi-file config merging
    for fp in filename_prio:
        if fp.exists():
            logging.debug("found config %r", fp)
            return fp
    return None


def get_config(filename: Optional[Path] = None, init: bool = False) -> Config:
    """Get a configuration object.

    Args:
        filename (Optional[str], optional): An optional user supplied file to throw into the mix. Defaults to None.

    Returns:
        Config: Config object loaded from file
    """
    from zabbix_cli.config.model import Config

    return Config.from_file(filename, init=init)


def init_config(
    config: Optional[Config] = None,
    config_file: Optional[Path] = None,
    overwrite: bool = False,
    # Compatibility with V2 zabbix-cli-init args
    url: Optional[str] = None,
    username: Optional[str] = None,
    login: bool = False,
) -> Path:
    """Creates required directories and boostraps config with
    options required to connect to the Zabbix API.
    """

    from zabbix_cli import auth
    from zabbix_cli.config.model import Config
    from zabbix_cli.dirs import init_directories
    from zabbix_cli.output.console import info
    from zabbix_cli.output.prompts import str_prompt
    from zabbix_cli.pyzabbix.client import ZabbixAPI

    # Create required directories
    init_directories()

    if config_file is None:
        config_file = DEFAULT_CONFIG_FILE
    if config_file.exists() and not overwrite:
        raise ConfigError(
            f"File {config_file} already exists. Use [option]--overwrite[/] to overwrite it."
        )

    if not config:
        config = Config.sample_config()
    if not url:
        url = str_prompt("Zabbix URL (without /api_jsonrpc.php)", url or config.api.url)
    config.api.url = url

    # Add username if provided
    # otherwise auth will prompt for it
    if username:
        config.api.username = username

    if login:
        client = ZabbixAPI.from_config(config)
        auth.login(client, config)

    config.dump_to_file(config_file)
    info(f"Configuration file created: {config_file}")
    return config_file
