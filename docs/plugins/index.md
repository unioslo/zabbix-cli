# Plugins

!!! warning "Work in progress"
    The plugin system is still under development and may change in future releases.

The functionality of the application can be extended using user-defined plugins. Plugins can be used to add new commands, modify existing commands, or add new functionality to the application. Plugins can installed as local Python modules or external Python packages.

## Local plugins

Local plugins are local Python modules (files) that are loaded by the application. They are the easiest way to add new functionality to the application, but are harder to distribute and share in a consistent manner. They are not automatically discovered by the application, and must be manually configured in the configuration file.

See the [local plugins](./local-plugins.md) page for more information.

## External plugins

External plugins are Python packages that can be installed with Pip and are automatically discovered by the application. They are easier to distribute and share, but require more effort on the part of the plugin author to create and maintain.

See the [external plugins](./external-plugins.md) page for more information.

## Choosing the correct plugin type

Both local and external plugins are essentially written in the same manner, following the application’s guidelines for plugin development outlined in [Writing plugins](./guide.md). This common foundation ensures that the core functionality is consistent whether the plugin is distributed as a local module or an external package.

The difference lies primarily in how they are packaged for distribution and how the application loads them. While local plugins require manual configuration to be recognized by the application, external plugins are designed to be discovered automatically once installed.

An easy way to decide which type of plugin to use is to consider whether you intend to share your plugin or not. If you do, an external plugin is likely the way to go. If you are developing a plugin for personal use or for a specific environment, a local plugin may be more appropriate.
