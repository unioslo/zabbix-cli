from __future__ import annotations


def blue(message: str) -> str:
    return f"[blue]{message}[/]"


def cyan(message: str) -> str:
    return f"[cyan]{message}[/]"


def green(message: str) -> str:
    return f"[green]{message}[/]"


def magenta(message: str) -> str:
    return f"[magenta]{message}[/]"


def red(message: str) -> str:
    return f"[red]{message}[/]"


def yellow(message: str) -> str:
    return f"[yellow]{message}[/]"


def bold(message: str) -> str:
    return f"[bold]{message}[/]"


def warning_color(message: str) -> str:
    return yellow(message)


def error_color(message: str) -> str:
    return red(message)


def success_color(message: str) -> str:
    return green(message)


def info_color(message: str) -> str:
    return message
