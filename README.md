# Zabbix-cli

<!-- Activate badges when we publish to PyPI -->
<!-- [![PyPI](https://img.shields.io/pypi/v/zabbix-cli)](https://pypi.org/project/zabbix-cli/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/zabbix-cli)](https://pypi.org/project/zabbix-cli/)
![PyPI - License](https://img.shields.io/pypi/l/zabbix-cli)(https://pypi.org/project/zabbix-cli/) -->
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/unioslo/zabbix-cli/test.yml?branch=master&label=tests)

**Zabbix-CLI v3 has been completely rewritten from the ground up. The old version can be found [here](https://github.com/unioslo/zabbix-cli/tree/2.3.2).**

## About

Zabbix-cli is a command line interface for performing common administrative tasks tasks in [Zabbix monitoring system](https://www.zabbix.com/) via the [Zabbix API](https://www.zabbix.com/documentation/current/en/manual/api).

The zabbix-cli code is written in [Python](https://www.python.org/) and distributed under the GNU General Public License v3. It has been developed and tested by [University Center for Information Technology](https://www.usit.uio.no/) at [the University of Oslo, Norway](https://www.uio.no/).

The project home page is on [GitHub](https://github.com/unioslo/zabbix-cli). Please report any issues or improvements there.

The manual is available online at <https://unioslo.github.io/zabbix-cli/>.

## Install

If you have [uv](https://github.com/astral-sh/uv) installed:

```bash
uv tool install git+https://github.com/unioslo/zabbix-cli.git@master

# Or if you just want to try out the CLI without installing it
uvx --from git+https://github.com/unioslo/zabbix-cli.git@master zabbix-cli
```

Alternatively, you can install the package with pip(x):

```bash
pipx install git+https://github.com/unioslo/zabbix-cli.git@master
```

We are in the process of acquiring the name `zabbix-cli` on PyPI. Until then, installation from the GitHub repository is the only option when installing as a Python package.

### Homebrew

A homebrew package exists, but it is not maintained by us. It can be installed with:

```bash
brew install zabbix-cli
```

### PyInstaller binaries

Binaries built with PyInstaller can be found on the [releases page](https://github.com/unioslo/zabbix-cli/releases). We build binaries for Linux, macOS and Windows for each release.

## Getting started

### Quick start

```bash
# Initialize the config file with your Zabbix URL
zabbix-cli init --zabbix-url https://your-zabbix-url.com/
# Start the REPL
zabbix-cli
```

### Usage

Zabbix-cli is a command line interface for Zabbix. It can be used in three ways:

1. **Interactive mode**: Start the REPL by running `zabbix-cli`. This will start a shell where you can run multiple commands in a persistent session.
2. **Single command**: Run a single command by running `zabbix-cli COMMAND`. This will run the command and print the output.
3. **Batch mode**: Run multiple commands from a file by running `zabbix-cli -f FILE`. The file should contain one command per line.

Command reference can be found in the [online user guide](https://unioslo.github.io/zabbix-cli/guide/introduction/) or by running `zabbix-cli --help`.

#### Formats

Zabbix-cli supports two output formats: table and JSON. The default format is table, but it can be changed with the `--format` parameter:

```bash
# Show hosts in table format (default)
zabbix-cli show_hosts
# Show hosts in JSON format
zabbix-cli --format json show_hosts

# Setting format in REPL
> --format json show_hosts
```

Or by setting the `app.output_format` parameter in the config file:

```toml
[app]
output_format = "json"
```

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

If you run into problems it is useful to enable debug logging in the config file:

```toml
[logging]
enabled = true
log_level = "DEBUG"
```

Find the log file with:

```bash
zabbix-cli open logs
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

#### Auth token file

Once you have authenticated with a username and password, zabbix-cli will store a session token if you configure `use_auth_token_file=true` in the config. This way you don't need to provide your credentials each time you run zabbix-cli. The token file should also be secured properly.

```toml
[app]
use_auth_token_file = true
```

The location of the auth token file can be changed in the config file:

```toml
[app]
auth_token_file = "/path/to/auth/token/file"
```

#### API token

Zabbix-cli also supports authentication with an API token specified directly in the config file:

```toml
[api]
auth_token = "API_TOKEN"

[app]
use_auth_token_file = false
```

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

If you do not wish to use Hatch, you can create a virtual environment manually:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U -e ".[test]"
```

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
