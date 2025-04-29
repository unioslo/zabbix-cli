"""Configuration classes for Zabbix CLI commands."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices
from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self

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


class _CreateGroupBase(BaseModel):
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


class CreateHostGroup(_CreateGroupBase):
    """Configuration for the `create_hostgroup` command."""


class CreateTemplateGroup(_CreateGroupBase):
    """Configuration for the `create_templategroup` command."""


class CreateHostOrTemplateGroup(_CreateGroupBase):
    """Shared config for `create_hostgroup` and `create_templategroup` commands.

    Can be used to configure both commands at once. Has no effect if
    `create_hostgroup` or `create_templategroup` is set.
    """


class ExportImport(BaseModel):
    """Shared configuration for `export_configuration` and `import_configuration` commands."""

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

    # Hosts
    create_host: CreateHost = Field(default_factory=CreateHost)

    # Groups
    create_hostgroup: CreateHostGroup = Field(default_factory=CreateHostGroup)
    create_templategroup: CreateTemplateGroup = Field(
        default_factory=CreateTemplateGroup,
    )

    # Users
    create_user: CreateUser = Field(default_factory=CreateUser)
    create_notification_user: CreateNotificationUser = Field(
        default_factory=CreateNotificationUser
    )

    # Export
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

    # Custom configs (shared between commands, etc.)
    create_group: CreateHostOrTemplateGroup = Field(
        default_factory=CreateHostOrTemplateGroup,
    )

    @model_validator(mode="after")
    def check_create_group(self) -> Self:
        """Fallback to `create_group` if `create_{host,template}group` are not set."""
        if (
            # create_{host,template}group are not set
            all(
                f not in self.model_fields_set
                for f in ["create_hostgroup", "create_templategroup"]
            )
            # Shared config is set
            and "create_group" in self.model_fields_set
        ):
            self.create_hostgroup = self.create_hostgroup.model_validate(
                self.create_group, from_attributes=True
            )
            self.create_templategroup = self.create_templategroup.model_validate(
                self.create_group, from_attributes=True
            )
        return self
