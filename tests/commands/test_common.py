from __future__ import annotations

import click
import pytest
import typer
from inline_snapshot import snapshot
from zabbix_cli.app.app import StatefulApp
from zabbix_cli.commands.common.args import CommandParam


def test_command_param(ctx: typer.Context) -> None:
    param = CommandParam()
    assert param.name == "command"

    # No ctx
    with pytest.raises(click.exceptions.BadParameter) as exc_info:
        param.convert("some-non-existent-command", None, None)
    assert exc_info.exconly() == snapshot("click.exceptions.BadParameter: No context.")

    # No value (empty string)
    with pytest.raises(click.exceptions.BadParameter) as exc_info:
        param.convert("", None, ctx)
    assert exc_info.exconly() == snapshot(
        "click.exceptions.BadParameter: Missing command."
    )

    # No value (None)
    with pytest.raises(click.exceptions.BadParameter) as exc_info:
        param.convert(None, None, ctx)  # type: ignore
    assert exc_info.exconly() == snapshot(
        "click.exceptions.BadParameter: Missing command."
    )

    # Command not found
    with pytest.raises(click.exceptions.BadParameter) as exc_info:
        param.convert("some-non-existent-command", None, None)
    assert exc_info.exconly() == snapshot("click.exceptions.BadParameter: No context.")


def test_command_param_in_command(
    app: StatefulApp, capsys: pytest.CaptureFixture[str]
) -> None:
    @app.command(name="help-command")
    def help_command(  # type: ignore
        ctx: typer.Context,
        cmd_arg: click.Command = typer.Argument(
            ..., help="The command to get help for."
        ),
    ) -> str:
        return cmd_arg.get_help(ctx)

    @app.command(name="other-command", help="Help for the other command.")
    def other_command(ctx: typer.Context) -> None:  # type: ignore
        pass

    cmd = typer.main.get_command(app)

    with cmd.make_context(None, ["help-command", "other-command"]) as new_ctx:
        new_ctx.info_name = "other-command"
        cmd.invoke(new_ctx)
        captured = capsys.readouterr()
        assert captured.err == snapshot("")
        # We cannot test the output with snapshot testing, because
        # the trim-trailing-whitespace pre-commit hook modifies the
        # snapshot output. Not ideal, so we have to test the relevant lines instead.
        #
        # Also, terminal styling is broken when testing outside of a terminal.
        # Thus, this minimal test.
        assert "other-command help-command [OPTIONS]" in captured.out
