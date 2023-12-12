from __future__ import annotations

import logging
import math
import os
from functools import wraps
from pathlib import Path
from typing import Any
from typing import Callable
from typing import overload
from typing import Type
from typing import TypeVar

from rich.prompt import Confirm
from rich.prompt import FloatPrompt
from rich.prompt import IntPrompt
from rich.prompt import Prompt
from typing_extensions import ParamSpec

from .console import console
from .console import error
from .console import exit_err
from .console import exit_ok
from .formatting.path import path_link
from .style import Icon
from .style.color import green
from .style.color import yellow
from zabbix_cli._types import EllipsisType
from zabbix_cli.state import get_state

T = TypeVar("T")
P = ParamSpec("P")


def no_headless(f: Callable[P, T]) -> Callable[P, T]:
    """Decorator that causes application to exit if called from a headless environment."""

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        if is_headless():
            # TODO: determine caller etc. via the stack
            # If a default argument was passed in, we can return that:
            if (default := kwargs.get("default")) and default is not Ellipsis:
                logging.debug(
                    "Returning default value from %s(%s, %s)", f, args, kwargs
                )
                return default  # type: ignore # bit of a hack
            exit_err(
                f"Headless session detected; user input required. Arguments: {args}, {kwargs}."
            )
        return f(*args, **kwargs)

    return wrapper


def is_headless() -> bool:
    """Determines if we are running in a headless environment (e.g. CI, Docker, etc.)"""
    if os.environ.get("CI", None):
        return True
    elif os.environ.get("DEBIAN_FRONTEND", None) == "noninteractive":
        return True
    # Probably not safe to test "DISPLAY" here
    return False


def prompt_msg(*msgs: str) -> str:
    return f"[bold]{green(Icon.PROMPT)} {' '.join(msg.strip() for msg in filter(None, msgs))}[/bold]"


@no_headless
def str_prompt(
    prompt: str,
    default: str | EllipsisType = ...,
    password: bool = False,
    show_default: bool = True,
    choices: list[str] | None = None,
    empty_ok: bool = False,
    strip: bool = True,
    **kwargs: Any,
) -> str:
    """Prompts the user for a string input. Optionally controls
    for empty input. Loops until a valid input is provided.

    Parameters
    ----------
    prompt : str
        Prompt to display to the user.
    default : Any, optional
        Default value to use if the user does not provide input.
        If not provided, the user will be required to provide input.
    password : bool, optional
        Whether to hide the input, by default False
    show_default : bool, optional
        Show the default value, by default True
        `password=True` supercedes this option, and sets it to False.
    empty_ok : bool, optional
        Allow input consisting of no characters or only whitespace,
        by default False
    strip : bool, optional
        Strip whitespace from the input, by default True
        Must be `False` to preserve whitespace when `empty_ok=True`.
    callback : Callable[[str], str], optional
        Callback function to run on the input before returning it,
        by default None
    """
    # Don't permit secrets to be shown ever
    if password:
        show_default = False

    # Notify user that a default secret will be used,
    # but don't actually show the secret
    if password and default not in (None, ..., ""):
        _prompt_add = "(leave empty to use existing value)"
    else:
        _prompt_add = ""
    msg = prompt_msg(prompt, _prompt_add)

    inp = None
    while not inp:
        inp = Prompt.ask(
            msg,
            console=console,
            password=password,
            show_default=show_default,
            default=default,
            choices=choices,
            **kwargs,
        )
        if empty_ok:  # nothing else to check
            break

        if not inp:
            error("Input cannot be empty.")
        elif inp.isspace() and inp != default:
            error("Input cannot solely consist of whitespace.")
        else:
            break
    return inp.strip() if strip else inp


@no_headless
def int_prompt(
    prompt: str,
    default: int | None = None,
    show_default: bool = True,
    min: int | None = None,
    max: int | None = None,
    show_range: bool = True,
    **kwargs: Any,
) -> int:
    return _number_prompt(
        IntPrompt,
        prompt,
        default=default,
        show_default=show_default,
        min=min,
        max=max,
        show_range=show_range,
        **kwargs,
    )


