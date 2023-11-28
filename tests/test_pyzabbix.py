from __future__ import annotations

import pytest
from packaging.version import Version

from zabbix_cli.pyzabbix import user_param_from_version


@pytest.mark.parametrize(
    "version, expect",
    [
        (Version("7.0.0"), "username"),
        (Version("6.0.0"), "username"),
        (Version("6.2.0"), "username"),
        (Version("6.4.0"), "username"),
        (Version("5.4.0"), "username"),
        (Version("5.4.1"), "username"),
        (Version("5.3.9"), "user"),
        (Version("5.2.0"), "user"),
        (Version("5.2"), "user"),
        (Version("5.0"), "user"),
        (Version("4.0"), "user"),
        (Version("2.0"), "user"),
    ],
)
def test_user_param_from_version(version: Version, expect: str):
    assert user_param_from_version(version) == expect
