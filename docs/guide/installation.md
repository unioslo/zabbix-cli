# Installation

The application is primarily distributed with `pip`, but other installation methods are available.

## Installing Zabbix CLI

{% set install_expand = true %}
{% include-markdown ".includes/quick-install.md" %}


## Creating a configuration file

The application requires a configuration file. It can be created with the command `zabbix-cli-init`.

```
zabbix-cli-init
```

The application will print the location of the created config file:

```
! Configuration file created: /Users/pederhan/Library/Application Support/zabbix-cli/zabbix-cli.toml
```

To bootstrap the config with a URL and username, use the options `--url` and `--user`:

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
