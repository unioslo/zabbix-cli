from __future__ import annotations

from zabbix_cli.output.style import Color


def test_color_call() -> None:
    assert Color.INFO("test") == "[default]test[/]"
    assert Color.SUCCESS("test") == "[green]test[/]"
    assert Color.WARNING("test") == "[yellow]test[/]"
    assert Color.ERROR("test") == "[red]test[/]"

    # Ensure it doesnt break normal instantiation with a value
    assert Color("default") == Color.INFO
    assert Color("yellow") == Color.WARNING
