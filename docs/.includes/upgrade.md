=== "uv"

    ```bash
    uv tool upgrade zabbix-cli-uio
    ```

=== "pipx"

    ```bash
    pipx upgrade zabbix-cli-uio
    ```

=== "pip"

    ```bash
    pip install --upgrade zabbix-cli-uio
    ```

=== "Homebrew"

    ```bash
    brew upgrade zabbix-cli
    ```

=== "Binary (Automatic)"

    Zabbix-cli has experimental support for updating itself. You can use the `zabbix-cli update` command to download and update the application to the latest version.

    !!! danger "Write access required"
        The application must have write access to itself and the directory it resides in.

    ```bash
    zabbix-cli update
    ```

=== "Binary (Manual)"

    The latest binary can be downloaded from [GitHub releases page](https://github.com/unioslo/zabbix-cli/releases). Download the binary for your platform and replace the current one.

    To download the latest Linux binary and replace the current one:

    ```bash
    curl -L -o zabbix-cli https://github.com/unioslo/zabbix-cli/releases/latest/download/zabbix-cli-ubuntu-latest-3.12

    chmod +x zabbix-cli

    # Replace destination with the path to the current binary
    mv zabbix-cli /usr/local/bin/zabbix-cli
    ```
