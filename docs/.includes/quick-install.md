=== "Cross-platform (pipx)"

    It is highly recommended to install the package with `pipx` to avoid conflicts with other Python packages.

    ```bash
    pip install pipx
    pipx install zabbix-cli
    ```

    This will install `zabbix-cli` in an isolated environment, and make it available on your system path.

=== "pip"

    If you prefer to install the package with `pip`, you can do so with the following command:

    ```bash
    pip install zabbix-cli
    ```

    This will install `zabbix-cli` in your user environment.

=== "MacOS"

    You can install `zabbix-cli` with Homebrew:

    ```bash
    brew install zabbix-cli
    ```

    !!! warning
        The Homebrew package is not maintained by the author of `zabbix-cli`. It may be outdated or contain bugs. For the most up to date version, follow the installation instructions for pipx.
