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

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import Optional

# This module should not import from other local modules because it's widely
# used throughout the application, and we don't want to create circular imports.
# Runtime imports from other modules should be done inside functions,
# while annotations imports should done in `if TYPE_CHECKING:` blocks.
if TYPE_CHECKING:
    from prompt_toolkit.history import History
    from rich.console import Console

    from zabbix_cli.config.model import Config
    from zabbix_cli.pyzabbix.client import ZabbixAPI

logger = logging.getLogger(__name__)


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

    _config_loaded: bool = False
    """Config has been loaded from file."""

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
        if self._config is None:
            from zabbix_cli.config.model import Config
            from zabbix_cli.logs import configure_logging

            # HACK: configure logging with sample config
            # in order to log the debug message to the default log file
            config = Config.sample_config()
            configure_logging(config.logging)
            logger.debug(
                "Using sample config file as fallback.",
                stacklevel=2,  # See who called this
            )
            return config
        return self._config

    @config.setter
    def config(self, config: Config) -> None:
        """Set the configuration object and update active configuration of
        loggers, consoles, etc."""
        from zabbix_cli.logs import configure_logging
        from zabbix_cli.output.console import configure_console

        self._config = config
        configure_logging(config.logging)
        configure_console(config)
        # HACK: don't consider using sample config as "loaded".
        # Signals that main callback should create a new config file.
        self._config_loaded = config.sample is False

    @property
    def is_config_loaded(self) -> bool:
        return self._config_loaded

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

    @property
    def ready(self) -> bool:
        """State is configured and ready to use."""
        return self.is_client_loaded and self.is_config_loaded

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
        """Log in to the Zabbix API.

        Uses the authentication info from the config to log into the Zabbix API.

        Also sets the JSON rendering mode on the TableRenderable base class
        used to render application output."""
        from zabbix_cli import auth
        from zabbix_cli.models import TableRenderable

        self.client = auth.login(self.config)
        TableRenderable.legacy_json_format = self.config.app.legacy_json_format

    def logout(self) -> None:
        """Log out and clear auth token file if configured."""
        from zabbix_cli import auth

        auth.logout(self.client, self.config)

    def logout_on_exit(self) -> None:
        """Log out on exit if not keeping the session alive via auth token file."""
        # If we are NOT keeping the API session alive between CLI invocations
        # we need to remember to log out once we are done in order to end the
        # session properly.
        # https://www.zabbix.com/documentation/current/en/manual/api/reference/user/login
        if (
            # State did not finish configuration before termination
            not self.ready
            # OR We want to keep the session alive
            or self.config.app.use_session_file
            # OR we are using an API token
            or self.client.use_api_token
        ):
            return
        try:
            self.logout()
        except Exception as e:
            from zabbix_cli.exceptions import handle_exception

            # Outside of main loop, handle the exception
            handle_exception(e)


def get_state() -> State:
    """Returns the global state object.

    Instantiates a new state object with defaults if it doesn't exist.
    """
    return State()
