from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
import typer
from typer import Typer
from typer.testing import CliRunner
from zabbix_cli.config.model import Config
from zabbix_cli.main import app
from zabbix_cli.pyzabbix.client import ZabbixAPI
from zabbix_cli.state import State
from zabbix_cli.state import get_state

runner = CliRunner()


@pytest.fixture(name="app")
def _app() -> Iterator[Typer]:
    yield app


def app_runner():
    return runner.invoke(app, ["--help"])


@pytest.fixture
def ctx(app: Typer) -> typer.Context:
    """Create context for the main command."""
    # Use the CliRunner to invoke a command and capture the context
    obj = {}
    with runner.isolated_filesystem():

        @app.callback(invoke_without_command=True)
        def callback(ctx: typer.Context):
            obj["ctx"] = ctx  # Capture the context in a non-local object

        runner.invoke(app, [], obj=obj)
    return obj["ctx"]


@pytest.fixture()
def data_dir() -> Iterator[Path]:
    yield Path(__file__).parent / "data"


@pytest.fixture(name="state")
def state(config: Config, zabbix_client: ZabbixAPI) -> Iterator[State]:
    """Return a fresh State object with a config and client.

    The client is not logged in to the Zabbix API.

    Modifies the State singleton to ensure a fresh state is returned
    each time.
    """
    State._instance = None  # pyright: ignore[reportPrivateUsage]
    state = get_state()
    state.config = config
    state.client = zabbix_client
    yield state
    # reset after test
    State._instance = None  # pyright: ignore[reportPrivateUsage]


@pytest.fixture(name="config")
def config(tmp_path: Path) -> Iterator[Config]:
    """Return a sample config."""
    conf = Config.sample_config()
    # Set up logging for the test environment
    log_file = tmp_path / "zabbix-cli.log"
    conf.logging.log_file = log_file
    conf.logging.log_level = "DEBUG"  # we want to see all logs
    yield conf


@pytest.fixture(name="zabbix_client")
def zabbix_client() -> Iterator[ZabbixAPI]:
    config = Config.sample_config()
    client = ZabbixAPI.from_config(config)
    yield client
