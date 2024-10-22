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

=== "pip(x)"

    Install with [`pipx`](https://pipx.pypa.io/stable/) to avoid conflicts with other Python packages in your system:

    ```bash
    pipx install zabbix-cli-uio
    ```

    If you prefer to install the package with `pip`:

    ```bash
    pip install zabbix-cli-uio
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

    We build binaries with PyInstaller for each tagged release of Zabbix-cli. You can download the latest release from the [GitHub releases page](https://github.com/unioslo/zabbix-cli/releases).

    Depending on your platform, you might need to make the binary executable and move it to a location in your `PATH`. Linux users can follow these steps:

    ```bash
    # Download the latest release and name it "zabbix-cli"
    curl -L -o zabbix-cli https://github.com/unioslo/zabbix-cli/releases/latest/download/zabbix-cli-ubuntu-latest-3.12

    # Make it executable
    chmod +x zabbix-cli

    # Move the binary to a location in your PATH
    mv zabbix-cli /usr/local/bin/zabbix-cli
    ```
