# Zabbix-cli

## About

Zabbix-cli is a command line interface for performing common administrative tasks tasks in [Zabbix monitoring system](https://www.zabbix.com/) via the [Zabbix API](https://www.zabbix.com/documentation/current/en/manual/api).

The zabbix-cli code is written in [Python](https://www.python.org/) and distributed under the GNU General Public License v3. It has been developed and tested by [University Center for Information Technology](https://www.usit.uio.no/) at [the University of Oslo, Norway](https://www.uio.no/).

The project home page is on [GitHub](https://github.com/unioslo/zabbix-cli). Please report any issues or improvements there.

The manual is available on-line at https://unioslo.github.io/zabbix-cli/manual.html.

## Install

There are versioned deb and rpm releases available on the [GitHub releases page](https://github.com/unioslo/zabbix-cli/releases).

You could also install directly from GitHub with pip:

```
pip install git+https://github.com/unioslo/zabbix-cli.git@master
```

## Getting started

### Configuration

Zabbix-cli need a config file. This can be created with the `zabbix-cli-init` command.

```
zabbix-cli-init --zabbix-url https://zabbix.example.com/
```

Zabbix-cli will look for config files in the following order. Any later files will override the former:

1. /usr/share/zabbix-cli/zabbix-cli.conf
2. /etc/zabbix-cli/zabbix-cli.conf
3. ~/.zabbix-cli/zabbix-cli.conf
4. File specified with `-c`/`--config` parameter
5. /etc/zabbix-cli/zabbix-cli.fixed.conf
6. /usr/share/zabbix-cli/zabbix-cli.fixed.conf

By running the config module you will get the current config or the default config:

```
python -m zabbix_cli.config show
python -m zabbix_cli.config defaults
```

If you run into problems it is useful to enable logging and set the `DEBUG` level for logging:

```
[logging]
logging = ON
log_level = DEBUG
log_file = /path/to/log/zabbix-cli.log
```

### Authentication

By default you will be asked for a username and password when running zabbix-cli.

Alternatively you could store your username and password in the file `~/.zabbix-cli_auth`. The content of this file will need to be on the `USERNAME::PASSWORD` format.

A third alternative is using the environment variables, `ZABBIX_USERNAME` and `ZABBIX_PASSWORD`.

You need to secure this authentication file and need to be aware that other processes on the same computer will be able to view your environment variables. Use these features at your own risk.

Zabbix-cli will store a session token if you configure `use_auth_token_file = ON`. This way you don't need to provide your credentials each time you run zabbix-cli. This token file should also be secured properly.

### Running zabbix-cli

You may run zabbix-cli as a shell/REPL by simply running `zabbix-cli`.

A single command could be run by using the `-C`/`--command` parameter like `zabbix-cli -C "show_host host.example.com"`.

Alternatively you could run multiple commands if you provide a file, with the `-f` parameter, with one command per line in the file.

Get more help and information by running `zabbix-cli --help` and `zabbix-cli -C "help"`.
