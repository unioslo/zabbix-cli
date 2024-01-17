from __future__ import annotations

from typing import Any
from typing import NoReturn
from typing import Optional

import typer
from rich.console import Console

from zabbix_cli.logs import logger
from zabbix_cli.output.style import Icon
from zabbix_cli.output.style.color import bold
from zabbix_cli.output.style.color import green
from zabbix_cli.output.style.color import red
from zabbix_cli.output.style.color import yellow
from zabbix_cli.state import get_state


# stdout console used to print results
console = Console()

# stderr console used to print prompts, messages, etc.
err_console = Console(
    stderr=True,
    highlight=False,
    soft_wrap=True,
)


RESERVED_EXTRA_KEYS = (
    "name",
    "level",
    "pathname",
    "lineno",
    "msg",
    "args",
    "exc_info",
    "func",
    "sinfo",
)


def get_extra_dict(**kwargs: Any) -> dict[str, Any]:
    """Format the extra dict for logging. Renames some keys to avoid
    collisions with the default keys.

    See: https://docs.python.org/3.11/library/logging.html#logging.LogRecord"""
    for k, v in list(kwargs.items()):  # must be list to change while iterating
        if k in RESERVED_EXTRA_KEYS:
            kwargs[f"{k}_"] = v  # add trailing underscore to avoid collision
            del kwargs[k]
    return kwargs


def debug_kv(key: str, value: Any) -> None:
    """Print and log a key value pair."""
    msg = f"[bold]{key:<20}:[/bold] {value}"
    logger.debug(msg, extra=get_extra_dict(key=key, value=value))
    err_console.print(msg)


def debug(message: str, icon: str = "", *args, **kwargs) -> None:
    """Log with INFO level and print an informational message."""
    logger.debug(message, extra=get_extra_dict(**kwargs))
    err_console.print(message)


def info(message: str, icon: str = Icon.INFO, *args, **kwargs) -> None:
    """Log with INFO level and print an informational message."""
    logger.info(message, extra=get_extra_dict(**kwargs))
    err_console.print(f"{green(icon)} {message}")


def success(message: str, icon: str = Icon.OK, **kwargs) -> None:
    """Log with INFO level and print a success message."""
    logger.info(message, extra=get_extra_dict(**kwargs))
    err_console.print(f"{green(icon)} {message}")


def warning(message: str, icon: str = Icon.WARNING, **kwargs) -> None:
    """Log with WARNING level and optionally print a warning message."""
    logger.warning(message, extra=get_extra_dict(**kwargs))
    err_console.print(bold(yellow(f"{icon} {message}")))


def error(
    message: str, icon: str = Icon.ERROR, exc_info: bool = False, **kwargs
) -> None:
    """Log with ERROR level and print an error message."""
    logger.error(message, extra=get_extra_dict(**kwargs), exc_info=exc_info)
    err_console.print(bold(red(f"{icon} ERROR: {message}")))


def print_help(ctx: typer.Context) -> None:
    console.print(ctx.command.get_help(ctx))
    raise SystemExit(1)


def exit_ok(message: Optional[str] = None, code: int = 0, **kwargs) -> NoReturn:
    """Logs a message with INFO level and exits with the given code (default: 0)

    Parameters
    ----------
    message : str
        Message to print.
    code : int, optional
        Exit code, by default 0
    **kwargs
        Additional keyword arguments to pass to the extra dict.
    """
    if message:
        info(message, **kwargs)
    raise SystemExit(code)


def exit_err(
    message: str, code: int = 1, exception: Optional[Exception] = None, **kwargs: Any
) -> NoReturn:
    """Logs a message with ERROR level and exits with the given
    code (default: 1).

    Parameters
    ----------
    message : str
        Message to print.
    code : int, optional
        Exit code, by default 1
    **kwargs
        Additional keyword arguments to pass to the extra dict.
    """
    state = get_state()
    if state.is_config_loaded and state.config.app.output_format == "json":
        from zabbix_cli.output.render import render_json
        from zabbix_cli.models import Result, ReturnCode

        errors = []  # type: list[str]
        if exception:
            errors.extend(str(a) for a in exception.args)
            if exception.__cause__:
                errors.extend(str(a) for a in exception.__cause__.args)
        render_json(
            Result(message=message, return_code=ReturnCode.ERROR, errors=errors)
        )
    else:
        error(message, **kwargs)
    raise SystemExit(code)
