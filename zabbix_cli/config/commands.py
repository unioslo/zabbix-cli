"""Configuration classes for Zabbix CLI commands."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import AliasChoices
from pydantic import Field
from pydantic import model_validator
from typing_extensions import Self

from zabbix_cli.config.base import BaseModel
from zabbix_cli.dirs import EXPORT_DIR
from zabbix_cli.pyzabbix.enums import ExportFormat

logger = logging.getLogger(__name__)


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

    def __bool__(self) -> bool:
        return bool(self.ro_groups or self.rw_groups)


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
    create_group: CreateHostOrTemplateGroup = Field(
        default_factory=CreateHostOrTemplateGroup,
    )
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
            # short-hand + command + combined names
            "export",
            "import",
            "export_configuration",
            "import_configuration",
            "export_import",
        ),
    )

    @model_validator(mode="after")
    def check_create_group(self) -> Self:
        """Fallback to `create_group` if `create_{host,template}group` are not set."""
        if (
            # one or both of create_{host,template}group is not set/empty
            any(not f for f in [self.create_hostgroup, self.create_templategroup])
            # Shared config is defined
            and "create_group" in self.model_fields_set
            # and has at least one type of group defined
            and (self.create_group.ro_groups or self.create_group.rw_groups)
        ):
            # Only override if empty/not set
            if not self.create_hostgroup:
                self.create_hostgroup = self.create_hostgroup.model_validate(
                    self.create_group, from_attributes=True
                )
            if not self.create_templategroup:
                self.create_templategroup = self.create_templategroup.model_validate(
                    self.create_group, from_attributes=True
                )
        return self

    @model_validator(mode="before")
    @classmethod
    def check_export_import(cls, data: Any) -> Any:
        """Emit warning if multiple export/import aliases are used."""
        if not isinstance(data, dict):
            return data

        if field := cls.model_fields.get("export"):
            if isinstance(field.validation_alias, AliasChoices):
                aliases = field.validation_alias.choices
                # NOTE: we assume alias order is identical to definition order
                # Coerce to str, even though we shouldn't have any AliasPath here
                found = [str(alias) for alias in aliases if alias in data]
                if len(found) > 1:
                    logger.warning(
                        "Multiple export/import configuration sections found (%s). "
                        "Using section: [app.commands.%s]",
                        ", ".join(f"[app.commands.{f}]" for f in found),
                        found[0],
                    )
        return data  # pyright: ignore[reportUnknownVariableType]
