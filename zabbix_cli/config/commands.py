"""Configuration classes for Zabbix CLI commands."""

from __future__ import annotations

from zabbix_cli.config.base import BaseModel


class CreateHost(BaseModel):
    """Configuration for the `create_host` command."""

    create_interface: bool = True
