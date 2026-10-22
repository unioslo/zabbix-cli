from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.append(Path(__file__).parent.as_posix())

import docs.scripts.gen_commands as gen_commands  # noqa
import gen_cli_data  # noqa
import gen_cli_options  # noqa
import gen_command_list  # noqa
import gen_formats  # noqa
import gen_config_data  # noqa


def main(*args: Any, **kwargs: Any) -> None:
    for mod in [
        gen_cli_data,
        gen_cli_options,
        gen_command_list,
        gen_commands,
        gen_formats,
        gen_config_data,
    ]:
        mod.main()
