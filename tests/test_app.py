from __future__ import annotations

import pytest
from zabbix_cli.app.app import StatefulApp
from zabbix_cli.config.model import PluginConfig
from zabbix_cli.exceptions import PluginError
from zabbix_cli.state import State


def test_get_plugin_config(app: StatefulApp, state: State) -> None:
    """Test that we can get a plugin's configuration."""
    # Add a plugin configuration
    state.config.plugins.root = {
        # From module specification
        "my_commands": PluginConfig(
            module="path.to.my_commands",
        ),
        # From path
        "my_commands2": PluginConfig(
            module="path/to/my_commands2.py",
        ),
        # From package with entrypoint
        "my_commands3": PluginConfig(),
    }

    # With name
    config = app.get_plugin_config("my_commands")
    assert config.module == "path.to.my_commands"

    # Missing
    with pytest.raises(PluginError):
        config = app.get_plugin_config("missing")
