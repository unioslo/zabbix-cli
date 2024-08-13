"""Defines the global state object for the application.

The global state object is a singleton that holds the current state of the
application. It is used to store the current configuration, Zabbix client,
and other stateful objects.
"""

# This module re-treads all the sins of Harbor CLI's state module.
#
# The lazy-loading, properties with setters/getters, and the singleton pattern
# are all code smells in their own ways (lazy-loading maybe less so in a CLI context).
# The sad thing is that this works well, and it's hard to find a good way to configure
# the application once, save that state, then maintain it for the duration
# of the application's lifetime. The only thing we have to be careful about it
# is to ensure we configure the State object before we use it, and perform
# all imports from other modules inside functions, so that we don't create
# circular imports.
#
# For some reason, I am totally blanking on how to do this in a way that doesn't
# suck when using Typer. With Click, it is easy, because we could just use the
# `@pass_obj` decorator to pass the State object to every command, but Typer
# doesn't have anything like that.
#
# We have a bunch of state we need to access in order to determine things like
# authentication, logging, default values, etc. So having them all gathered
# in this one place is convenient.
from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Optional

# This module should not import from other local modules because it's widely
# used throughout the application, and we don't want to create circular imports.
# Imports from other modules should be done inside functions, or in TYPE_CHECKING:
if TYPE_CHECKING:
    from prompt_toolkit.history import History
    from rich.console import Console

    from zabbix_cli.config.model import Config
    from zabbix_cli.pyzabbix.client import ZabbixAPI


class State:
    """Object that encapsulates the current state of the application.
    Holds the current configuration, Zabbix client, and other stateful objects.
    """

    _instance = None

    def __new__(cls, *args: Any, **kwargs: Any):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    repl: bool = False
    """REPL is active."""

    bulk: bool = False
    """Running in bulk mode."""

    _client: Optional[ZabbixAPI] = None
    """Zabbix API client object."""

    _config: Optional[Config] = None
    """Current Config object (may have overrides)."""

    _config_repl_original: Optional[Config] = None
    """Config object when the REPL was first launched."""

    _console: Optional[Console] = None
    """Stdout Rich console object."""

    _err_console: Optional[Console] = None
    """Stderr Rich console object."""

    token: Optional[str] = None
    """Active Zabbix API auth token."""

    _history: Optional[History] = None

    @property
    def client(self) -> ZabbixAPI:
        """Zabbix API client object.
        Fails if the client is not configured.
        """
        from zabbix_cli.exceptions import ZabbixCLIError

        if self._client is None:
            raise ZabbixCLIError("Not connected to the Zabbix API.")
        return self._client

    @client.setter
    def client(self, client: ZabbixAPI) -> None:
        self._client = client

    @property
    def is_client_loaded(self) -> bool:
        return self._client is not None

    @property
    def config(self) -> Config:
        from zabbix_cli.exceptions import ZabbixCLIError

        if self._config is None:
            raise ZabbixCLIError("Config not configured")
        return self._config

    @config.setter
    def config(self, config: Config) -> None:
        self._config = config

    @property
    def is_config_loaded(self) -> bool:
        return self._config is not None

    @property
    def console(self) -> Console:
        """Rich console object."""
        # fmt: off
        if not self._console:
            from .output.console import console
            self._console = console
        return self._console
        # fmt: on

    @property
    def err_console(self) -> Console:
        """Rich console object."""
        # fmt: off
        if not self._err_console:
            from .output.console import err_console
            self._err_console = err_console
        return self._err_console
        # fmt: on

    @property
    def history(self) -> History:
        """Prompt history.

        Lazily instantiates the history object if it doesn't exist.
        """
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.history import InMemoryHistory

        if not self._history:
            if self.config.app.history and self.config.app.history_file:
                try:
                    self._history = FileHistory(str(self.config.app.history_file))
                except Exception as e:
                    from zabbix_cli.output.console import error

                    error(f"Failed to instantiate CLI history: {e}")
                    self._history = InMemoryHistory()
            else:
                self._history = InMemoryHistory()
        return self._history

    def configure(self, config: Config) -> None:
        """Bootstrap the state object with the config and Zabbix API
        client objects. Also bootstraps ZabbixAPIBaseModel class vars.

        Should be called once at the beginning of the application's lifetime.

        Assigns the loaded config to the global state, as well as instantiating
        the Zabbix API client object. Uses the authentication info from the config
        to log into the Zabbix API.

        Finally, the API version is set on the ZabbixAPIBaseModel class, so that
        we know how to render the results for the given version of the API.
        """
        from zabbix_cli.pyzabbix.client import ZabbixAPI

        self.config = config

        # Create the Zabbix API client object and log in
        self.client = ZabbixAPI.from_config(config)
        self.login()

    def revert_config_overrides(self) -> None:
        """Revert config overrides from CLI args applied in REPL.

        Ensures that overrides only apply to a single command invocation,
        and are reset afterwards.

        In REPL mode, we have to ensure overrides don't persist between commands:

        ```
        > show_trigger_events 123 # renders table
        > -o json show_trigger_events 123 # renders json (override applied to config)
        > show_trigger_events 123 # renders table (override reverted)
        ```

        The override is reset after the command is executed.
        """
        if not self.repl or not self.is_config_loaded:
            return
        if not self._config_repl_original:
            self._config_repl_original = self.config.model_copy(deep=True)
        else:
            self.config = self._config_repl_original.model_copy(deep=True)

    def login(self) -> None:
        """Log in to the Zabbix API."""
        from zabbix_cli import auth
        from zabbix_cli.models import TableRenderable

        auth.login(self.client, self.config)
        TableRenderable.zabbix_version = self.client.version
        TableRenderable.legacy_json_format = self.config.app.legacy_json_format

    def logout(self) -> None:
        """Ends the current user's API session if the client is logged in
        and the application is not configured to use an auth token file.
        """
        from zabbix_cli.auth import clear_auth_token_file

        try:
            # Technically this API endpoint might return "false", which
            # would signify that that the logout somehow failed, but it's
            # not documented in the API docs.
            self.client.logout()
            # Token is now expired - delete it
            clear_auth_token_file(self.config)
        except Exception as e:
            from zabbix_cli.output.console import exit_err

            exit_err(f"Failed to log out of Zabbix API session: {e}")

    def logout_on_exit(self) -> None:
        """Ends the current user's API session if the client is logged in
        and the application is not configured to use an auth token file.
        """
        # If we are NOT keeping the API session alive between CLI invocations
        # we need to remember to log out once we are done in order to end the
        # session properly.
        # https://www.zabbix.com/documentation/current/en/manual/api/reference/user/login
        if (
            # State did not finish configuration before termination
            self._config is None
            or self._client is None
            # OR We want to keep the session alive
            or self.config.app.use_auth_token_file
        ):
            return
        self.logout()


def get_state() -> State:
    """Returns the global state object.

    Instantiates a new state object with defaults if it doesn't exist.
    """
    return State()
