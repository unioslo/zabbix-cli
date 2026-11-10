from __future__ import annotations

from pathlib import Path

import pytest
from zabbix_cli.update import PyInstallerUpdater, download_file


@pytest.mark.parametrize(
    "os, arch, version, expect_info",
    [
        ("linux", "x86_64", "1.2.3", "1.2.3-linux-x86_64"),
        ("linux", "arm64", "1.2.3", "1.2.3-linux-arm64"),
        ("linux", "armv7l", "1.2.3", "1.2.3-linux-armv7l"),
        ("darwin", "x86_64", "1.2.3", "1.2.3-macos-x86_64"),
        ("darwin", "arm64", "1.2.3", "1.2.3-macos-arm64"),
        ("win32", "x86_64", "1.2.3", "1.2.3-win-x86_64.exe"),
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


def test_download_file_without_content_length(monkeypatch, tmp_path: Path):
    """Downloads using chunked encoding (no Content-Length) must not crash."""

    class FakeResponse:
        status_code = 200
        headers: dict = {}

        def iter_bytes(self):
            yield b"data"

    class FakeStream:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *args):
            return False

    import zabbix_cli.update as update_module

    monkeypatch.setattr(update_module.httpx, "stream", FakeStream)
    dest = tmp_path / "zabbix-cli"
    download_file("https://example.com/zabbix-cli", dest)
    assert dest.read_bytes() == b"data"
