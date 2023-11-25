import pytest
from packaging.version import Version

from zabbix_cli.apiutils import username_by_version, proxyname_by_version


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
def test_username_by_version(version: Version, expect: str):
    assert username_by_version(version) == expect


@pytest.mark.parametrize(
        "version, expect",
        [
            # TODO (pederhan): decide on a set number of versions we test against
            # instead of coming up with them on the fly such as here.
            # Do we want to test against minor and patch versions or only major?
            (Version("7.0.0"), "name"),
            (Version("6.0.0"), "host"),
            (Version("5.0.0"), "host"),
            (Version("3.0.0"), "host"),
            (Version("2.0.0"), "host"),
            (Version("1.0.0"), "host"),
        ],
)
def test_proxyname_by_version(version: Version, expect: str):
    assert proxyname_by_version(version) == expect

