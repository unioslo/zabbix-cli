from __future__ import annotations

from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner
from zabbix_cli.commands import template
from zabbix_cli.pyzabbix.types import Host
from zabbix_cli.pyzabbix.types import Template
from zabbix_cli.state import State

HOST = Host(hostid="456", host="foo.example.com")
TEMPLATE = Template(templateid="123", host="Apache by HTTP", hosts=[HOST])


def invoke_unlink(
    state: State, monkeypatch: pytest.MonkeyPatch, flags: list[str]
) -> Mock:
    """Invoke `unlink_template_from_host` and return the mocked API request.

    Only the transport is mocked, so the test covers the path from the
    command through `ZabbixAPI.unlink_templates_from_hosts` to the API call.
    """
    do_request = Mock()
    monkeypatch.setattr(state.client, "do_request", do_request)
    monkeypatch.setattr(template, "parse_templates_arg", lambda *a, **kw: [TEMPLATE])
    monkeypatch.setattr(template, "parse_hosts_arg", lambda *a, **kw: [HOST])

    cli = typer.Typer()
    _ = cli.command()(template.unlink_template_from_host)
    result = CliRunner().invoke(cli, [*flags, "123", "456"])
    assert result.exit_code == 0, result.output
    return do_request


@pytest.mark.parametrize(
    "flags, expected",
    [
        pytest.param([], {"templateids_clear": ["123"]}, id="default"),
        pytest.param(["--clear"], {"templateids_clear": ["123"]}, id="clear"),
        pytest.param(["--no-clear"], {"templateids": ["123"]}, id="no-clear"),
    ],
)
def test_unlink_template_from_host_clear(
    state: State,
    monkeypatch: pytest.MonkeyPatch,
    flags: list[str],
    expected: dict[str, list[str]],
) -> None:
    do_request = invoke_unlink(state, monkeypatch, flags)
    do_request.assert_called_once_with(
        "host.massremove", {"hostids": ["456"], **expected}
    )


@pytest.mark.parametrize(
    "flags",
    [
        pytest.param(["--dryrun"], id="default"),
        pytest.param(["--dryrun", "--clear"], id="clear"),
        pytest.param(["--dryrun", "--no-clear"], id="no-clear"),
    ],
)
def test_unlink_template_from_host_dryrun(
    state: State, monkeypatch: pytest.MonkeyPatch, flags: list[str]
) -> None:
    invoke_unlink(state, monkeypatch, flags).assert_not_called()
