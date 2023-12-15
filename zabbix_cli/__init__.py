from __future__ import annotations


# Patch typer to remove dimming of help text
# https://github.com/tiangolo/typer/issues/437#issuecomment-1224149402
try:
    import typer

    typer.rich_utils.STYLE_HELPTEXT = ""
except Exception:  # likely AttributeError?
    import rich
    import sys

    # Rudimentary, but provides enough info to debug and fix the issue
    console = rich.console.Console(stderr=True)
    console.print_exception()
    console.print("[bold red]Failed to patch [i]typer.rich_utils.STYLE_HELPTEXT[/][/]")
    console.print(f"Typer version: {typer.__version__}")
    console.print(f"Python version: {sys.version}")

__version__ = "2.3.2"
