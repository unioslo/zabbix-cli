=== "Cross-platform (pipx)"

    It is highly recommended to install the package with [`pipx`](https://pipx.pypa.io/stable/) to avoid conflicts with other Python packages on your system.

    ```bash
    pip install pipx
    pipx install zabbix-cli-uio
    ```

    This will install `zabbix-cli` in an isolated environment and make it available on your system path.


    !!! note
        We are in the process of acquiring the unmaintained PyPI package name `zabbixcli`, which will allow us to publish this package on PyPI under the name `zabbix-cli`. Until then, installation must be done via the aliased package name `zabbix-cli-uio`.

    {% if install_expand is defined and install_expand == true %}
    ### Multiple installed versions
    {% include-markdown ".includes/pipx-multiple.md" %}
    {% endif %}

=== "Cross-platform (pip)"

    If you prefer to install the package with `pip`, you can do so with the following command:

    ```bash
    pip install zabbix-cli-uio
    ```

    This will install `zabbix-cli` in your user environment.

=== "MacOS"

    You can install `zabbix-cli` with Homebrew:

    ```bash
    brew install zabbix-cli
    ```

    !!! warning
        The Homebrew package is maintained by a third party. It may be outdated or contain bugs. For the most up to date version, follow the installation instructions for pipx.

=== "PyInstaller Binary"

    We build binaries with PyInstaller for each tagged release of Zabbix-cli. You can download the latest release from the [GitHub releases page](https://github.com/unioslo/zabbix-cli/releases).

    Depending on your platform, you might need to make the binary executable:

    ```bash
    # Rename and move the binary to a location in your PATH
    mv zabbix-cli-ubuntu-22.04-3.12 /usr/local/bin/zabbix-cli

    # Make it executable
    chmod +x /usr/local/bin/zabbix-cli
    ```
