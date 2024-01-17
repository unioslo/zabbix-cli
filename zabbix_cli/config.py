# Authors:
# rafael@postgresql.org.es / http://www.postgresql.org.es/
#
# Copyright (c) 2014-2016 USIT-University of Oslo
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
from __future__ import annotations

import configparser
import logging
from enum import Enum
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import Tuple

import tomli
import tomli_w
import typer
from pydantic import AliasChoices
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import SecretStr
from pydantic import ValidationInfo
from strenum import StrEnum

from zabbix_cli._v2_compat import CONFIG_PRIORITY as CONFIG_PRIORITY_LEGACY
from zabbix_cli.dirs import CONFIG_DIR
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.dirs import LOGS_DIR
from zabbix_cli.dirs import SITE_CONFIG_DIR
from zabbix_cli.exceptions import ConfigError


# Config file basename
CONFIG_FILENAME = "zabbix-cli.toml"
DEFAULT_CONFIG_FILE = CONFIG_DIR / CONFIG_FILENAME

CONFIG_PRIORITY = (
    Path() / CONFIG_FILENAME,  # current directory
    DEFAULT_CONFIG_FILE,  # local config directory
    SITE_CONFIG_DIR / CONFIG_FILENAME,  # system config directory
)


logger = logging.getLogger(__name__)


# Environment variable names
ENV_VAR_PREFIX = "ZABBIX_CLI_"
ENV_ZABBIX_USERNAME = f"{ENV_VAR_PREFIX}USERNAME"
ENV_ZABBIX_PASSWORD = f"{ENV_VAR_PREFIX}PASSWORD"


class OutputFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    TABLE = "table"


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    @field_validator("*")
    @classmethod
    def _conf_bool_validator_compat(cls, v: Any, info: ValidationInfo) -> Any:
        """Handles old config files that specified bools as ON/OFF."""
        if not isinstance(v, str):
            return v
        if v.upper() == "ON":
            return True
        if v.upper() == "OFF":
            return False
        return v


class APIConfig(BaseModel):
    url: str = Field(
        default=...,
        # Changed in V3: zabbix_api_url -> url
        validation_alias=AliasChoices("url", "zabbix_api_url"),
    )
    verify_ssl: bool = Field(
        default=True,
        # Changed in V3: cert_verify -> verify_ssl
        validation_alias=AliasChoices("verify_ssl", "cert_verify"),
    )


class AppConfig(BaseModel):
    username: str = Field(
        default="zabbix-ID",
        # Changed in V3: system_id -> username
        validation_alias=AliasChoices("username", "system_id"),
    )
    password: Optional[SecretStr] = Field(default=None, exclude=True)
    auth_token: Optional[SecretStr] = Field(default=None, exclude=True)
    default_hostgroups: List[str] = Field(
        default=["All-hosts"],
        # Changed in V3: default_hostgroup -> default_hostgroups
        validation_alias=AliasChoices("default_hostgroups", "default_hostgroup"),
    )
    default_admin_usergroups: List[str] = Field(
        default=["All-root"],
        # Changed in V3: default_admin_usergroup -> default_admin_usergroups
        validation_alias=AliasChoices(
            "default_admin_usergroups", "default_admin_usergroup"
        ),
    )
    default_create_user_usergroups: List[str] = Field(
        default=["All-users"],
        # Changed in V3: default_create_user_usergroup -> default_create_user_usergroups
        validation_alias=AliasChoices(
            "default_create_user_usergroups", "default_create_user_usergroup"
        ),
    )
    default_notification_users_usergroups: List[str] = Field(
        default=["All-notification-users"],
        # Changed in V3: default_notification_users_usergroup -> default_notification_users_usergroups
        validation_alias=AliasChoices(
            "default_notification_users_usergroups",
            "default_notification_users_usergroup",
        ),
    )
    default_directory_exports: Path = EXPORT_DIR
    default_export_format: Literal["XML", "JSON", "YAML", "PHP"] = "XML"
    include_timestamp_export_filename: bool = True
    use_colors: bool = True
    use_auth_token_file: bool = False
    use_paging: bool = False
    output_format: OutputFormat = OutputFormat.TABLE
    allow_insecure_authfile: bool = True  # mimick old behavior
    legacy_json_format: bool = False
    """Mimicks V2 behavior where the JSON output was ALWAYS a dict, where
    each entry was stored under the keys "0", "1", "2", etc.
    """

    @field_validator(
        # Group names that were previously singular that are now plural
        "default_admin_usergroups",
        "default_create_user_usergroups",
        "default_hostgroups",
        "default_notification_users_usergroups",
        mode="before",
    )
    @classmethod
    def _validate_maybe_comma_separated(cls, v: Any) -> Any:
        """Validate argument that can be a single comma-separated values string
        or a list of strings.

        Used for backwards-compatibility with V2 config files, where multiple arguments
        were specified as comma-separated strings.
        """
        if isinstance(v, str):
            return v.strip().split(",")
        return v

    @field_validator("output_format", mode="before")
    @classmethod
    def _ignore_enum_case(cls, v: Any) -> Any:
        """Ignore case when validating enum value."""
        if isinstance(v, str):
            return v.lower()
        return v


