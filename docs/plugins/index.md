# Plugins

!!! note
    The plugin system is still under development and may change in future releases.

The functionality of the application can be extended using user-defined plugins. Plugins can be used to add new commands, modify existing commands, or add new functionality to the application.

## Plugin types

There are two types of plugins:

1. [Local plugins](#local-plugins)
2. [External plugins](#external-plugins)

### Local plugins

Local plugins are local Python modules (files), whose paths are defined in the application's configuration file. They are the easiest way to add new functionality to the application, but are harder to distribute and share in a consistent way.

See the [local plugins](./local-plugins.md) page for more information.

### External plugins

External plugins are Python packages that can be installed with Pip and are automatically discovered by the application. They are easier to distribute and share, but require more setup and configuration by the plugin author.

See the [external plugins](./external-plugins.md) page for more information.
