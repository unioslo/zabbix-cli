"""This State module re-treads all the sins of Harbor CLI's state module.

The lazy-loading, properties with setters/getters, and the singleton pattern
are all code smells in their own ways. The sad thing is that this works well,
and it's hard to find a good way to configure the application once, save that state,
then maintain it for the duration of the application's lifetime. For some reason,
I am totally blanking on how to do this in a way that doesn't suck.

We have a bunch of state we need to access in order to determine things like
authentication, logging, default values, etc. So having them all gathered
in this one place is convenient.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from zabbix_cli.config import Config

from zabbix_cli.pyzabbix import ZabbixAPI

# This module generally shouldn't import from other local modules
# because it's widely used throughout the application, and we don't want
# to create circular import issues. It sucks, but it's the way it is.

if TYPE_CHECKING:
    pass


class State:
    """Object that encapsulates the current state of the application.
    Holds the current configuration, harbor client, and other stateful objects.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    repl: bool = False
    """Whether or application is inside REPL mode."""

    _client = None  # type: ZabbixAPI | None
    """Current Zabbix API client object."""

    _config = None  # type: Config | None
    """Current configuration object."""

    _console = None  # type: Console | None
    """Lazy-loaded Rich console object."""

    token = None  # type: str | None
    """The current active Zabbix API auth token."""

    @property
    def client(self) -> ZabbixAPI:
        """Harbor async client object.

        Returns a client with bogus defaults if the client is not configured.
        """
        if self._client is None:
            raise RuntimeError("Client not configured")
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
            raise RuntimeError("Config not configured")
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

    def configure(self, config: Config) -> None:
        """Sets the config and client objects.
        Logs into the Zabbix API with the configured credentials.
        """
        self.config = config
        if not self.config.app.auth_token and not self.config.app.password:
            raise RuntimeError(
                "FATAL ERROR: No authentication credentials configured when loading config"
            )
        self.client = ZabbixAPI(self.config.api.url)
        self.client.session.verify = self.config.api.verify_ssl
        # TODO: handle expired auth tokens by prompting for username/password

        # alias for brevity
        ca = config.app
        config_token = ca.auth_token.get_secret_value() if ca.auth_token else None

        self.token = self.client.login(
            user=ca.username,
            password=ca.password.get_secret_value() if ca.password else None,
            auth_token=config_token,
        )

        # Write the token file if it's new and we are configured to save it
        if (
            config.app.use_auth_token_file
            and ca.username  # we need a username in the token file
            and self.token  # must be not None and not empty
            and self.token != config_token  # must be a new token
        ):
            from zabbix_cli.auth import write_auth_token_file  # circular import

            # TODO: only write if we updated the token
            write_auth_token_file(ca.username, self.token)

    def logout(self):
        """Ends the current user's API session if auth token file is not used."""
        # If we are NOT keeping the API session alive between CLI invocations
        # we need to remember to log out once we are done in order to end the
        # session properly.
        # https://www.zabbix.com/documentation/current/en/manual/api/reference/user/login
        if self._config is None or self._client is None:
            return  # we have not been configured yet

        if not self.config.app.use_auth_token_file:
            try:
                self.client.user.logout()
                # Technically this API endpoint might return "false", which
                # would signify that that the logout somehow failed, but it's
                # not documented in the API docs.
            except Exception as e:
                from zabbix_cli.output.console import error

                error(f"Failed to log out of Zabbix API session: {e}")


def get_state() -> State:
    """Returns the global state object.

    Instantiates a new state object with defaults if it doesn't exist."""
    return State()


def get_client() -> ZabbixAPI:
    """Returns the global Harbor client object.

    Instantiates a new client object with defaults if it doesn't exist."""
    return get_state().client
