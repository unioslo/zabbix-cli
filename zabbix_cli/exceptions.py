from __future__ import annotations

import functools
from typing import TYPE_CHECKING
from typing import Any
from typing import NoReturn
from typing import Optional
from typing import Protocol
from typing import runtime_checkable

if TYPE_CHECKING:
    from httpx import ConnectError
    from httpx import RequestError
    from httpx import Response as HTTPResponse
    from pydantic import BaseModel
    from pydantic import ValidationError

    from zabbix_cli.pyzabbix.types import ParamsType
    from zabbix_cli.pyzabbix.types import ZabbixAPIResponse


class ZabbixCLIError(Exception):
    """Base exception class for ZabbixCLI exceptions."""


class ZabbixCLIFileError(ZabbixCLIError, OSError):
    """Errors related to reading/writing files."""


class ZabbixCLIFileNotFoundError(ZabbixCLIError, FileNotFoundError):
    """Errors related to reading/writing files."""


class ConfigError(ZabbixCLIError):
    """Error with configuration file."""


class ConfigExistsError(ConfigError):
    """Configuration file already exists."""


class ConfigOptionNotFound(ConfigError):
    """Configuration option is missing from the loaded config."""


class CommandFileError(ZabbixCLIError):
    """Error running bulk commands from a file."""


class AuthError(ZabbixCLIError):
    """Base class for all authentication errors."""

    # NOTE: We might still run into the problem of expired tokens, which won't raise
    # this type of error, but instead raise a ZabbixAPIRequestError.
    # We should probably handle that in the client and raise the appropriate exception


class SessionFileError(AuthError):
    """Session file error."""


class SessionFileNotFoundError(SessionFileError, FileNotFoundError):
    """Session file does not exist."""


class SessionFilePermissionsError(SessionFileError):
    """Session file has incorrect permissions."""


class AuthTokenFileError(AuthError):
    """Auth token file error."""


class AuthTokenError(AuthError):
    """Auth token (not file) error."""


class PluginError(ZabbixCLIError):
    """Plugin error."""


class PluginConfigError(PluginError, ConfigError):
    """Plugin configuration error."""


class PluginConfigTypeError(PluginConfigError, TypeError):
    """Plugin configuration type error."""


class PluginLoadError(PluginError):
    """Error loading a plugin."""

    msg = "Error loading plugin '{plugin_name}'"

    def __init__(self, plugin_name: str, plugin_config: BaseModel | None) -> None:
        self.plugin_name = plugin_name
        self.plugin_config = plugin_config
        super().__init__(self.msg.format(plugin_name=plugin_name))


class PluginPostImportError(PluginLoadError):
    """Error running post-import configuration for a plugin."""

    msg = "Error running post-import configuration for plugin '{plugin_name}'"


class ZabbixAPIException(ZabbixCLIError):
    # Extracted from pyzabbix, hence *Exception suffix instead of *Error
    """Base exception class for Zabbix API exceptions."""

    def reason(self) -> str:
        return ""


class ZabbixAPIRequestError(ZabbixAPIException):
    """Zabbix API response error."""

    def __init__(
        self,
        *args: Any,
        params: Optional[ParamsType] = None,
        api_response: Optional[ZabbixAPIResponse] = None,
        response: Optional[HTTPResponse] = None,
    ) -> None:
        super().__init__(*args)
        self.params = params
        self.api_response = api_response
        self.response = response

    def reason(self) -> str:
        if self.api_response and self.api_response.error:
            reason = (
                f"({self.api_response.error.code}) {self.api_response.error.message}"
            )
            if self.api_response.error.data:
                reason += f" {self.api_response.error.data}"
        elif self.response and self.response.text:
            reason = self.response.text
        else:
            reason = str(self)
        return reason


class ZabbixAPITokenExpiredError(ZabbixAPIRequestError, AuthError):
    """Zabbix API token expired error."""


class ZabbixAPINotAuthorizedError(ZabbixAPIRequestError):
    """Zabbix API not authorized error."""


class ZabbixAPIResponseParsingError(ZabbixAPIRequestError):
    """Zabbix API request error."""


class ZabbixAPISessionExpired(ZabbixAPIRequestError):
    """Zabbix API session expired."""


class ZabbixAPICallError(ZabbixAPIException):
    """Zabbix API request error."""

    def __str__(self) -> str:
        msg = super().__str__()
        if self.__cause__ and isinstance(self.__cause__, ZabbixAPIRequestError):
            msg = f"{msg}: {self.__cause__.reason()}"
        return msg


