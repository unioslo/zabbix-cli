# Writing plugins

A plugin is simply a Python module that is loaded by the application. You can define whatever functionality you want in a plugin, while having access to the same functionality and application state as the built-in commands.

A plugin consists of two parts:

1. [Python module](#python-module)
2. [Config file entry](#configuration)

## Python module

A plugin module can contain anything, but typically we want to import `zabbix_cli.app.app` to access the application state, define new commands, modify existing commands, etc.

```python
from __future__ import annotations

from typing import Optional

import typer
from zabbix_cli.app import app
from zabbix_cli.render import render_result


# Header for the rich help panel shown in the --help output
CATEGORY = "My custom commands"

# Define a new command
@app.command(name="my_command", rich_help_panel=CATEGORY)
def my_command(
    ctx: typer.Context,
    arg1: str = typer.Argument(help="Some argument"),
    opt1: Optional[str] = typer.Option(None, help="Some option"),
) -> None:
    """Short description of the command."""
    # We can use the Zabbix API client
    host = app.state.client.get_host(arg1)

    # We can use the same rendering machinery as the built-in commands
    render_result(host)
```

### Post-import configuration

The module can define a function called `__post_import__` that will be called after the module is imported. This can be used to perform any necessary setup or configuration for the plugin. The function should take a single argument, the `PluginConfig` object that contains the configuration for the plugin.

```python
from zabbix_cli.app import app

def __post_import__(config: PluginConfig) -> None:
    from zabbix_cli.logs import logger
    logger.info(f"Running post-import configuration for {config.module}")

    # We can access anything we need from the application state as long as the plugin module imports `zabbix_cli.app.app`

    # Set custom HTTP headers
    app.state.client.session.headers["X-Plugin-Header"] = "Some value"

    # Ensure that a certain configuration key is set
    app.state.config.api.legacy_json_format = False
```

The sky is the limit when it comes to what you can do in the `__post_import__` function. However, be aware that modiyfing certain config options will not have any effect. This is especially true for the `api` section of the config file, as the API client is loaded and connected to the Zabbix API before the plugin modules are loaded.

## Configuration

The plugin must also be configured in the config file. Each plugin should be defined as a subsection of the `plugins` section in the config file.

```toml
[plugins.my_plugin]
module = "path.to.my_plugin"
# OR
# module = "/path/to/my_plugin.py"
```

The `module` key can be a module path or a a file path. If using a file path, it is highly recommended to use an absolute path.
