from __future__ import annotations

from typing import Any
from typing import NoReturn
from typing import Optional

from rich.console import Console

from zabbix_cli.logs import logger
from zabbix_cli.output.style import Icon
from zabbix_cli.output.style.color import bold
from zabbix_cli.output.style.color import green
from zabbix_cli.output.style.color import red
from zabbix_cli.output.style.color import yellow


# stdout console used to print results
console = Console()

# stderr console used to print prompts, messages, etc.
err_console = Console(
    stderr=True,
    highlight=False,
    soft_wrap=True,
)


def info(message: str, icon: str = Icon.INFO, *args, **kwargs) -> None:
    """Log with INFO level and print an informational message."""
    logger.info(message, extra=dict(**kwargs))
    err_console.print(f"{green(icon)} {message}")


def success(message: str, icon: str = Icon.OK, **kwargs) -> None:
    """Log with DEBUG level and print a success message."""
    logger.debug(message, extra=dict(**kwargs))
    err_console.print(f"{green(icon)} {message}")


def warning(message: str, icon: str = Icon.WARNING, **kwargs) -> None:
    """Log with WARNING level and optionally print a warning message."""
    logger.warning(message, extra=dict(**kwargs))
    err_console.print(bold(f"{yellow(icon)} {message}"))


def error(
    message: str, icon: str = Icon.ERROR, exc_info: bool = False, **kwargs
) -> None:
    """Log with ERROR level and print an error message."""
    logger.error(message, extra=dict(**kwargs), exc_info=exc_info)
    err_console.print(bold(f"{red(icon)} {message}"))


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


def exit_err(message: str, code: int = 1, **kwargs: Any) -> NoReturn:
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
    error(message, **kwargs)
    raise SystemExit(code)
