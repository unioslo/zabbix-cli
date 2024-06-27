from __future__ import annotations

import os

import pytest
from zabbix_cli.output.prompts import HEADLESS_VARS_SET
from zabbix_cli.output.prompts import TRUE_ARGS
from zabbix_cli.output.prompts import is_headless


@pytest.mark.parametrize("envvar", HEADLESS_VARS_SET)
@pytest.mark.parametrize("value", TRUE_ARGS)
def test_is_headless_set_true(envvar: str, value: str):
    """Returns True when the envvar is set to a truthy value."""
    _do_test_is_headless(envvar, value, True)


@pytest.mark.parametrize("envvar", HEADLESS_VARS_SET)
@pytest.mark.parametrize("value", ["0", "false", "", None])
def test_is_headless_set_false(envvar: str, value: str):
    """Returns False when the envvar is set to a falsey value or unset"""
    _do_test_is_headless(envvar, value, False)


@pytest.mark.parametrize(
    "envvar, value, expected",
    [
        ("DEBIAN_FRONTEND", "noninteractive", True),
        ("DEBIAN_FRONTEND", "teletype", False),
        ("DEBIAN_FRONTEND", "readline", False),
        ("DEBIAN_FRONTEND", "dialog", False),
        ("DEBIAN_FRONTEND", "gtk", False),
        ("DEBIAN_FRONTEND", "text", False),
        ("DEBIAN_FRONTEND", "anything", False),
        ("DEBIAN_FRONTEND", None, False),
        ("DEBIAN_FRONTEND", "", False),
        ("DEBIAN_FRONTEND", "0", False),
        ("DEBIAN_FRONTEND", "false", False),
        ("DEBIAN_FRONTEND", "1", False),
        ("DEBIAN_FRONTEND", "true", False),
    ],
)
def test_is_headless_map(envvar: str, value: str, expected: bool) -> None:
    """Returns True when the envvar is set to a specific value."""
    _do_test_is_headless(envvar, value, expected)


def _do_test_is_headless(envvar: str, value: str | None, expected: bool):
    """Helper function for testing is_headless.

    Sets/clears envvar before testing, then clears cache and envvar after test.
    """
    _orig_environ = os.environ.copy()
    os.environ.clear()
    try:
        if value is None:
            os.environ.pop(envvar, None)
        else:
            os.environ[envvar] = value
        assert is_headless() == expected
    finally:
        # IMPORTANT: Remove envvar and clear cache after each test
        os.environ = _orig_environ  # type: ignore
        is_headless.cache_clear()
