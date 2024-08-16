from __future__ import annotations

import pytest
from packaging.version import Version
from zabbix_cli.pyzabbix import compat


def test_packaging_version_release_sanity():
    """Ensures that the `Version.release` tuple is in the correct format and
    supports users running pre-release versions of Zabbix.
    """
    assert Version("7.0.0").release == (7, 0, 0)
    # Test that all types of pre-releases evaluate to the same release tuple
    for pr in ["a1", "b1", "rc1", "alpha1", "beta1"]:
        assert Version(f"7.0.0{pr}").release == (7, 0, 0)
        assert Version(f"7.0.0{pr}").release >= (7, 0, 0)
        assert Version(f"7.0.0{pr}").release <= (7, 0, 0)


@pytest.mark.parametrize(
    "version, expect",
    [
        # TODO (pederhan): decide on a set of versions we test against
        # instead of coming up with them on the fly, such as here.
        # Do we test against only major versions or minor versions as well?
        (Version("7.0.0"), "proxyid"),
        (Version("6.0.0"), "proxy_hostid"),
        (Version("5.0.0"), "proxy_hostid"),
        (Version("3.0.0"), "proxy_hostid"),
        (Version("2.0.0"), "proxy_hostid"),
        (Version("1.0.0"), "proxy_hostid"),
    ],
)
def test_host_proxyid(version: Version, expect: str):
    assert compat.host_proxyid(version) == expect


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
def test_login_user_name(version: Version, expect: str):
    assert compat.login_user_name(version) == expect


@pytest.mark.parametrize(
    "version, expect",
    [
        (Version("7.0.0"), "name"),
        (Version("6.0.0"), "host"),
        (Version("5.0.0"), "host"),
        (Version("3.0.0"), "host"),
        (Version("2.0.0"), "host"),
        (Version("1.0.0"), "host"),
    ],
)
def test_proxy_name(version: Version, expect: str):
    assert compat.proxy_name(version) == expect


@pytest.mark.parametrize(
    "version, expect",
    [
        (Version("7.0.0"), "username"),
        (Version("6.4.0"), "username"),
        (Version("6.0.0"), "username"),
        # NOTE: special case here where we use "alias" instead of "username"
        # even though it was deprecated in 5.4.0 (matches historical zabbix_cli behavior)
        (Version("5.4.0"), "alias"),
        (Version("5.0.0"), "alias"),
        (Version("3.0.0"), "alias"),
        (Version("2.0.0"), "alias"),
        (Version("1.0.0"), "alias"),
    ],
)
def test_user_name(version: Version, expect: str):
    assert compat.user_name(version) == expect
