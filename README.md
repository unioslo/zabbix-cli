# Zabbix-cli

## About

Zabbix-cli is a command line interface for performing common administrative tasks tasks in [Zabbix monitoring system](https://www.zabbix.com/) via the [Zabbix API](https://www.zabbix.com/documentation/current/en/manual/api).

The zabbix-cli code is written in [Python](https://www.python.org/) and distributed under the GNU General Public License v3. It has been developed and tested by [University Center for Information Technology](https://www.usit.uio.no/) at [the University of Oslo, Norway](https://www.uio.no/).

The project home page is on [GitHub](https://github.com/unioslo/zabbix-cli). Please report any issues or improvements there.

The manual is available on-line at <https://unioslo.github.io/zabbix-cli/manual.html>.

## Install

Install with pip:

```bash
pip install git+https://github.com/unioslo/zabbix-cli.git@master
```

## Getting started

### Configuration

Zabbix-cli needs a config file. This can be created with the `zabbix-cli init` command.

```bash
zabbix-cli init --zabbix-url https://zabbix.example.com/
```

Zabbix-cli will look for config files in the following order:

1. The path specified with the `--config` parameter
2. `./zabbix-cli.toml`
3. XDG config directory (usually `~/.config/zabbix-cli/zabbix-cli.toml`), or equivalent Platformdirs directory on [Windows](https://platformdirs.readthedocs.io/en/latest/api.html#windows) and [macOS](https://platformdirs.readthedocs.io/en/latest/api.html#macos)
4. XDG site config directory (usually `/etc/xdg/zabbix-cli/zabbix-cli.toml`), or equivalent Platformdirs directory on [Windows](https://platformdirs.readthedocs.io/en/latest/api.html#windows) and [macOS](https://platformdirs.readthedocs.io/en/latest/api.html#macos)

To show the directories used by the application run:

```
zabbix-cli show_dirs
```

To open the default config directory with the default window manager run:

```bash
zabbix-cli open config
```

Or print the path to the default config directory:

```bash
zabbix-cli open config --path
```

Zabbix-cli provides commands for showing the current and default configuration:

```bash
zabbix-cli show_config
zabbix-cli sample_config
```

If you run into problems it is useful to enable logging and set the `DEBUG` level for logging:

```toml
[logging]
logging = ON
log_level = DEBUG
log_file = /path/to/log/zabbix-cli.log
```

### Authentication

Zabbix-cli provides several ways to authenticate. They are tried in the following order if multiple are set:

1. API token in config file
2. API token in file (if `use_auth_token_file=true`)
3. Username and password in config file
4. Username and password in auth file
5. Username and password in environment variables
6. Username and password from prompt

#### Username and Password

Username and password-based authentication is the default and easiest way to authenticate, but also the least secure.

##### Config file

The password can be set directly in the config file:

```toml
[api]
zabbix_url = "https://zabbix.example.com/"
username = "Admin"
password = "zabbix"
```

##### Prompt

By omitting the `password` parameter in the config file, you will be prompted for a password when running zabbix-cli:

```toml
[api]
zabbix_url = "https://zabbix.example.com/"
username = "Admin"
```

##### Auth file

An auth file named `.zabbix-cli_auth` can be created in the user's home directory. The content of this file should be in the `USERNAME::PASSWORD` format.

```bash
echo "Admin::zabbix" > ~/.zabbix-cli_auth
```

The file is automatically loaded if it exists and the `password` parameter is not set in the config file. The location of the file can be changed in the config file:

```toml
[app]
auth_file = "/path/to/auth/file"
```

##### Environment variables

The username and password can be set as environment variables:

```bash
export ZABBIX_USERNAME="Admin"
export ZABBIX_PASSWORD="zabbix"
```

These are automatically loaded if the `password` parameter is not set in the config file.

#### Auth token

Once you have authenticated with a username and password, zabbix-cli will store a session token if you configure `use_auth_token_file=true` in the config. This way you don't need to provide your credentials each time you run zabbix-cli. The token file should also be secured properly.

```toml
[app]
use_auth_token_file = true
```

The location of the config file can be changed in the config file:

```toml
[app]
auth_token_file = "/path/to/auth/token/file"
```

#### API token

Zabbix-cli also supports authentication with an API token. This is the most secure way to authenticate. The API token must be set directly in the config file:

```toml
[api]
auth_token = "API_TOKEN"

[app]
use_auth_token_file = false
```

### Running zabbix-cli

You may run zabbix-cli as a shell/REPL by simply running `zabbix-cli`.

A single command could be run by callign `zabbix-cli` with the command as an argument:

```bash
zabbix-cli show_hosts
```

Alternatively you could run multiple commands if you provide a file, with the `-f` parameter, with one command per line in the file.

Get more help and information by running `zabbix-cli --help` and `zabbix-cli -C "help"`.

## Development

Zabbix-cli currently uses [Hatch](https://hatch.pypa.io/latest/) for project management and packaging. To start off, clone the repository:

```bash
git clone https://github.com/unioslo/zabbix-cli.git
```

Then make a virtual environment using Hatch:

```bash
hatch shell
```

This will create a new virtual environment, install the required dependencies and enter the environment.

### Testing

Run unit tests (without coverage):

```bash
hatch run test
```

Generate coverage report:

```bash
hatch run cov
```

### Documentation

To serve the documentation locally:

```bash
hatch run docs:serve
```

This will start a local web server on `http://localhost:8001` that is automatically refreshed when you make changes to the documentation. However, some hooks are only run on startup, such as the creation of pages for each command. Changes to command examples or docstrings will require a restart.