@no_headless
def float_prompt(
    prompt: str,
    default: float | None = None,
    show_default: bool = True,
    min: float | None = None,
    max: float | None = None,
    show_range: bool = True,
    **kwargs: Any,
) -> float:
    val = _number_prompt(
        FloatPrompt,
        prompt,
        default=default,
        show_default=show_default,
        min=min,
        max=max,
        show_range=show_range,
        **kwargs,
    )
    # explicit cast to float since users might pass in int as default
    # and we have no logic inside _number_prompt to handle that
    return float(val)


@overload
def _number_prompt(
    prompt_type: Type[IntPrompt],
    prompt: str,
    default: int | float | None = ...,
    show_default: bool = ...,
    min: int | float | None = ...,
    max: int | float | None = ...,
    show_range: bool = ...,
    **kwargs: Any,
) -> int:
    ...


@overload
def _number_prompt(
    prompt_type: Type[FloatPrompt],
    prompt: str,
    default: int | float | None = ...,
    show_default: bool = ...,
    min: int | float | None = ...,
    max: int | float | None = ...,
    show_range: bool = ...,
    **kwargs: Any,
) -> float:
    ...


def _number_prompt(
    prompt_type: Type[IntPrompt] | Type[FloatPrompt],
    prompt: str,
    default: int | float | None = None,
    show_default: bool = True,
    min: int | float | None = None,
    max: int | float | None = None,
    show_range: bool = True,
    **kwargs: Any,
) -> int | float:
    default_arg = ... if default is None else default

    _prompt_add = ""
    if show_range:
        if min is not None and max is not None:
            if min > max:
                raise ValueError("min must be less than or equal to max")
            _prompt_add = f"{min}<=x<={max}"
        elif min is not None:
            _prompt_add = f"x>={min}"
        elif max is not None:
            _prompt_add = f"x<={max}"
        if _prompt_add:
            _prompt_add = yellow(_prompt_add)
    msg = prompt_msg(prompt, _prompt_add)

    while True:
        val = prompt_type.ask(
            msg,
            console=console,
            default=default_arg,
            show_default=show_default,
            **kwargs,
        )

        # Shouldn't happen, but ask() returns DefaultType | int | float
        # so it thinks we could have an ellipsis here
        if not isinstance(val, (int, float)):
            error("Value must be a number")
            continue
        if math.isnan(val):
            error("Value can't be NaN")
            continue
        if min is not None and val < min:
            error(f"Value must be greater or equal to {min}")
            continue
        if max is not None and val > max:
            error(f"Value must be less than or equal to {max}")
            continue
        return val


@no_headless
def bool_prompt(
    prompt: str,
    default: Any = ...,
    show_default: bool = True,
    warning: bool = False,
    **kwargs: Any,
) -> bool:
    return Confirm.ask(
        prompt_msg(prompt),
        console=console,
        show_default=show_default,
        default=default,
        **kwargs,
    )


@no_headless
def path_prompt(
    prompt: str,
    default: Any = ...,
    show_default: bool = True,
    exist_ok: bool = True,
    must_exist: bool = False,
    **kwargs: Any,
) -> Path:
    if isinstance(default, Path):
        default_arg = str(default)
    elif default is None:
        default_arg = ...  # type: ignore
    else:
        default_arg = default

    while True:
        path_str = str_prompt(
            prompt,
            default=default_arg,
            show_default=show_default,
            **kwargs,
        )
        path = Path(path_str)

        if must_exist and not path.exists():
            error(f"Path does not exist: {path_link(path)}")
        elif not exist_ok and path.exists():
            error(f"Path already exists: {path_link(path)}")
        else:
            return path


@no_headless
def delete_prompt(
    force: bool,
    dry_run: bool = False,
    resource: str | None = None,
    name: str | None = None,
) -> None:
    """Prompt user to confirm deletion of a resource."""
    if dry_run:
        return
    if force:
        return
    config = get_state().config
    if config.general.confirm_deletion:
        resource = resource or "resource(s)"
        name = f" {name!r}" if name else ""
        message = f"Are you sure you want to delete the {resource}{name}?"
        if not bool_prompt(message, default=False):
            exit_ok("Deletion aborted.")
    return