class LoggingConfig(BaseModel):
    enabled: bool = Field(
        default=True,
        # Changed in V3: logging -> enabled (we also allow enable [why?])
        validation_alias=AliasChoices("logging", "enabled", "enable"),
    )
    log_level: Literal[
        "DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL"
    ] = "ERROR"
    log_file: Optional[Path] = (
        # TODO: define this default path elsewhere
        LOGS_DIR / "zabbix-cli.log"
    )

    @field_validator("log_file", mode="before")
    @classmethod
    def _empty_string_is_none(cls, v: Any) -> Any:
        """Passing in an empty string to `log_file` sets it to `None`,
        while omitting the option altogether sets it to the default.

        Examples
        -------

        To get `LoggingConfig.log_file == None`:

        ```toml
        [logging]
        log_file = ""
        ```

        To get `LoggingConfig.log_file == <default_log_file>`:

        ```toml
        [logging]
        # log_file = ""
        ```
        """
        if v == "":
            return None
        return v


class Config(BaseModel):
    api: APIConfig = Field(
        default_factory=APIConfig,
        # Changed in V3: zabbix_api -> api
        validation_alias=AliasChoices("api", "zabbix_api"),
    )
    app: AppConfig = Field(
        default_factory=AppConfig,
        # Changed in V3: zabbix_config -> app
        validation_alias=AliasChoices("app", "zabbix_config"),
    )
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    config_path: Optional[Path] = None

    @classmethod
    def sample_config(cls) -> Config:
        """Get a sample configuration."""
        return cls(api=APIConfig(url="https://zabbix.example.com/api_jsonrpc.php"))

    @classmethod
    def from_file(cls, filename: Optional[Path] = None) -> Config:
        """Load configuration from a file.

        Attempts to find a config file to load if none is specified.

        Prioritizes new-style .toml config files, but falls back
        to legacy .conf config files if no .toml config file can be found.
        """
        fp = find_config(filename)
        if not fp:  # We didn't find a .toml file, so try to find a legacy .conf file
            fp = find_config(filename, CONFIG_PRIORITY_LEGACY)
            if fp:
                logger.warning("Using legacy config file %r", fp)
                conf = _load_config_conf(fp)
                # Use legacy JSON format if we find a legacy config file
                conf.setdefault("zabbix_config", {}).setdefault(
                    "legacy_json_format", True
                )
            else:
                # Failed to find both .toml and .conf files
                raise FileNotFoundError("No configuration file found.")
        else:
            conf = _load_config_toml(fp)
        return cls(**conf, config_path=fp)

    def as_toml(self) -> str:
        """Dump the configuration to a TOML string."""
        return tomli_w.dumps(
            self.model_dump(
                mode="json",
                exclude_none=True,  # we shouldn't have any, but just in case
            )
        )

    def dump_to_file(self, filename: Path) -> None:
        """Dump the configuration to a TOML file."""
        if not filename.parent.exists():
            try:
                filename.parent.mkdir(parents=True)
            except OSError:
                logger.error("unable to create directory %r", filename.parent)
                raise ConfigError(f"unable to create directory {filename.parent}")
        filename.write_text(self.as_toml())


def _load_config_toml(filename: Path) -> Dict[str, Any]:
    """Load a TOML configuration file."""
    return tomli.loads(filename.read_text())


def _load_config_conf(filename: Path) -> Dict[str, Any]:
    """Load a conf configuration file with ConfigParser."""
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
    # If we have a file, just try to load it and call it a day?
    filename_prio = list(priority)
    if filename:
        filename_prio.insert(
            0, filename
        )  # TODO: append last when we implement multi-file config merging
    for fp in filename_prio:
        if fp.exists():
            logger.debug("found config %r", fp)
            return fp
    return None


def get_config(filename: Optional[Path] = None) -> Config:
    """Get a configuration object.

    Args:
        filename (Optional[str], optional): An optional user supplied file to throw into the mix. Defaults to None.

    Returns:
        Config: Config object loaded from file
    """
    return Config.from_file(find_config(filename))


def create_config_file(filename: Optional[Path] = None) -> Path:
    """Create a default config file."""
    if filename is None:
        filename = DEFAULT_CONFIG_FILE
    if filename.exists():
        raise ConfigError(f"File {filename} already exists")
    config = Config.sample_config()
    try:
        config.dump_to_file(filename)
    except OSError:
        raise ConfigError(f"unable to create config file {filename}")
    logger.info("Created default config file %r", filename)
    return filename


class RunMode(str, Enum):
    SHOW = "show"
    DEFAULTS = "defaults"


def main(
    arg: RunMode = typer.Argument(RunMode.DEFAULTS, case_sensitive=False),
    filename: Optional[Path] = None,
):
    """Print current or default config to stdout."""
    if arg == RunMode.SHOW:
        config = get_config(filename)
    else:
        config = Config.sample_config()
    print(config.as_toml())


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    from zabbix_cli.logs import configure_logging

    configure_logging()
    typer.run(main)
