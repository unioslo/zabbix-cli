from __future__ import annotations

import sys
from pathlib import Path

import yaml  # type: ignore
from harbor_cli.format import OutputFormat

sys.path.append(Path(__file__).parent.as_posix())

from common import DATA_DIR  # noqa


def main() -> None:
    fmts = [fmt.value for fmt in OutputFormat]

    with open(DATA_DIR / "formats.yaml", "w") as f:
        yaml.dump(fmts, f, default_flow_style=False)


if __name__ == "__main__":
    main()
