from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(Path(__file__).parent.as_posix())

import gen_cli_data  # noqa
import gen_cli_options  # noqa
import gen_command_list  # noqa
import docs.scripts.gen_commands as gen_commands  # noqa
import gen_formats  # noqa


# NOTE: for some reason putting this logic into a main() function causes the first
# build to not actually include all the generated files, while just putting it
# at the top-level works fine (albeit with a warning about a missing main() function)
# Not sure why, but it's not worth investigating right now.

for mod in [
    gen_cli_data,
    gen_cli_options,
    gen_command_list,
    gen_commands,
    gen_formats,
]:
    mod.main()
