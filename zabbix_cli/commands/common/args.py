from __future__ import annotations

from typing import Any
from typing import Optional

import click
import typer
from click.types import ParamType
from typer.core import TyperGroup

from zabbix_cli.logs import logger


def get_limit_option(
    limit: Optional[int] = 0,
    resource: str = "results",
    long_option: str = "--limit",
    short_option: str = "-n",
) -> Any:  # TODO: Can we type this better?
    """Limit option factory."""
    return typer.Option(
        limit,
        long_option,
        short_option,
        help=f"Limit the number of {resource}. 0 to show all.",
    )


OPTION_LIMIT = get_limit_option(0)

ARG_TEMPLATE_NAMES_OR_IDS = typer.Argument(
    help="Template names or IDs. Comma-separated. Supports wildcards.",
    show_default=False,
)
ARG_HOSTNAMES_OR_IDS = typer.Argument(
    help="Hostnames or IDs. Comma-separated. Supports wildcards.",
    show_default=False,
)
ARG_GROUP_NAMES_OR_IDS = typer.Argument(
    help="Host/template group names or IDs. Comma-separated. Supports wildcards.",
    show_default=False,
)


class CommandParam(ParamType):
    """Command param type that resolves into a click Command."""

    name = "command"

    def convert(
        self, value: str, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> click.Command:
        if not value:
            self.fail("Missing command.", param, ctx)
        if not ctx:
            self.fail("No context.", param, ctx)
        root_ctx = ctx.find_root()
        root_command = root_ctx.command

        if not isinstance(root_command, TyperGroup):
            logger.error(
                "Root context of %s is not a TyperGroup, unable to show help",
                root_command,
            )
            self.fail(f"Unable to show help for '{value}'")

        cmd = root_command.get_command(root_ctx, value)
        if not cmd:
            self.fail(f"Command '{value}' not found.")
        return cmd
