from __future__ import annotations

from collections.abc import Generator
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer
from packaging.version import Version
from pytest_httpserver import HTTPServer
from typer.testing import CliRunner
from zabbix_cli.app import StatefulApp
from zabbix_cli.config.model import Config
from zabbix_cli.main import app
from zabbix_cli.pyzabbix.client import ZabbixAPI
from zabbix_cli.state import State
from zabbix_cli.state import get_state

runner = CliRunner()


@pytest.fixture(name="app")
def _app() -> Iterator[StatefulApp]:
    yield app


@pytest.fixture
def ctx(app: StatefulApp) -> typer.Context:
    """Create context for the main command."""
    # Use the CliRunner to invoke a command and capture the context
    obj = {}
    with runner.isolated_filesystem():

        @app.callback(invoke_without_command=True)
        def callback(ctx: typer.Context):
            obj["ctx"] = ctx  # Capture the context in a non-local object

        runner.invoke(app, [], obj=obj)
    return obj["ctx"]


DATA_DIR = Path(__file__).parent / "data"

# Read sample configs once per test run to avoid too much I/O
TOML_CONFIG = DATA_DIR / "zabbix-cli.toml"
TOML_CONFIG_STR = TOML_CONFIG.read_text()

CONF_CONFIG = DATA_DIR / "zabbix-cli.conf"
CONF_CONFIG_STR = CONF_CONFIG.read_text()


@pytest.fixture()
def data_dir() -> Iterator[Path]:
    yield Path(__file__).parent / "data"


@pytest.fixture()
def config_path(tmp_path: Path) -> Iterator[Path]:
    config_copy = tmp_path / "zabbix-cli.toml"
    config_copy.write_text(TOML_CONFIG_STR)
    yield config_copy


@pytest.fixture()
def legacy_config_path(tmp_path: Path) -> Iterator[Path]:
    config_copy = tmp_path / "zabbix-cli.conf"
    config_copy.write_text(CONF_CONFIG_STR)
    yield config_copy


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


@pytest.fixture(name="zabbix_client_mock_version")
def zabbix_client_mock_version(
    zabbix_client: ZabbixAPI, monkeypatch: pytest.MonkeyPatch
) -> Iterator[ZabbixAPI]:
    monkeypatch.setattr(zabbix_client, "api_version", lambda: Version("7.0.0"))
    yield zabbix_client


def add_httpserver_version_endpoint(
    httpserver: HTTPServer, version: Version, id: int = 0
) -> None:
    """Add an endpoint emulating the Zabbix apiiinfo.version method."""
    httpserver.expect_oneshot_request(
        "/api_jsonrpc.php",
        json={"jsonrpc": "2.0", "method": "apiinfo.version", "params": {}, "id": id},
        method="POST",
        headers={"Content-Type": "application/json-rpc"},
    ).respond_with_json({"jsonrpc": "2.0", "result": str(version), "id": id})


@pytest.fixture(name="force_color")
def force_color() -> Generator[Any, Any, Any]:
    import os

    os.environ["FORCE_COLOR"] = "1"
    yield
    os.environ.pop("FORCE_COLOR", None)


@pytest.fixture(name="no_color")
def no_color() -> Generator[Any, Any, Any]:
    """Disable color in a test. Takes precedence over force_color."""
    import os

    os.environ.pop("FORCE_COLOR", None)
    os.environ["NO_COLOR"] = "1"
    yield
    os.environ.pop("NO_COLOR", None)
