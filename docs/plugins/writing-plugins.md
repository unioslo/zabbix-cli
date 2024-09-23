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

The module can define a function called `__configure__` that will be called after the module is imported. This can be used to perform any necessary setup or configuration for the plugin. The function should take a single argument, the `PluginConfig` object that contains the configuration for the plugin.

```python
from zabbix_cli.app import app

def __configure__(config: PluginConfig) -> None:
    from zabbix_cli.logs import logger
    logger.info(f"Running post-import configuration for {config.module}")

    # We can access anything we need from the application state as long as the plugin module imports `zabbix_cli.app.app`

    # Set custom HTTP headers
    app.state.client.session.headers["X-Plugin-Header"] = "Some value"

    # Ensure that a certain configuration key is set
    app.state.config.api.legacy_json_format = False
```

The sky is the limit when it comes to what you can do in the `__configure__` function. However, be aware that modiyfing certain config options will not have any effect. This is especially true for the `api` section of the config file, as the API client is loaded and connected to the Zabbix API before the plugin modules are loaded.

## Configuration

The plugin must also be configured in the config file. Each plugin should be defined as a subsection of the `plugins` section in the config file.

```toml
[plugins.my_plugin]
module = "path.to.my_plugin"
# OR
# module = "/path/to/my_plugin.py"
```

The `module` key can be a module path or a a file path. If using a file path, it is highly recommended to use an absolute path.

We can also selectively disable plugins by setting the `enabled` key to `false`.

```toml
[plugins.my_plugin]
enabled = false
```

Or try to load the plugin if it exists, but do not fail if it does not.

```toml
[plugins.my_plugin]
optional = true
```

### Extra options

The plugin configuration can contain any number of extra options that can be used by the plugin module. These options can be accessed through the `PluginConfig` object that is passed to the `__configure__` function.

```toml
[plugins.my_plugin]
module = "path.to.my_plugin"
extra_option_str = "Some value"
extra_option_int = 42
```

These options are not type-checked, so it is up to the plugin module to handle them correctly.

```python
from zabbix_cli.app import app

def __configure__(config: PluginConfig) -> None:
    opt = config.get("extra_option_str")

    # Either convert to str or assert
    assert isinstance(opt, str)
    opt = str(opt)

    # Types from the TOML file are preserved
    opt = config.get("extra_option_int")
    assert isinstance(opt, int)

    # We can also pass a default value for unset options
    opt = config.get("extra_option_float", 3.14)
    assert isinstance(opt, float)

    # No default value returns None for unset options
    opt = config.get("non_existent_option")
    assert opt is None

    # Use our config options:
    app.state.client.session.headers["X-Plugin-Header"] = config.get("extra_option_str")
```
