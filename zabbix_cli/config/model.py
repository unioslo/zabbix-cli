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

import logging
from pathlib import Path
from typing import Any
from typing import List
from typing import Optional

from pydantic import AliasChoices
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import SecretStr
from pydantic import ValidationInfo
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator
from typing_extensions import Self

from zabbix_cli._v2_compat import CONFIG_PRIORITY as CONFIG_PRIORITY_LEGACY
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.config.utils import find_config
from zabbix_cli.config.utils import load_config_conf
from zabbix_cli.config.utils import load_config_toml
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.dirs import LOGS_DIR
from zabbix_cli.exceptions import ConfigError
from zabbix_cli.logs import LogLevelStr
from zabbix_cli.pyzabbix.enums import ExportFormat


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
    username: str = Field(
        default="Admin",
        # Changed in V3: system_id -> username
        validation_alias=AliasChoices("username", "system_id"),
    )
    password: SecretStr = Field(default="", exclude=True)
    verify_ssl: bool = Field(
        default=True,
        # Changed in V3: cert_verify -> verify_ssl
        validation_alias=AliasChoices("verify_ssl", "cert_verify"),
    )
    timeout: Optional[int] = 0
    auth_token: Optional[SecretStr] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _validate_model(self) -> Self:
        # Convert 0 timeout to None
        if self.timeout == 0:
            self.timeout = None
        return self

    @field_serializer("timeout", when_used="json")
    def _serialize_timeout(self, timeout: Optional[int]) -> int:
        """Represent None timeout as 0 in serialized output."""
        return timeout if timeout is not None else 0


class AppConfig(BaseModel):
    username: str = Field(
        default="",
        validation_alias=AliasChoices("username", "system_id"),
        # DEPRECATED: Use `api.username` instead
        exclude=True,
    )

    default_hostgroups: List[str] = Field(
        default=["All-hosts"],
        # Changed in V3: default_hostgroup -> default_hostgroups
        validation_alias=AliasChoices("default_hostgroups", "default_hostgroup"),
    )
    default_admin_usergroups: List[str] = Field(
        default=[],
        # Changed in V3: default_admin_usergroup -> default_admin_usergroups
        validation_alias=AliasChoices(
            "default_admin_usergroups", "default_admin_usergroup"
        ),
    )
    default_create_user_usergroups: List[str] = Field(
        default=[],
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
    export_directory: Path = Field(
        default=EXPORT_DIR,
        # Changed in V3: default_directory_exports -> export_directory
        validation_alias=AliasChoices("default_directory_exports", "export_directory"),
    )
    export_format: ExportFormat = Field(
        # Changed in V3: Config options are now lower-case by default,
        #                but we also allow upper-case for backwards-compatibility
        #                i.e. both "json" and "JSON" are valid
        # Changed in V3: Default format is now JSON
        default=ExportFormat.JSON,
        # Changed in V3: default_export_format -> export_format
        validation_alias=AliasChoices("default_export_format", "export_format"),
    )
    export_timestamps: bool = Field(
        default=False,
        # Changed in V3: include_timestamp_export_filename -> export_timestamps
        validation_alias=AliasChoices(
            "include_timestamp_export_filename", "export_timestamps"
        ),
    )
    use_colors: bool = True
    use_auth_token_file: bool = True
    auth_token_file: Path = AUTH_TOKEN_FILE
    auth_file: Path = AUTH_FILE
    use_paging: bool = False
    output_format: OutputFormat = OutputFormat.TABLE
    history: bool = True
    history_file: Path = DATA_DIR / "history"

    # Legacy options
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

    @model_validator(mode="after")
    def ensure_history_file(self) -> Self:
        if not self.history or self.history_file.exists():
            return self
        # If user passes in path to non-existent directory, we have to create that too
        # TODO: add some abstraction for creating files & directories and raising exceptions
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self.history_file.touch(exist_ok=True)
        except OSError as e:
            # TODO: print path to config file in error message
            raise ConfigError(
                f"Unable to create history file {self.history_file}. Disable history or specify a different path in the configuration file."
            ) from e
        return self


class LoggingConfig(BaseModel):
    enabled: bool = Field(
        default=True,
        # Changed in V3: logging -> enabled (we also allow enable [why?])
        validation_alias=AliasChoices("logging", "enabled", "enable"),
    )
    log_level: LogLevelStr = "ERROR"
    log_file: Optional[Path] = (
        # TODO: define this default path elsewhere
        LOGS_DIR / "zabbix-cli.log"
    )

    @field_validator("log_file", mode="before")
    @classmethod
    def _empty_string_is_none(cls, v: Any) -> Any:
        """Passing in an empty string to `log_file` sets it to `None`,
        while omitting the option altogether sets it to the default.

        Examples:
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
    config_path: Optional[Path] = Field(default=None, exclude=True)

    @classmethod
    def sample_config(cls) -> Config:
        """Get a sample configuration."""
        return cls(api=APIConfig(url="https://zabbix.example.com", username="Admin"))

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
                logging.warning("Using legacy config file (%s)", fp)
                conf = load_config_conf(fp)
                # Use legacy JSON format if we find a legacy config file
                conf.setdefault("zabbix_config", {}).setdefault(
                    "legacy_json_format", True
                )
            else:
                # Failed to find both .toml and .conf files
                from zabbix_cli.config.utils import init_config

                fp = init_config()
                if not fp.exists():
                    raise ConfigError(
                        "Failed to create configuration file. Run [command]zabbix-cli-init[/] to create one."
                    )
                return cls.from_file(fp)
        else:
            conf = load_config_toml(fp)
        return cls(**conf, config_path=fp)

    @model_validator(mode="after")
    def _assign_legacy_options(self) -> Self:
        """Ensures that options that have moved from one section to another are copied
        to the new section. I.e. `app.username` -> `api.username`.
        """
        # Only override if `api.username` is not set
        if self.app.username and not self.api.username:
            logging.warning(
                "Config option `app.username` is deprecated and will be removed. Use `api.username` instead."
            )
            self.api.username = self.app.username
        if not self.api.username:
            raise ConfigError("No username specified in the configuration file.")
        return self

    def as_toml(self) -> str:
        """Dump the configuration to a TOML string."""
        import tomli_w

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
                logging.error("unable to create directory %r", filename.parent)
                raise ConfigError(f"unable to create directory {filename.parent}")
        filename.write_text(self.as_toml())
