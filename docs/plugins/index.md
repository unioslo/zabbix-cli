# Plugins

!!! note
    The plugin system is still under development and may change in future releases.

The functionality of the application can be extended using user-defined plugins. Plugins can be used to add new commands, modify existing commands, or add new functionality to the application.

As of now, the application only supports plugins defined via local Python modules. Support for [pip-installable plugins](https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/) is planned for a future release.

!!! warning
    Addings commands via plugins is only supported in REPL mode. Due to limitations with how Typer works, adding commands after instantiating the application is not possible without adding a lot of complexity and brittleness.
    See [#217](https://github.com/unioslo/zabbix-cli/issues/217) for more information.
