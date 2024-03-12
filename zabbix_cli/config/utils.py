from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import TYPE_CHECKING

from zabbix_cli.config.constants import CONFIG_PRIORITY
from zabbix_cli.config.constants import DEFAULT_CONFIG_FILE
from zabbix_cli.dirs import mkdir_if_not_exists
from zabbix_cli.exceptions import ConfigError

if TYPE_CHECKING:
    from zabbix_cli.config.model import Config


def _load_config_toml(filename: Path) -> Dict[str, Any]:
    """Load a TOML configuration file."""
    import tomli

    return tomli.loads(filename.read_text())


def _load_config_conf(filename: Path) -> Dict[str, Any]:
    """Load a conf configuration file with ConfigParser."""
    import configparser

    config = configparser.ConfigParser()
    config.read_file(filename.open())
    return {s: dict(config.items(s)) for s in config.sections()}


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


def get_config(filename: Optional[Path] = None) -> Config:
    """Get a configuration object.

    Args:
        filename (Optional[str], optional): An optional user supplied file to throw into the mix. Defaults to None.

    Returns:
        Config: Config object loaded from file
    """
    from zabbix_cli.config.model import Config

    return Config.from_file(find_config(filename))


def create_config_file(
    config: Optional[Config] = None,
    filename: Optional[Path] = None,
    overwrite: bool = False,
) -> Path:
    """Create a default config file."""
    if filename is None:
        filename = DEFAULT_CONFIG_FILE
    if filename.exists() and not overwrite:
        raise ConfigError(f"File {filename} already exists")
    mkdir_if_not_exists(filename.parent)

    if not config:
        config = Config.sample_config()

    try:
        config.dump_to_file(filename)
    except OSError:
        raise ConfigError(f"unable to create config file {filename}")
    return filename
