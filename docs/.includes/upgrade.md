=== "uv"

    ```bash
    uv tool upgrade zabbix-cli-uio
    ```

=== "pipx"

    ```bash
    pipx upgrade zabbix-cli-uio
    ```

=== "Homebrew"

    ```bash
    brew upgrade zabbix-cli
    ```

=== "Binary (Automatic)"

    Zabbix-cli has experimental support for updating itself. You can use the `zabbix-cli update` command to update the application to the latest version.

    !!! danger "Write access required"
        The application must have write access to itself and the directory it resides in.

    ```bash
    zabbix-cli update
    ```

=== "Binary (Manual)"

    The latest binary can be downloaded from [GitHub releases page](https://github.com/unioslo/zabbix-cli/releases). Download the binary for your platform and replace the current one.

    !!! warning "Linux & macOS"

        Remember to make the binary executable with `chmod +x zabbix-cli`.
