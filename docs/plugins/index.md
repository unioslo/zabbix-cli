# Plugins

!!! note
    The plugin system is still under development and may change in future releases.

The functionality of the application can be extended using user-defined plugins. Plugins can be used to add new commands, modify existing commands, or add new functionality to the application. Plugins can installed as local Python modules or external Python packages.

## Local plugins

Local plugins are local Python modules (files) that are loaded by the application. They are the easiest way to add new functionality to the application, but are harder to distribute and share in a consistent way. They are not automatically discovered by the application, and must be manually configured in the configuration file.

See the [local plugins](./local-plugins.md) page for more information.

## External plugins

External plugins are Python packages that can be installed with Pip and are automatically discovered by the application. They are easier to distribute and share, but require more effort on the part of the plugin author to create and maintain.

See the [external plugins](./external-plugins.md) page for more information.
