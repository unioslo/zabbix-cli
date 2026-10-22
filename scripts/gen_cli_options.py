"""Generates a YAML file containing all the global options for the CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

import yaml  # type: ignore
from zabbix_cli.main import app

sys.path.append(Path(__file__).parent.as_posix())
from common import DATA_DIR  # noqa
from utils.commands import get_app_callback_options  # noqa


def convert_envvar_value(text: str | list[str] | None) -> list[str] | None:
    # The envvars might actually be instances of `harbor_cli.config.EnvVar`,
    # which the YAML writer does not convert to strings. Hence `str(...)`
    if isinstance(text, list):
        return [str(t) for t in text]
    elif isinstance(text, str):
        # convert to str (might be enum) and wrap in list
        return [str(text)]
    elif text is None:
        return []
    else:
        raise ValueError(f"Unexpected option env var type {type(text)} ({text})")


# name it OptInfo to avoid confusion with typer.models.OptionInfo
class OptInfo(NamedTuple):
    params: list[str]
    help: str | None
    envvar: list[str]
    config_value: str | None

    @property
    def fragment(self) -> str | None:
        if self.config_value is None:
            return None
        return self.config_value.replace(".", "")

    def to_dict(self) -> dict[str, str | list[str] | None]:
        return {
            "params": ", ".join(f"`{p}`" for p in self.params),
            "help": self.help or "",
            "envvar": convert_envvar_value(self.envvar),
            "config_value": self.config_value,
            "fragment": self.fragment,
        }


def main() -> None:
    options = []  # type: list[OptInfo]
    for option in get_app_callback_options(app):
        if not option.param_decls:
            continue
        conf_value = None
        if hasattr(option, "config_override"):
            conf_value = option.config_override
        h = option._help_original if hasattr(option, "_help_original") else option.help
        o = OptInfo(
            params=option.param_decls,
            help=h,
            envvar=option.envvar,
            config_value=conf_value,
        )
        options.append(o)

    to_dump = [o.to_dict() for o in options]

    with open(DATA_DIR / "options.yaml", "w") as f:
        yaml.dump(to_dump, f, sort_keys=False)


if __name__ == "__main__":
    main()
