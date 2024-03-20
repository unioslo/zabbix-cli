from typing import Iterator
import pytest
import typer
from typer.testing import CliRunner
from typer import Typer


from zabbix_cli.main import app

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
