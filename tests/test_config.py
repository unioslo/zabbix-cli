from __future__ import annotations

import pytest
from pydantic import ValidationError
from zabbix_cli.config.model import Config


def test_config_default() -> None:
    """Assert that the config by default only requires a URL."""
    with pytest.raises(ValidationError) as excinfo:
        Config()
    assert "1 validation error" in str(excinfo.value)
    assert "url" in str(excinfo.value)


def test_sample_config() -> None:
    """Assert that the sample config can be instantiated."""
    assert Config.sample_config()
