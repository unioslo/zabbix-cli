"""Base model for all configuration models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict
from pydantic import PrivateAttr
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic import model_validator
from typing_extensions import Self

from zabbix_cli.config.utils import check_deprecated_fields


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    _deprecation_checked: bool = PrivateAttr(default=False)
    """Has performed a deprecaction check for the fields on the model."""

    @field_validator("*")
    @classmethod
    def _conf_bool_validator_compat(cls, v: Any, info: ValidationInfo) -> Any:
        """Handles old config files that specified bools as ON/OFF."""
        if not isinstance(v, str):
            return v
        if v.upper() == "ON":
            return True
        if v.upper() == "OFF":
            return False
        return v

    @model_validator(mode="after")
    def _check_deprecated_fields(self) -> Self:
        """Check for deprecated fields and log warnings."""
        if not self._deprecation_checked:
            check_deprecated_fields(self)
            self._deprecation_checked = True
        return self
