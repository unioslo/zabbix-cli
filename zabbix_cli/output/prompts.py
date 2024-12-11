from __future__ import annotations

import logging
import math
import os
from functools import lru_cache
from functools import wraps
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Optional
from typing import overload

from rich.prompt import Confirm
from rich.prompt import FloatPrompt
from rich.prompt import IntPrompt
from rich.prompt import Prompt
from typing_extensions import ParamSpec
from typing_extensions import TypeVar

from zabbix_cli.exceptions import ZabbixCLIError

from .console import err_console
from .console import error
from .console import exit_err
from .formatting.path import path_link
from .style import Color
from .style import Icon
from .style import green

T = TypeVar("T")
P = ParamSpec("P")


def no_headless(f: Callable[P, T]) -> Callable[P, T]:
    """Decorator that causes application to exit if called from a headless environment."""

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        if is_headless():
            # If a default argument was passed in, we can return that:
            default = kwargs.get("default")
            if "default" in kwargs and default is not ...:
                logging.debug(
                    "Returning default value from %s(%s, %s)", f, args, kwargs
                )
                return default  # type: ignore # bit of a hack
            # Assume first arg is the prompt:
            prompt = args[0] if args else kwargs.get("prompt", "")
            exit_err(
                f"Cannot proceed! User input required for {prompt!r}. Exiting...",
                args=args,
                kwargs=kwargs,
            )
        return f(*args, **kwargs)

    return wrapper


HEADLESS_VARS_SET = ["CI", "ZABBIX_CLI_HEADLESS"]
"""Envvars that indicate headless environ when set (1, true)."""
HEADLESS_VARS_SET_MAP = {"DEBIAN_FRONTEND": "noninteractive"}
"""Envvars that indicate headless environ when set to a specific value."""

TRUE_ARGS = ["1", "true"]  # case-insensitive


# NOTE: if testing this function, clear cache after each test
@lru_cache(maxsize=None)
def is_headless() -> bool:
    """Determines if we are running in a headless environment (e.g. CI, Docker, etc.)"""
    # Truthy values indicate headless
    for envvar in HEADLESS_VARS_SET:
        if os.environ.get(envvar, "").lower() in ["1", "true"]:
            return True
    # Specific values indicate headless
    for envvar, value in HEADLESS_VARS_SET_MAP.items():
        if os.environ.get(envvar, None) == value:
            return True
    return False


def prompt_msg(*msgs: str) -> str:
    return f"[bold]{green(Icon.PROMPT)} {' '.join(msg.strip() for msg in filter(None, msgs))}[/bold]"


@no_headless
def str_prompt(
    prompt: str,
    default: str = ...,  # pyright: ignore[reportArgumentType] # rich uses ... to signify no default
    password: bool = False,
    show_default: bool = True,
    choices: Optional[list[str]] = None,
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
    # Don't permit secrets to be shown ever + no empty defaults shown
    if password or default is ... or not default:  # pyright: ignore[reportUnnecessaryComparison]
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
            console=err_console,
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
def str_prompt_optional(
    prompt: str,
    default: str = "",
    password: bool = False,
    show_default: bool = False,
    choices: Optional[list[str]] = None,
    strip: bool = True,
    **kwargs: Any,
) -> str:
    prompt = f"{prompt} [i](optional)[/]"
    return str_prompt(
        prompt,
        default=default,
        password=password,
        show_default=show_default,
        choices=choices,
        empty_ok=True,
        strip=strip,
        **kwargs,
    )


TypeConstructor = Callable[[object], T]


@no_headless
def list_prompt(
    prompt: str,
    empty_ok: bool = True,
    strip: bool = True,
    keep_empty: bool = False,
    # https://github.com/python/mypy/issues/3737
    # https://github.com/python/mypy/issues/3737#issuecomment-1446769973
    # Using this weird TypeConstructor type seems very hacky
    type: TypeConstructor[T] = str,
) -> list[T]:
    """Prompt user for a comma-separated list of values."""
    from zabbix_cli.utils.args import parse_list_arg

    inp = str_prompt(prompt, empty_ok=empty_ok, strip=strip)
    arglist = parse_list_arg(inp, keep_empty=keep_empty)
    try:
        # NOTE: type() in this context is the constructor for the type
        # we passed in, not the built-in type() function (shadowed in this scope)
        return [type(arg) for arg in arglist]
    except Exception as e:
        raise ZabbixCLIError(f"Invalid value: {e}") from e


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
    prompt_type: type[IntPrompt],
    prompt: str,
    default: int | float | None = ...,
    show_default: bool = ...,
    min: int | float | None = ...,
    max: int | float | None = ...,
    show_range: bool = ...,
    **kwargs: Any,
) -> int: ...


@overload
def _number_prompt(
    prompt_type: type[FloatPrompt],
    prompt: str,
    default: int | float | None = ...,
    show_default: bool = ...,
    min: int | float | None = ...,
    max: int | float | None = ...,
    show_range: bool = ...,
    **kwargs: Any,
) -> float: ...


def _number_prompt(
    prompt_type: type[IntPrompt] | type[FloatPrompt],
    prompt: str,
    default: int | float | None = None,
    show_default: bool = True,
    min: int | float | None = None,
    max: int | float | None = None,
    show_range: bool = True,
    **kwargs: Any,
) -> int | float:
    # NOTE: pyright really doesn't like Ellipsis as default!
    default_arg = (  # pyright: ignore[reportUnknownVariableType]
        ... if default is None else default
    )

    IntPrompt.ask()

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
            _prompt_add = Color.YELLOW(_prompt_add)
    msg = prompt_msg(prompt, _prompt_add)

    while True:
        val = prompt_type.ask(  # pyright: ignore[reportUnknownVariableType]
            msg,
            console=err_console,
            default=default_arg,  # pyright: ignore[reportUnknownArgumentType]
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
    default: bool = ...,  # pyright: ignore[reportArgumentType] # rich uses ... to signify no default
    show_default: bool = True,
    warning: bool = False,
    **kwargs: Any,
) -> bool:
    return Confirm.ask(
        prompt_msg(prompt),
        console=err_console,
        show_default=show_default,
        default=default,
        **kwargs,
    )


@no_headless
def path_prompt(
    prompt: str,
    default: str | Path = ...,  # pyright: ignore[reportArgumentType] # rich uses ... to signify no default
    show_default: bool = True,
    exist_ok: bool = True,
    must_exist: bool = False,
    **kwargs: Any,
) -> Path:
    if isinstance(default, Path):
        default_arg = str(default)
    else:
        default_arg = default

    while True:
        path_str = str_prompt(
            prompt,
            default=default_arg,  # pyright: ignore[reportUnknownVariableType]
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
