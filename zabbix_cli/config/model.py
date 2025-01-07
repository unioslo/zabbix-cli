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

import functools
import logging
from pathlib import Path
from typing import Any
from typing import Optional
from typing import TypeVar
from typing import Union
from typing import overload

from pydantic import AliasChoices
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import PrivateAttr
from pydantic import RootModel
from pydantic import SecretStr
from pydantic import SerializationInfo
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic import ValidationInfo
from pydantic import field_serializer
from pydantic import field_validator
from pydantic import model_validator
from typing_extensions import Self

from zabbix_cli._v2_compat import CONFIG_PRIORITY as CONFIG_PRIORITY_LEGACY
from zabbix_cli.bulk import BulkRunnerMode
from zabbix_cli.config.constants import AUTH_FILE
from zabbix_cli.config.constants import AUTH_TOKEN_FILE
from zabbix_cli.config.constants import HISTORY_FILE
from zabbix_cli.config.constants import LOG_FILE
from zabbix_cli.config.constants import SESSION_FILE
from zabbix_cli.config.constants import OutputFormat
from zabbix_cli.config.constants import SecretMode
from zabbix_cli.config.utils import check_deprecated_fields
from zabbix_cli.config.utils import find_config
from zabbix_cli.config.utils import get_deprecated_fields_set
from zabbix_cli.config.utils import load_config_conf
from zabbix_cli.config.utils import load_config_toml
from zabbix_cli.config.utils import update_deprecated_fields
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.exceptions import ConfigError
from zabbix_cli.exceptions import ConfigOptionNotFound
from zabbix_cli.exceptions import PluginConfigTypeError
from zabbix_cli.exceptions import ZabbixCLIFileError
from zabbix_cli.logs import LogLevelStr
from zabbix_cli.pyzabbix.enums import ExportFormat
from zabbix_cli.utils.fs import mkdir_if_not_exists

T = TypeVar("T")

logger = logging.getLogger("zabbix_cli.config")


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    _deprecation_checked: bool = PrivateAttr(default=False)
    """Has performed a deprecaction check for the fields on the model."""

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

    @model_validator(mode="after")
    def _check_deprecated_fields(self) -> Self:
        """Check for deprecated fields and log warnings."""
        if not self._deprecation_checked:
            check_deprecated_fields(self)
            self._deprecation_checked = True
        return self


class APIConfig(BaseModel):
    """Configuration for the Zabbix API."""

    url: str = Field(
        default="",
        # Changed in V3: zabbix_api_url -> url
        validation_alias=AliasChoices("url", "zabbix_api_url"),
        description="URL of the Zabbix API host. Should not include `/api_jsonrpc.php`.",
        examples=["https://zabbix.example.com"],
    )
    username: str = Field(
        default="Admin",
        # Changed in V3: system_id -> username
        validation_alias=AliasChoices("username", "system_id"),
        description="Username for the Zabbix API.",
        examples=["Admin"],
    )
    password: SecretStr = Field(
        default=SecretStr(""),
        description="Password for user.",
        examples=["zabbix"],
    )
    auth_token: SecretStr = Field(
        default=SecretStr(""),
        description="API auth token.",
        examples=["API_TOKEN_123"],
    )
    verify_ssl: bool = Field(
        default=True,
        # Changed in V3: cert_verify -> verify_ssl
        validation_alias=AliasChoices("verify_ssl", "cert_verify"),
        description="Verify SSL certificate of the Zabbix API host.",
    )
    timeout: Optional[int] = Field(
        default=0,
        description="API request timeout in seconds.",
    )

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

    @field_serializer("password", "auth_token", when_used="json")
    def dump_secret(self, v: Any, info: SerializationInfo) -> Any:
        """Dump secrets if enabled in serialization context."""
        if not isinstance(v, SecretStr):
            logger.debug("%s from field %s is not a SecretStr", v, info)
            return v

        mode = SecretMode.from_context(info.context)
        if mode == SecretMode.PLAIN:
            return v.get_secret_value()
        elif mode == SecretMode.MASK:
            return str(v)  # SecretStr masks by default
        else:  # fall back on hidden otherwise
            return ""


class OutputConfig(BaseModel):
    """Configuration for output formatting."""

    format: OutputFormat = Field(
        default=OutputFormat.TABLE,
        description="Default output format.",
    )
    color: bool = Field(
        default=True,
        description="Use colors in terminal output.",
    )
    paging: bool = Field(
        default=False,
        description="Use paging in terminal output.",
    )
    theme: str = Field(
        default="default",
        description="Color theme to use.",
        exclude=True,
    )

    @field_validator("format", mode="before")
    @classmethod
    def _ignore_enum_case(cls, v: Any) -> Any:
        """Ignore case when validating enum value."""
        if isinstance(v, str):
            return v.lower()
        return v


