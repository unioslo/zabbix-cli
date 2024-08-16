"""Models for rendering results of commands.

Should not be imported on startup, as we don't want to build Pydantic models
until we actually need them - this has a massive startup time impact.

Each command module should have a corresponding module in this package that
defines the models for its results. i.e. `zabbix_cli.commands.host` should
define its result models in  `zabbix_cli.commands.results.host`.
"""

from __future__ import annotations
