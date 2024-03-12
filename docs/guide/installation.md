# Installation

The application is primarily distributed with `pip`, but other installation methods are available.

## Installing Zabbix CLI

{% include-markdown ".includes/quick-install.md" %}


### Multiple versions with pipx

pipx supports installing multiple versions of the same package by giving each installation a custom suffix. For example, if we wish to install Zabbix CLI version 3 alongside an existing previous version, we can do so:

```bash
pipx install zabbix-cli>=3.0.0 --suffix @v3
```

This installs Zabbix CLI >= 3.0.0 with the suffix `@v3`, and we can run it with:

```bash
zabbix-cli@v3
```

and the existing version can be run with:

```bash
zabbix-cli
```

## Creating a configuration file

The application requires a configuration file. Normally, this file is created on first time startup, but it can also be created with the command `zabbix-cli-init`.

```
zabbix-cli-init
```

The application will print the location of the created config file:

```
! Configuration file created: /Users/pederhan/Library/Application Support/zabbix-cli/zabbix-cli.toml
```

To specify a URL and username, use the options `--url` and `--user`:

```
zabbix-cli-init --url https://zabbix.example.com --user Admin
```

### Create a sample config

If you for whatever reason want to preview the sample config, or create it in a different location than the default, you can use the `sample_config` command to print a sample config to stdout, which can be redirected to a file.

```
zabbix-cli sample_config > /path/to/config.toml
```

A more convoluted way of creating a default config file in the default location would be:

```
zabbix-cli sample_config > "$(zabbix-cli open --path config)/zabbix-cli.toml"
```

## Upgrading Zabbix CLI

The upgrade process depends on the chosen installation method.

{% include ".includes/upgrade.md" %}