class AppConfig(BaseModel):
    """Configuration for app defaults and behavior."""

    # Zabbix defaults
    default_hostgroups: list[str] = Field(
        default=["All-hosts"],
        # Changed in V3: default_hostgroup -> default_hostgroups
        validation_alias=AliasChoices("default_hostgroups", "default_hostgroup"),
        description=(
            "Default host groups to assign to hosts created with `create_host`. "
            "Hosts are always added to these groups unless `--no-default-hostgroup` "
            "is provided."
        ),
    )
    default_admin_usergroups: list[str] = Field(
        default=[],
        # Changed in V3: default_admin_usergroup -> default_admin_usergroups
        validation_alias=AliasChoices(
            "default_admin_usergroups", "default_admin_usergroup"
        ),
        description=(
            "Default user groups to give read/write permissions to groups "
            "created with `create_hostgroup` and `create_templategroup` "
            "when `--rw-groups` option is not provided."
        ),
    )
    default_create_user_usergroups: list[str] = Field(
        default=[],
        # Changed in V3: default_create_user_usergroup -> default_create_user_usergroups
        validation_alias=AliasChoices(
            "default_create_user_usergroups", "default_create_user_usergroup"
        ),
        description=(
            "Default user groups to add users created with `create_user` "
            "to when `--usergroups` is not provided."
        ),
    )
    default_notification_users_usergroups: list[str] = Field(
        default=["All-notification-users"],
        # Changed in V3: default_notification_users_usergroup -> default_notification_users_usergroups
        validation_alias=AliasChoices(
            "default_notification_users_usergroups",
            "default_notification_users_usergroup",
        ),
        description=(
            "Default user groups to add notification users created with "
            "`create_notification_user` to when `--usergroups` is not provided."
        ),
    )

    # Exports
    export_directory: Path = Field(
        default=EXPORT_DIR,
        # Changed in V3: default_directory_exports -> export_directory
        validation_alias=AliasChoices("default_directory_exports", "export_directory"),
        description="Default directory to export files to.",
    )
    export_format: ExportFormat = Field(
        # Changed in V3: Config options are now lower-case by default,
        #                but we also allow upper-case for backwards-compatibility
        #                i.e. both "json" and "JSON" are valid
        # Changed in V3: Default format is now JSON
        default=ExportFormat.JSON,
        # Changed in V3: default_export_format -> export_format
        validation_alias=AliasChoices("default_export_format", "export_format"),
        description="Default export format.",
    )
    export_timestamps: bool = Field(
        default=False,
        # Changed in V3: include_timestamp_export_filename -> export_timestamps
        validation_alias=AliasChoices(
            "include_timestamp_export_filename", "export_timestamps"
        ),
        description="Include timestamps in exported filenames.",
    )

    # Auth
    use_session_file: bool = Field(
        default=True,
        validation_alias=AliasChoices("use_session_file", "use_auth_token_file"),
        description="Use session file for storing API session IDs for persistent sessions.",
    )

    session_file: Path = Field(
        default=SESSION_FILE,
        description="Path to session file.",
    )
    auth_token_file: Path = Field(
        default=AUTH_TOKEN_FILE,
        description="Path to legacy auth token file.",
        deprecated=True,
    )
    auth_file: Path = Field(
        default=AUTH_FILE,
        description="Path to auth file.",
    )
    # TODO: rename symbol to allow_insecure_auth
    allow_insecure_auth_file: bool = Field(
        default=True,
        # Changed in V3: allow_insecure_authfile -> allow_insecure_auth_file
        validation_alias=AliasChoices(
            "allow_insecure_auth",
            "allow_insecure_auth_file",
            "allow_insecure_authfile",
        ),
    )

    # History
    history: bool = Field(
        default=True,
        description="Enable command history.",
    )
    history_file: Path = Field(
        default=HISTORY_FILE,
        description="Path to history file.",
    )

    bulk_mode: BulkRunnerMode = Field(
        default=BulkRunnerMode.STRICT,
        description="Bulk mode error handling.",
    )

    # Deprecated/moved fields
    output_format: OutputFormat = Field(
        default=OutputFormat.TABLE,
        deprecated=True,
        json_schema_extra={"replacement": "app.output.format"},
        exclude=True,
    )
    use_colors: bool = Field(
        default=True,
        deprecated=True,
        json_schema_extra={"replacement": "app.output.color"},
        exclude=True,
    )
    use_paging: bool = Field(
        default=False,
        deprecated=True,
        json_schema_extra={"replacement": "app.output.paging"},
        exclude=True,
    )
    system_id: str = Field(
        default="",
        validation_alias=AliasChoices("username", "system_id"),
        deprecated=True,
        json_schema_extra={"replacement": "api.username"},
        exclude=True,
    )

    # Legacy options
    legacy_json_format: bool = Field(
        default=False,
        description="Use legacy JSON format.",
    )
    """Mimicks V2 behavior where the JSON output was ALWAYS a dict, where
    each entry was stored under the keys "0", "1", "2", etc.
    """

    is_legacy: bool = Field(  # TODO: use PrivateAttr instead of Field
        default=False,
        exclude=True,
    )
    """Marks whether the configuration was loaded from a legacy config file."""

    # Sub-models
    output: OutputConfig = Field(default_factory=OutputConfig)

    @field_validator(
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
        if not self.history:
            return self

        if self.history_file.exists():
            if self.history_file.is_file():
                return self
            raise ConfigError(
                f"History file {self.history_file} is a directory, not a file. Disable history or specify a different path in the configuration file."
            )

        # If user passes in path to non-existent directory, we have to create that too
        # TODO: add some abstraction for creating files & directories and raising exceptions
        try:
            mkdir_if_not_exists(self.history_file.parent)
        except ZabbixCLIFileError as e:
            # TODO: print path to config file in error message
            raise ConfigError(
                f"Unable to create history file {self.history_file}. Disable history or specify a different path in the configuration file."
            ) from e
        return self


class LoggingConfig(BaseModel):
    """Configuration for application logs."""

    enabled: bool = Field(
        default=True,
        # Changed in V3: logging -> enabled (we also allow enable [why?])
        validation_alias=AliasChoices("logging", "enabled", "enable"),
        description="Enable logging.",
    )
    log_level: LogLevelStr = Field(
        default="INFO",
        description="Log level.",
    )
    log_file: Optional[Path] = Field(
        # TODO: define this default path elsewhere
        default=LOG_FILE,
        description=(
            "File for storing logs. "
            "Can be omitted to log to stderr (**warning:** NOISY)."
        ),
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


# Can consider moving this elsewhere
@functools.cache
def _get_type_adapter(type: type[T]) -> TypeAdapter[T]:
    """Get a type adapter for a given type."""
    return TypeAdapter(type)


NotSet = object()


class PluginConfig(BaseModel):
    module: str = ""
    """Name or path to module to load.

    Should always be specified for plugins loaded from local modules.
    Can be omitted for plugins loaded from entry points.
    TOML table name is used as the module name for entry point plugins."""

    enabled: bool = True
    optional: bool = False
    """Do not raise an error if the plugin fails to load."""

    model_config = ConfigDict(extra="allow")

    # No default no type
    @overload
    def get(self, key: str) -> Any: ...

    # Type with no default
    @overload
    def get(self, key: str, *, type: type[T]) -> T: ...

    # No type with default
    @overload
    def get(self, key: str, default: T) -> Any | T: ...

    # Type with default
    @overload
    def get(
        self,
        key: str,
        default: T,
        type: type[T],
    ) -> T: ...

    # Union type with no default
    @overload
    def get(
        self,
        key: str,
        *,
        type: Optional[type[T]],
    ) -> Optional[T]: ...

    # Union type with default
    @overload
    def get(
        self,
        key: str,
        default: Optional[T],
        type: Optional[type[T]],
    ) -> Optional[T]: ...

    def get(
        self,
        key: str,
        default: Union[T, Any] = NotSet,
        type: Optional[type[T]] = object,
    ) -> Union[T, Optional[T], Any]:
        """Get a plugin configuration value by key.

        Optionally validate the value as a specific type.
        """
        try:
            if default is not NotSet:
                attr = getattr(self, key, default)
            else:
                attr = getattr(self, key)
            if type is object:
                return attr
            adapter = _get_type_adapter(type)
            return adapter.validate_python(attr)
        except AttributeError:
            raise ConfigOptionNotFound(f"Plugin configuration key '{key}' not found")
        except ValidationError as e:
            raise PluginConfigTypeError(
                f"Plugin config key '{key}' failed to validate as type {type}: {e}"
            ) from e

    def set(self, key: str, value: Any) -> None:
        """Set a plugin configuration value by key."""
        setattr(self, key, value)


class PluginsConfig(RootModel[dict[str, PluginConfig]]):
    root: dict[str, PluginConfig] = Field(default_factory=dict)

    def get(self, key: str, strict: bool = False) -> Optional[PluginConfig]:
        """Get a plugin configuration by name."""
        conf = self.root.get(key)
        if conf is None and strict:
            raise ConfigError(f"Plugin {key} not found in configuration")
        return conf


class Config(BaseModel):
    """Configuration for the application."""

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
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)

    config_path: Optional[Path] = Field(default=None, exclude=True)
    sample: bool = Field(default=False, exclude=True)

    @model_validator(mode="after")
    def _set_deprecated_fields_in_new_location(self) -> Self:
        """Set values specified on deprecated fields in their new location.

        Only updates new fields if the old field is set and the new field is not.

        I.e. `app.username` -> `api.username`.
             `app.output_format` -> `app.output.format`.
        """
        # Guard against failure in case we have a config that cannot be updated
        # After all, this validator is added for _increased_ compatibility, not decreased
        try:
            update_deprecated_fields(self)
        except Exception as e:
            logger.error("Failed to update deprecated fields: %s", e)
        self.check_emit_upgrade_instructions()
        return self

    @classmethod
    def sample_config(cls) -> Config:
        """Get a sample configuration."""
        return cls(api=APIConfig(url="https://zabbix.example.com"), sample=True)

    @classmethod
    def from_file(cls, filename: Optional[Path] = None, init: bool = False) -> Config:
        """Load configuration from a file.

        Attempts to find a config file to load if none is specified.

        Prioritizes V3 .toml config files, but falls back
        to legacy V2 .conf config files if no .toml config file can be found.
        """
        if filename:
            fp = filename
        else:
            fp = find_config(filename)
            if (
                not fp
            ):  # We didn't find a .toml file, so try to find a legacy .conf file
                fp = find_config(filename, CONFIG_PRIORITY_LEGACY)

        # Failed to find both .toml and .conf files
        if not fp or not fp.exists():
            if init:
                from zabbix_cli.config.utils import init_config

                fp = init_config(config_file=filename)
                if not fp.exists():
                    raise ConfigError(
                        "Failed to create configuration file. Run [command]zabbix-cli-init[/] to create one."
                    )
            else:
                return cls.sample_config()

        if fp.suffix == ".conf":
            return cls.from_conf_file(fp)
        else:
            return cls.from_toml_file(fp)

    @classmethod
    def from_toml_file(cls, filename: Path) -> Config:
        """Load configuration from a TOML file."""
        conf = load_config_toml(filename)
        try:
            return cls(**conf, config_path=filename)
        except ValidationError as e:
            raise ConfigError(f"Invalid configuration file {filename}: {e}") from e
        except Exception as e:
            raise ConfigError(
                f"Failed to load configuration file {filename}: {e}"
            ) from e

    @classmethod
    def from_conf_file(cls, filename: Path) -> Config:
        """Load configuration from a legacy .conf file."""
        logging.info("Using legacy config file (%s)", filename)
        conf = load_config_conf(filename)
        # Use legacy JSON format if we load from a legacy .conf file
        # and mark the loaded config as stemming from a legacy config file
        conf.setdefault("zabbix_config", {}).setdefault("legacy_json_format", True)
        conf.setdefault("zabbix_config", {}).setdefault("is_legacy", True)
        try:
            return cls(**conf, config_path=filename)
        except ValidationError as e:
            raise ConfigError(
                f"Failed to validate legacy configuration file {filename}: {e}"
            ) from e
        except Exception as e:
            raise ConfigError(
                f"Failed to load legacy configuration file {filename}: {e}"
            ) from e

    def as_toml(self, secrets: SecretMode = SecretMode.MASK) -> str:
        """Dump the configuration to a TOML string."""
        import tomli_w

        try:
            return tomli_w.dumps(
                self.model_dump(
                    mode="json",
                    exclude_none=True,  # we shouldn't have any, but just in case
                    context={"secrets": secrets},
                )
            )
        except Exception as e:
            raise ConfigError(f"Failed to serialize configuration to TOML: {e}") from e

    def dump_to_file(
        self, filename: Path, secrets: SecretMode = SecretMode.HIDE
    ) -> None:
        """Dump the configuration to a TOML file."""
        try:
            mkdir_if_not_exists(filename.parent)
            filename.write_text(self.as_toml(secrets=secrets))
        except OSError as e:
            raise ConfigError(
                f"Failed to write configuration file {filename}: {e}"
            ) from e

    def check_emit_upgrade_instructions(self) -> None:
        from zabbix_cli.output.console import warning

        # TODO: Detmermine whether or not to prefix command with `zabbix-cli`
        #       based on whether or not we are in the REPL
        if self.app.is_legacy:
            warning(
                "Your configuration file is from an older version of Zabbix-CLI.\n"
                "  To update your config file to the new format, run:\n"
                "  [command]zabbix-cli migrate_config[/]\n"
                "  For more information, see the documentation."
            )
        else:
            deprecated_fields = get_deprecated_fields_set(self)
            if not deprecated_fields:
                return

            # If none of the deprecated fields have a replacement, we don't
            # need to inform the user about them. They can be safely ignored.
            if all(not field.replacement for field in deprecated_fields):
                return

            warning(
                "Your configuration file contains deprecated options.\n"
                "  To update your config file with the new options, run:\n"
                "  [command]zabbix-cli update_config[/]\n"
                "  For more information, see the documentation."
            )
