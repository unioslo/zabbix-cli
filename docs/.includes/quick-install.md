=== "uv"

    Install with [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to avoid conflicts with other Python packages in your system:

    ```bash
    uv tool install zabbix-cli-uio
    ```

    To try out Zabbix-CLI without installing it, run it directly with [`uvx`](https://docs.astral.sh/uv/#tool-management):

    ```bash
    uvx --from zabbix-cli-uio zabbix-cli
    ```

    {% include-markdown ".includes/admonition-pypi.md" %}

=== "pipx"

    Install with [`pipx`](https://pipx.pypa.io/stable/) to avoid conflicts with other Python packages in your system:

    ```bash
    pipx install zabbix-cli-uio
    ```

    {% include-markdown ".includes/admonition-pypi.md" %}

=== "Homebrew"

    You can install `zabbix-cli` with Homebrew:

    ```bash
    brew install zabbix-cli
    ```

    !!! warning
        The Homebrew package is maintained by a third party. It may be outdated or contain bugs. For the most up to date version, follow the installation instructions for pipx.

=== "Binary"

    Binaries are built with PyInstaller for each release and can be downloaded from the [GitHub releases page](https://github.com/unioslo/zabbix-cli/releases). Download the correct binary for your platform and save it as `zabbix-cli`.

    !!! warning "Linux & macOS"

        Remember to make the binary executable with `chmod +x zabbix-cli`.
