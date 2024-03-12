from __future__ import annotations

import typer


def main(
    input_file: str = typer.Option(
        "-",
        "--input-file",
        "-f",
        metavar="FILE",
        help="File to read commands from, defaults to stdin",
    ),
) -> None:
    pass
