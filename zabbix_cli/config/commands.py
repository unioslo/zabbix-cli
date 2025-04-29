"""Configuration classes for Zabbix CLI commands."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices
from pydantic import Field

from zabbix_cli.config.base import BaseModel
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.pyzabbix.enums import ExportFormat


class CreateHost(BaseModel):
    """Configuration for the `create_host` command."""

    create_interface: bool = Field(
        default=True,
        description="Create a DNS/IP interface for the host automatically.",
    )
    hostgroups: list[str] = Field(
        default=[],
        validation_alias=AliasChoices(
            "hostgroups",  # v3.6
            "create_host_hostgroups",  # v3.0
            "create_host_hostgroup",  # v2
        ),
        description="Default host group to add hosts to.",
    )


class CreateNotificationUser(BaseModel):
    """Configuration for the `create_notification_user` command."""

    usergroups: list[str] = Field(
        default=[],
        # Changed in V3: default_notification_users_usergroup -> default_notification_users_usergroups
        validation_alias=AliasChoices(
            "usergroups",  # v3.6
            "default_notification_users_usergroups",  # v3.0
            "default_notification_users_usergroup",  # v2
        ),
        description=(
            "Default user groups to add notification users to when `--usergroups` is not provided."
        ),
    )


class CreateUser(BaseModel):
    """Configuration for the `create_user` command."""

    usergroups: list[str] = Field(
        default=[],
        validation_alias=AliasChoices(
            "usergroups",  # v3.6
            "default_create_user_usergroups",  # v3.0
            "default_create_user_usergroup",  # v2
        ),
        description=(
            "Default user groups to add users to when `--usergroups` is not provided."
        ),
    )


class CreateHostGroup(BaseModel):
    """Configuration for the `create_hostgroup` command."""

    ro_groups: list[str] = Field(
        default=[],
        validation_alias=AliasChoices(
            "ro_groups",  # v3.6
            "default_create_user_usergroups",  # v3.0
            "default_create_user_usergroup",  # v2
        ),
        description=(
            "Default user groups to give read-only permissions to groups "
            "when `--ro-groups` option is not provided."
        ),
    )
    rw_groups: list[str] = Field(
        default=[],
        validation_alias=AliasChoices(
            "rw_groups",  # v3.6
            "default_admin_usergroups",  # v3.0
            "default_admin_usergroup",  # v2
        ),
        description=(
            "Default user groups to give read/write permissions to groups "
            "when `--rw-groups` option is not provided."
        ),
    )


class ExportImport(BaseModel):
    """Shared configuration for `export_configuration` and `import_configuration` commands."""

    # Exports
    directory: Path = Field(
        default=EXPORT_DIR,
        validation_alias=AliasChoices(
            "directory",  # v3.6
            "export_directory",  # v3.0
            "default_directory_exports",  # v2
        ),
        description="Default directory to export files to.",
    )
    format: ExportFormat = Field(
        default=ExportFormat.JSON,
        validation_alias=AliasChoices(
            "format",  # v3.6
            "export_format",  # v3.0
            "default_export_format",  # v2
        ),
        description="Default export format.",
    )
    timestamps: bool = Field(
        default=False,
        # Changed in V3: include_timestamp_export_filename -> export_timestamps
        validation_alias=AliasChoices(
            "timestamps",  # v3.6
            "export_timestamps",  # v3.0
            "include_timestamp_export_filename",  # v2
        ),
        description="Include timestamps in exported filenames.",
    )


# Top-level class composed of individual classes for each command
class CommandConfig(BaseModel):
    """Configuration of commands."""

    create_host: CreateHost = Field(default_factory=CreateHost)
    create_hostgroup: CreateHostGroup = Field(default_factory=CreateHostGroup)
    create_notification_user: CreateNotificationUser = Field(
        default_factory=CreateNotificationUser
    )
    create_user: CreateUser = Field(default_factory=CreateUser)
    export: ExportImport = Field(
        default_factory=ExportImport,
        validation_alias=AliasChoices(
            # short-hand + command names
            "export",
            "import",
            "export_configuration",
            "import_configuration",
        ),
    )
