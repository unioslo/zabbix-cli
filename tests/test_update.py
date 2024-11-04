from __future__ import annotations

import pytest
from zabbix_cli.update import PyInstallerUpdater
from zabbix_cli.update import UpdateError


@pytest.mark.parametrize(
    "os, arch, version, expect_info",
    [
        ("linux", "x86_64", "1.2.3", "1.2.3-linux-x86_64"),
        ("darwin", "x86_64", "1.2.3", "1.2.3-macos-x86_64"),
        ("darwin", "arm64", "1.2.3", "1.2.3-macos-arm64"),
        ("win32", "x86_64", "1.2.3", "1.2.3-win-x86_64.exe"),
        # Unsupported platforms
        pytest.param(
            "linux",
            "arm64",
            "1.2.3",
            "1.2.3-linux-arm64",
            marks=pytest.mark.xfail(raises=UpdateError, strict=True),
        ),
        pytest.param(
            "linux",
            "armv7l",
            "1.2.3",
            "1.2.3-linux-armv7l",
            marks=pytest.mark.xfail(raises=UpdateError, strict=True),
        ),
    ],
)
def test_pyinstaller_updater_get_url(
    os: str, arch: str, version: str, expect_info: str
):
    BASE_URL = (
        "https://github.com/unioslo/zabbix-cli/releases/latest/download/zabbix-cli"
    )
    expect_url = f"{BASE_URL}-{expect_info}"

    url = PyInstallerUpdater.get_url(os, arch, version)
    assert url == expect_url