class ZabbixAPILoginError(ZabbixAPICallError, AuthError):
    """Zabbix API login error."""


class ZabbixAPILogoutError(ZabbixAPICallError, AuthError):
    """Zabbix API logout error."""


class ZabbixNotFoundError(ZabbixAPICallError):
    """A Zabbix API resource was not found."""


class Exiter(Protocol):
    """Protocol class for exit function that can be passed to an
    exception handler function.

    See Also:
    --------
    [zabbix_cli.exceptions.HandleFunc][]
    """

    def __call__(
        self,
        message: str,
        code: int = ...,
        exception: Optional[Exception] = ...,
        **kwargs: Any,
    ) -> NoReturn: ...


@runtime_checkable
class HandleFunc(Protocol):
    """Interface for exception handler functions.

    They take any exception and an Exiter function as the arguments
    and exit with the appropriate message after running any necessary
    cleanup and/or logging.
    """

    def __call__(self, e: Any) -> NoReturn: ...


def get_cause_args(e: Optional[BaseException]) -> list[str]:
    """Retrieves all args as strings from all exceptions in the cause chain.
    Flattens the args into a single list.
    """
    args: list[str] = []
    while e:
        args.extend(get_exc_args(e))
        e = e.__cause__
    return args


def get_exc_args(e: BaseException) -> list[str]:
    """Returns the error message as a string."""
    args: list[str] = [str(arg) for arg in e.args]
    if isinstance(e, ZabbixAPIRequestError):
        args.append(e.reason())
    return args


def handle_notraceback(e: Exception) -> NoReturn:
    """Handles an exception with no traceback in console.
    The exception is logged with a traceback in the log file.
    """
    get_exit_err()(str(e), exception=e, exc_info=True)


def handle_validation_error(e: ValidationError) -> NoReturn:
    """Handles a Pydantic validation error."""
    # TODO: Use some very primitive heuristics to determine whether or not
    # the error is from an API response or somewhere else
    get_exit_err()(str(e), exception=e, exc_info=True)


def _fmt_request_error(e: RequestError, exc_type: str, reason: str) -> str:
    method = e.request.method
    url = e.request.url
    return f"{exc_type}: {method} {url} - {reason}"


def handle_connect_error(e: ConnectError) -> NoReturn:
    """Handles an httpx ConnectError."""
    # Simple heuristic here to determine cause
    if e.args and "connection refused" in str(e.args[0]).casefold():
        reason = "Connection refused"
    else:
        reason = str(e)
    msg = _fmt_request_error(e, "Connection error", reason)
    get_exit_err()(msg, exception=e, exc_info=False)


def handle_zabbix_api_exception(e: ZabbixAPIException) -> NoReturn:
    """Handles a ZabbixAPIException."""
    from zabbix_cli.state import get_state

    state = get_state()
    # If we have a stale auth token, we need to clear it.
    if (
        state.is_config_loaded
        and state.config.app.use_session_file
        and any("re-login" in arg for arg in get_cause_args(e))
    ):
        from zabbix_cli.auth import clear_auth_token_file
        from zabbix_cli.output.console import error

        # Clear token file and from the config object
        error("Auth token expired. You must re-authenticate.")
        clear_auth_token_file(state.config)
        if state.repl:  # Hack: run login flow again in REPL
            state.login()
        # NOTE: ideally we automatically re-run the command here, but that's
        # VERY hacky and could lead to unexpected behavior.
        raise SystemExit(1)  # Exit without a message
    else:
        # TODO: extract the reason for the error from the exception here
        # and add it to the message.
        handle_notraceback(e)


def get_exception_handler(type_: type[Exception]) -> Optional[HandleFunc]:
    """Returns the exception handler for the given exception type."""
    from httpx import ConnectError
    from pydantic import ValidationError

    # Defined inline for performance reasons (httpx and pydantic imports)
    EXC_HANDLERS: dict[type[Exception], HandleFunc] = {
        # ZabbixAPICallError: handle_zabbix_api_call_error,  # NOTE: use different strategy for this?
        ZabbixAPIException: handle_zabbix_api_exception,  # NOTE: use different strategy for this?
        ZabbixCLIError: handle_notraceback,
        ValidationError: handle_validation_error,
        ConnectError: handle_connect_error,
        ConfigError: handle_notraceback,  # NOTE: can we remove this? subclass of ZabbixCLIError
    }
    """Mapping of exception types to exception handling strategies."""

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
