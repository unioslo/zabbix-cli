from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional
from typing import Union

from strenum import StrEnum

from zabbix_cli.dirs import CONFIG_DIR
from zabbix_cli.dirs import DATA_DIR
from zabbix_cli.dirs import SITE_CONFIG_DIR

logger = logging.getLogger("zabbix_cli.config")

# Config file basename
CONFIG_FILENAME = "zabbix-cli.toml"
DEFAULT_CONFIG_FILE = CONFIG_DIR / CONFIG_FILENAME


CONFIG_PRIORITY = (
    Path() / CONFIG_FILENAME,  # current directory
    DEFAULT_CONFIG_FILE,  # local config directory
    SITE_CONFIG_DIR / CONFIG_FILENAME,  # system config directory
)


AUTH_TOKEN_FILE = DATA_DIR / ".zabbix-cli_auth_token"
"""Path to file containing API session token."""

AUTH_FILE = DATA_DIR / ".zabbix-cli_auth"
"""Path to file containing user credentials."""


# Environment variable names
class ConfigEnvVars:
    USERNAME = "ZABBIX_USERNAME"
    PASSWORD = "ZABBIX_PASSWORD"
    API_TOKEN = "ZABBIX_API_TOKEN"


class OutputFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
    TABLE = "table"


class SecretMode(StrEnum):
    """Mode for serializing secrets."""

    HIDE = "hide"
    MASK = "masked"
    PLAIN = "plain"

    _DEFAULT = MASK

    @classmethod
    def from_context(
        cls, context: Optional[Union[Dict[str, Any], Callable[..., Dict[str, Any]]]]
    ) -> SecretMode:
        """Get the secret mode from a serialization context."""
        if isinstance(context, dict) and (ctx := context.get("secrets")) is not None:
            # Support for old-style context values (true/false)
            # as well as new context values (enum values)
            try:
                if isinstance(ctx, SecretMode):
                    return ctx
                elif ctx is True:
                    return cls.PLAIN
                elif ctx is False:
                    return cls.MASK
                else:
                    return cls(str(ctx).lower())
            except ValueError:
                logger.warning(
                    "Got invalid secret mode from context %s: %s", context, ctx
                )
        return cls._DEFAULT
