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

Binaries built with PyInstaller can be found on the [releases page](https://github.com/unioslo/zabbix-cli/releases). We build binaries for Linux (x86), macOS (ARM & x86) and Windows (x86) for each release.

## Quick start

Running `zabbix-cli` for the first time will prompt for a Zabbix URL, username and password. The URL should be the URL of the Zabbix web server without the `/api_jsonrpc.php` path.

Running without arguments will start the REPL:

```bash
zabbix-cli
```

<img width="60%" src="https://github.com/unioslo/zabbix-cli/blob/master/resources/open-autocomplete.png?raw=true">

## Usage

Zabbix-cli is a command line interface for Zabbix. It can be used in three ways:

1. **Interactive mode**: Start the REPL by running `zabbix-cli`. This will start a shell where you can run multiple commands in a persistent session.
2. **Single command**: Run a single command by running `zabbix-cli COMMAND`. This will run the command and print the output.
3. **Batch mode**: Run multiple commands from a file by running `zabbix-cli -f FILE`. The file should contain one command per line.

Command reference can be found in the [online user guide](https://unioslo.github.io/zabbix-cli/commands/) or by running `zabbix-cli --help`.

### Authentication

By default, the application will prompt for a username and password. Once authenticated, the application stores the session token in a file for future use.

For more information about the various authentication methods, see the [authentication guide](https://unioslo.github.io/zabbix-cli/guide/authentication/).

### Configuration

Zabbix-cli needs a config file. It is created when the application is started for the first time. The config file can be created manually with the `init` command:

```bash
zabbix-cli init --zabbix-url https://zabbix.example.com/
```

For more detailed information about the configuration file, see the [configuration guide](https://unioslo.github.io/zabbix-cli/guide/configuration/).

### Formats

Zabbix-cli supports two output formats: table and JSON. The default format is table, but it can be changed with the `--format` parameter:

```bash
# Show hosts in table format (default)
zabbix-cli show_hosts

# Show hosts in JSON format
zabbix-cli --format json show_hosts

# Set format in REPL mode
> --format json show_hosts
```

The default format can be configured with the `app.output.format` config option:

```toml
[app.output]
format = "json"
```

#### Table

<img width="60%" alt="format-table" src="https://github.com/user-attachments/assets/207fa12b-39c6-45b9-9f0e-7f217c723461">

The default rendering mode is a [Rich](https://github.com/Textualize/rich) table that adapts to the width of the terminal.

#### JSON

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

<details>
  <summary><code>show_host foo.example.com*</code></summary>

```json
{
  "message": "",
  "errors": [],
  "return_code": "Done",
  "result": {
    "hostid": "10648",
    "host": "foo.example.com",
    "description": "",
    "groups": [
      {
        "groupid": "22",
        "name": "All-hosts",
        "hosts": [],
        "flags": 0,
        "internal": null,
        "templates": []
      },
      {
        "groupid": "46",
        "name": "Source-foosource",
        "hosts": [],
        "flags": 0,
        "internal": null,
        "templates": []
      },
      {
        "groupid": "47",
        "name": "Hostgroup-bob-hosts",
        "hosts": [],
        "flags": 0,
        "internal": null,
        "templates": []
      },
      {
        "groupid": "48",
        "name": "Importance-X",
        "hosts": [],
        "flags": 0,
        "internal": null,
        "templates": []
      },
      {
        "groupid": "49",
        "name": "Hostgroup-alice-hosts",
        "hosts": [],
        "flags": 0,
        "internal": null,
        "templates": []
      }
    ],
    "templates": [],
    "inventory": {},
    "monitored_by": "proxy",
    "proxyid": "2",
    "proxy_groupid": "0",
    "maintenance_status": "0",
    "active_available": "0",
    "status": "0",
    "macros": [],
    "interfaces": [
      {
        "type": 1,
        "ip": "",
        "dns": "foo.example.com",
        "port": "10050",
        "useip": 0,
        "main": 1,
        "interfaceid": "49",
        "available": 0,
        "hostid": "10648",
        "bulk": null,
        "connection_mode": "Dns",
        "type_str": "Agent"
      }
    ],
    "proxy": {
      "proxyid": "2",
      "name": "proxy-prod02.example.com",
      "hosts": [],
      "status": null,
      "operating_mode": 0,
      "address": "127.0.0.1",
      "proxy_groupid": "1",
      "compatibility": 0,
      "version": 0,
      "local_address": "192.168.0.1",
      "local_port": "10051",
      "mode": "Active",
      "compatibility_str": "Undefined"
    },
    "zabbix_agent": "Unknown"
  }
}
```

</details>

<details>
  <summary><code>show_hosts foo.*</code></summary>

```json
{
  "message": "",
  "errors": [],
  "return_code": "Done",
  "result": [
    {
      "hostid": "10648",
      "host": "foo.example.com",
      "description": "",
      "groups": [
        {
          "groupid": "22",
          "name": "All-hosts",
          "hosts": [],
          "flags": 0,
          "internal": null,
          "templates": []
        },
        {
          "groupid": "46",
          "name": "Source-foosource",
          "hosts": [],
          "flags": 0,
          "internal": null,
          "templates": []
        },
        {
          "groupid": "47",
          "name": "Hostgroup-bob-hosts",
          "hosts": [],
          "flags": 0,
          "internal": null,
          "templates": []
        },
        {
          "groupid": "48",
          "name": "Importance-X",
          "hosts": [],
          "flags": 0,
          "internal": null,
          "templates": []
        },
        {
          "groupid": "49",
          "name": "Hostgroup-alice-hosts",
          "hosts": [],
          "flags": 0,
          "internal": null,
          "templates": []
        }
      ],
      "templates": [],
      "inventory": {},
      "monitored_by": "proxy",
      "proxyid": "2",
      "proxy_groupid": "0",
      "maintenance_status": "0",
      "active_available": "0",
      "status": "0",
      "macros": [],
      "interfaces": [],
      "proxy": {
        "proxyid": "2",
        "name": "proxy-prod02.example.com",
        "hosts": [],
        "status": null,
        "operating_mode": 0,
        "address": "127.0.0.1",
        "proxy_groupid": "1",
        "compatibility": 0,
        "version": 0,
        "local_address": "192.168.0.1",
        "local_port": "10051",
        "mode": "Active",
        "compatibility_str": "Undefined"
      },
      "zabbix_agent": "Unknown"
    }
  ]
}
```

</details>

## Development

Zabbix-cli currently uses [uv](https://docs.astral.sh/uv/)  and [Hatch](https://hatch.pypa.io/latest/) for project management and packaging. To start off, clone the repository:

```bash
git clone https://github.com/unioslo/zabbix-cli.git
```

Then make a virtual environment using uv:

```bash
uv venv
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
