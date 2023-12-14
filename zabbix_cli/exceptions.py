from __future__ import annotations

import functools
from typing import Any
from typing import NoReturn
from typing import Optional
from typing import Protocol
from typing import runtime_checkable
from typing import Type


class ZabbixCLIError(Exception):
    """Base exception class for ZabbixCLI exceptions."""


class ConfigError(ZabbixCLIError):
    """Exception raised when there is a configuration error."""


class CommandFileError(ZabbixCLIError):
    """Exception raised when there is a bulk command file error."""


class AuthTokenFileError(ZabbixCLIError):
    """Exception raised when there is an auth token file error."""


class AuthTokenError(ZabbixCLIError):  # NOTE: unused
    """Exception raised when there is an auth token error."""


class ZabbixAPIException(ZabbixCLIError):
    # Extracted from pyzabbix, hence *Exception suffix instead of *Error
    """generic zabbix api exception
    code list:
         -32602 - Invalid params (eg already exists)
         -32500 - no permissions
    """


class ZabbixNotFoundError(ZabbixAPIException):
    """A Zabbix API resource was not found."""


class Exiter(Protocol):
    """Protocol class for exit function that can be passed to an
    exception handler function.

    See Also
    --------
    [zabbix_cli.exceptions.HandleFunc][]
    """

    def __call__(
        self,
        message: str,
        code: int = ...,
        exception: Optional[Exception] = ...,
        **kwargs: Any,
    ) -> NoReturn:
        ...


@runtime_checkable
class HandleFunc(Protocol):
    """Interface for exception handler functions.

    They take any exception and an Exiter function as the arguments
    and exit with the appropriate message after running any necessary
    cleanup and/or logging.
    """

    def __call__(self, e: Any) -> NoReturn:
        ...


def handle_notraceback(e: Exception) -> NoReturn:
    """Handles an exception with no traceback in console.
    The exception is logged with a traceback in the log file."""
    get_exit_err()(str(e), exception=e, exc_info=True)


def handle_zabbix_api_exception(e: ZabbixAPIException) -> NoReturn:
    """Handles a ZabbixAPIException."""
    from zabbix_cli.auth import clear_auth_token_file
    from zabbix_cli.state import get_state

    state = get_state()

    # If we have a stale auth token, we need to clear it.
    if (
        state.is_config_loaded
        and state.config.app.use_auth_token_file
        and "re-login" in e.args[0]
    ):
        clear_auth_token_file()
        get_exit_err()(
            "Your auth token has expired. Please re-run the command to login."
        )
    else:
        # TODO: extract the reason for the error from the exception here
        # and add it to the message.
        # if e.__cause__ and e.__cause__.args:
        #     e.args
        handle_notraceback(e)


EXC_HANDLERS = {
    ZabbixCLIError: handle_notraceback,
    ZabbixAPIException: handle_zabbix_api_exception,  # NOTE: use different strategy for this?
}  # type: dict[type[Exception], HandleFunc]
"""Mapping of exception types to exception handling strategies."""


def get_exception_handler(type_: Type[Exception]) -> Optional[HandleFunc]:
    """Returns the exception handler for the given exception type."""
    handler = EXC_HANDLERS.get(type_, None)
    if handler:
        return handler
    if type_.__bases__:
        for base in type_.__bases__:
            handler = get_exception_handler(base)
            if handler:
                return handler
    return None


def handle_exception(e: Exception) -> NoReturn:
    """Handles an exception and exits with the appropriate message."""
    handler = get_exception_handler(type(e))
    if not handler:
        raise e
    handler(e)


@functools.lru_cache(maxsize=1)
def get_exit_err() -> Exiter:
    """Cached lazy-import of `zabbix_cli.output.console.exit_err`.
    Avoids circular imports. Because we can "exit" multiple times in the
    REPL, it's arguably worth caching the import this way.
    """
    from zabbix_cli.output.console import exit_err as _exit_err

    return _exit_err
