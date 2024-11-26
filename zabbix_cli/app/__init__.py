from __future__ import annotations

from zabbix_cli.commands import bootstrap_commands  # type: ignore # noqa: E402, F401

from .app import *  # noqa: F403 # wildcard import to avoid circular import (why?)
from .app import StatefulApp  # explicit import for type checker

app = StatefulApp(
    name="zabbix-cli",
    help="Zabbix-CLI is a command line interface for Zabbix.",
    add_completion=True,
    rich_markup_mode="rich",
)

# Import commands to register them with the app
from zabbix_cli.commands import cli  # type: ignore # noqa: E402, F401, I001
from zabbix_cli.commands import export  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import host  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import host_interface  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import hostgroup  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import host_monitoring  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import item  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import macro  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import maintenance  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import media  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import problem  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import proxy  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import template  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import templategroup  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import user  # type: ignore # noqa: E402, F401
from zabbix_cli.commands import usergroup  # type: ignore # noqa: E402, F401


# Import dev commands
# TODO: Disable by default, enable with a flag.
bootstrap_commands()
