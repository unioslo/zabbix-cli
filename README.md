# Zabbix-cli

[![PyPI](https://img.shields.io/pypi/v/zabbix-cli-uio)](https://pypi.org/project/zabbix-cli-uio/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/zabbix-cli-uio)](<https://pypi.org/project/zabbix-cli-uio/>)
[![PyPI - License](https://img.shields.io/pypi/l/zabbix-cli-uio)](<https://pypi.org/project/zabbix-cli-uio/>)
![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/unioslo/zabbix-cli/test.yml?branch=master&label=tests)

<p align="center">
  <table>
    <tr>
        <td>
            <img width="100%" src="https://github.com/unioslo/zabbix-cli/blob/master/resources/help.png?raw=true">
        </td>
        <td>
            <img width="100%" src="https://github.com/unioslo/zabbix-cli/blob/master/resources/hosts.png?raw=true">
        </td>
    </tr>
    <tr>
        <td>
            <img width="100%" src="https://github.com/unioslo/zabbix-cli/blob/master/resources/host-inventory.png?raw=true">
        </td>
        <td>
            <img width="100%" src="https://github.com/unioslo/zabbix-cli/blob/master/resources/proxies.png?raw=true">
        </td>
    </tr>
  </table>
</p>

**Zabbix-CLI v3 has been completely rewritten from the ground up. The old version can be found [here](https://github.com/unioslo/zabbix-cli/tree/2.3.2).**

## About

Zabbix-cli is a command line interface for performing common administrative tasks tasks in [Zabbix monitoring system](https://www.zabbix.com/) via the [Zabbix API](https://www.zabbix.com/documentation/current/en/manual/api).

The zabbix-cli code is written in [Python](https://www.python.org/) and distributed under the GNU General Public License v3. It has been developed and tested by [University Center for Information Technology](https://www.usit.uio.no/) at [the University of Oslo, Norway](https://www.uio.no/).

The project home page is on [GitHub](https://github.com/unioslo/zabbix-cli). Please report any issues or improvements there.

The manual is available online at <https://unioslo.github.io/zabbix-cli/>.

## Install

### From source

> [!NOTE]
> We are in the process of acquiring the name `zabbix-cli` on PyPI. Until then, installation must be done via the mirror package `zabbix-cli-uio`.

#### [uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv tool install zabbix-cli-uio
```

#### [uvx](https://docs.astral.sh/uv/#tool-management)

```bash

uvx --from zabbix-cli-uio zabbix-cli
```

#### [pipx](https://pipx.pypa.io/stable/)

```bash
pipx install zabbix-cli-uio
```

### Homebrew

A homebrew package exists, but it is maintained by a third party. It can be installed with:

```bash
brew install zabbix-cli
```

### Binary

Binaries built with PyInstaller can be found on the [releases page](https://github.com/unioslo/zabbix-cli/releases). We build binaries for Linux (x86), macOS (ARM) and Windows (x86) for each release.

## Quick start

```bash
# Initialize the config file with your Zabbix URL
zabbix-cli init --zabbix-url https://your-zabbix-url.com/
# Start the REPL
zabbix-cli
```

<img width="60%" src="https://github.com/unioslo/zabbix-cli/blob/master/resources/open-autocomplete.png?raw=true">

## Usage

Zabbix-cli is a command line interface for Zabbix. It can be used in three ways:

1. **Interactive mode**: Start the REPL by running `zabbix-cli`. This will start a shell where you can run multiple commands in a persistent session.
2. **Single command**: Run a single command by running `zabbix-cli COMMAND`. This will run the command and print the output.
3. **Batch mode**: Run multiple commands from a file by running `zabbix-cli -f FILE`. The file should contain one command per line.

Command reference can be found in the [online user guide](https://unioslo.github.io/zabbix-cli/guide/introduction/) or by running `zabbix-cli --help`.

## Formats

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

### Table

<img width="60%" alt="format-table" src="https://github.com/user-attachments/assets/207fa12b-39c6-45b9-9f0e-7f217c723461">

The default rendering mode is a [Rich](https://github.com/Textualize/rich) table that adapts to the width of the terminal.

### JSON

<img width="60%" alt="format-json" src="https://github.com/user-attachments/assets/680f507b-dc2a-41b2-87c4-c3a443d83979">

The JSON output format is always in this format, where `ResultT` is the expected result type:

```json
{
  "message": "",
  "errors": [],
  "return_code": "Done",
  "result": ResultT
}
```

The type of the `result` field varies based on the command run. For `show_host` it is a single Host object, while for `show_hosts` it is an _array_ of Host objects.

## Configuration

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

## Authentication

Zabbix-cli provides several ways to authenticate. They are tried in the following order if multiple are set:

1. [API token from config file](#api-token-config-file)
2. [API token from environment variables](#api-token-environment-variables)
3. [Auth token from auth token file](#auth-token-file)
4. [Username and password from config file](#config-file)
5. [Username and password from auth file](#auth-file)
6. [Username and password from environment variables](#environment-variables)
7. [Username and password from prompt](#prompt)

### Username and Password

Password-based authentication is the default way to authenticate with Zabbix-cli. If the application is unable to determine authentication from other sources, it will prompt for a username and password.

#### Config file

The password can be set directly in the config file:

```toml
[api]
zabbix_url = "https://zabbix.example.com/"
username = "Admin"
password = "zabbix"
```

#### Auth file

An auth file named `.zabbix-cli_auth` can be created in the user's home directory. The content of this file should be in the `USERNAME::PASSWORD` format.

```bash
echo "Admin::zabbix" > ~/.zabbix-cli_auth
```

The location of this file can be changed in the config file:

```toml
[app]
auth_file = "/path/to/auth/file"
```

#### Environment variables

The username and password can be set as environment variables:

```bash
export ZABBIX_USERNAME="Admin"
export ZABBIX_PASSWORD="zabbix"
```

#### Prompt

By omitting the `password` parameter in the config file or when all other authentication methods have been exhausted, you will be prompted for a password when starting zabbix-cli:

```toml
[api]
zabbix_url = "https://zabbix.example.com/"
username = "Admin"
```

### API token

API token authentication foregoes the need for a username and password. The token can be an API token created in the web frontend or a user's session token obtained by logging in.

#### API token (config file)

API token can be specified directly in the config file:

```toml
[api]
auth_token = "API_TOKEN"
```

#### API token (environment variables)

API token can be specified as an environment variable:

```bash
export ZABBIX_API_TOKEN="API TOKEN"
```

#### Auth token file

The application can store the session token returned by the Zabbix API when logging in to a file on your computer. The file is then used for subsequent sessions to authenticate with the Zabbix API.

This feature useful when authenticating with a username and password from a prompt, which would otherwise require you to enter your password every time you start the application.

The feature is enabled by default in the config file:

```toml
[app]
use_auth_token_file = true
```

The location of the auth token file can be changed in the config file:

```toml
[app]
auth_token_file = "/path/to/auth/token/file"
```

By default, the auth token file is not required to have secure permissions. If you want to require the file to have `600` (rw-------) permissions, you can set `allow_insecure_auth_file=false` in the config file. This has no effect on Windows.

```toml
[app]
allow_insecure_auth_file = false
```

Zabbix-cli attempts to set `600` permissions when writing the auth token file if `allow_insecure_auth_file=false`.

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
