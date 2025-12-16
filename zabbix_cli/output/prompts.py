from __future__ import annotations

import logging
import math
import os
from functools import cache
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


logger = logging.getLogger(__name__)


def no_headless(f: Callable[P, T]) -> Callable[P, T]:
    """Decorator that causes application to exit if called from a headless environment
    when the prompt does not have a default value (i.e. required input).

    If the prompt has a default value, that value is returned instead."""

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        if is_headless():
            # If a default argument was passed in, we can return that:
            default = kwargs.get("default")
            if "default" in kwargs and default is not ...:
                logger.debug("Returning default value from %s(%s, %s)", f, args, kwargs)
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
@cache
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

    import shellingham  # pyright: ignore[reportMissingTypeStubs]

    try:
        shellingham.detect_shell()  # pyright: ignore[reportUnknownMemberType]
    except shellingham.ShellDetectionFailure:
        # If we can't detect the shell, assume we're in a headless environment
        return True

    return False


def prompt_msg(*msgs: str) -> str:
    return f"[bold]{green(Icon.PROMPT)} {' '.join(msg.strip() for msg in filter(None, msgs))}[/bold]"


@no_headless
def str_prompt(
    prompt: str,
    *,
    default: str | None = None,  # pyright: ignore[reportArgumentType] # rich uses ... to signify no default
    password: bool = False,
    choices: Optional[list[str]] = None,
    show_default: bool = True,
    show_choices: bool = True,
    empty_ok: bool = False,
    strip: bool = True,
) -> str:
    """Prompts the user for a string input.

    Optionally controls for empty input. Loops until a valid input is provided.

    Args:
        prompt (str): String prompt to display to the user.
        default (Any, optional): Default value to use if the user does not provide input.
            If not provided, the user will be required to provide input.
        password (bool, optional): Whether to hide the input. Defaults to False.
        choices (list[str], optional): List of valid choices. If provided, the user
            must select one of the choices. Defaults to None.
        show_default (bool, optional): Show the default value. Defaults to True.
            If `password=True`, this option is overridden and set to False.
        show_choices (bool, optional): Show the choices in the prompt. Defaults to True.
        empty_ok (bool, optional): Allow input consisting of no characters or only whitespace.
            Defaults to False.
        strip (bool, optional): Strip whitespace from the input. Defaults to True.
            Must be `False` to preserve whitespace when `empty_ok=True`.

    Returns:
        str: The user input as a string. If `strip=True`, leading and trailing whitespace
            will be removed from the input.
    """

    prompt_parts = [prompt]

    # Never show password default or empty default
    if password or not default:
        show_default = False

    # Add notice for hidden password default
    if password and default:
        prompt_parts.append("(leave empty to use existing value)")

    msg = prompt_msg(*prompt_parts)

    # Rich uses `...` to signify no default, which is clunky when wrapping
    # Prompt.ask, since it doesn't have an overload for explicitly passing
    # in `...`. To work around that, we don't pass in the default kwarg
    # if it's None.
    kwargs: dict[str, Any] = {}
    if default is not None:
        kwargs["default"] = default

    while not (
        inp := Prompt.ask(
            msg,
            console=err_console,
            password=password,
            show_default=show_default,
            show_choices=show_choices,
            choices=choices,
            **kwargs,
        )
    ):
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
    *,
    default: str = "",
    password: bool = False,
    show_default: bool = False,
    choices: Optional[list[str]] = None,
    strip: bool = True,
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
    )


TypeConstructor = Callable[[object], T]


@no_headless
def list_prompt(
    prompt: str,
    *,
    default: list[T] | None = None,
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

    default_arg = ",".join(str(d) for d in default) if default else None

    inp = str_prompt(
        prompt,
        default=default_arg,
        empty_ok=empty_ok,
        strip=strip,
    )
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
    *,
    default: int | None = None,
    show_default: bool = True,
    min: int | None = None,
    max: int | None = None,
    show_range: bool = True,
    **kwargs: Any,
) -> int:
    """Prompt user for an integer input. Loops until a valid input is provided.

    Args:
        prompt (str): String prompt to display to the user.
        default (int, optional): Default value to use if the user does not provide input.
            If not provided, the user will be required to provide input.
        show_default (bool, optional): Show the default value. Defaults to True.
        min (int, optional): Minimum value. Defaults to None.
        max (int, optional): Maximum value. Defaults to None.
        show_range (bool, optional): Show the range in the prompt. Defaults to True.
        **kwargs: Additional keyword arguments to pass to the prompt.

    Returns:
        int: The user input as an integer.
    """
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
    *,
    default: float | None = None,
    show_default: bool = True,
    min: float | None = None,
    max: float | None = None,
    show_range: bool = True,
    **kwargs: Any,
) -> float:
    """Prompt user for a float input. Loops until a valid input is provided.

    Args:
        prompt (str): String prompt to display to the user.
        default (float, optional): Default value to use if the user does not provide input.
            If not provided, the user will be required to provide input.
        show_default (bool, optional): Show the default value. Defaults to True.
        min (float, optional): Minimum value. Defaults to None.
        max (float, optional): Maximum value. Defaults to None.
        show_range (bool, optional): Show the range in the prompt. Defaults to True.
        **kwargs: Additional keyword arguments to pass to the prompt.

    Returns:
        float: The user input as a float.
    """
    val = _number_prompt(
        FloatPrompt,
        prompt,
        default=default,
        show_default=show_default,
        min=min,
        max=max,
        show_range=show_range,
    )
    # explicit cast to float since users might pass in int as default
    # and we have no logic inside _number_prompt to handle that
    return float(val)


@overload
def _number_prompt(
    prompt_type: type[IntPrompt],
    prompt: str,
    *,
    default: int | float | None = ...,
    show_default: bool = ...,
    min: int | float | None = ...,
    max: int | float | None = ...,
    show_range: bool = ...,
) -> int: ...


@overload
def _number_prompt(
    prompt_type: type[FloatPrompt],
    prompt: str,
    *,
    default: int | float | None = ...,
    show_default: bool = ...,
    min: int | float | None = ...,
    max: int | float | None = ...,
    show_range: bool = ...,
) -> float: ...


def _number_prompt(
    prompt_type: type[IntPrompt] | type[FloatPrompt],
    prompt: str,
    *,
    default: int | float | None = None,
    show_default: bool = True,
    min: int | float | None = None,
    max: int | float | None = None,
    show_range: bool = True,
) -> int | float:
    prompt_parts = [prompt]
    if show_range:
        input_range_str = ""
        if min is not None and max is not None:
            if min > max:
                raise ValueError("min must be less than or equal to max")
            input_range_str = f"{min}<=x<={max}"
        elif min is not None:
            input_range_str = f"x>={min}"
        elif max is not None:
            input_range_str = f"x<={max}"
        if input_range_str:
            prompt_parts.append(Color.YELLOW(input_range_str))

    msg = prompt_msg(*prompt_parts)

    # See str_prompt() for why we use pass default as part of the kwargs mapping
    kwargs: dict[str, Any] = {}
    if default is not None:
        kwargs["default"] = default

    while True:
        val = prompt_type.ask(  # pyright: ignore[reportUnknownVariableType]
            msg,
            console=err_console,
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
    *,
    default: bool | None = None,
    show_default: bool = True,
) -> bool:
    """Prompt user for a boolean input (y/n). Loops until a valid input is provided.

    Args:
        prompt (str): String prompt to display to the user.
        default (bool, optional): Default value to use if the user does not provide input.
            If not provided, the user will be required to provide input.
        show_default (bool, optional): Show the default value. Defaults to True.
        warning (bool, optional): Show a warning message if the user selects "no". Defaults to False.
        **kwargs: Additional keyword arguments to pass to the prompt.
    Returns:
        bool: The user input as a boolean.
    """
    kwargs: dict[str, Any] = {}
    if default is not None:
        kwargs["default"] = default

    return Confirm.ask(
        prompt_msg(prompt),
        console=err_console,
        show_default=show_default,
        **kwargs,
    )


@no_headless
def path_prompt(
    prompt: str,
    default: str | Path | None = None,
    *,
    show_default: bool = True,
    exist_ok: bool = True,
    must_exist: bool = False,
) -> Path:
    """Prompt user for a path.

    Optionally checks if the path exists OR if it does _not_ exist.

    Args:
        prompt (str): String prompt to display to the user.
        default (str | Path, optional): Default value to use if the user does not provide input.
            If not provided, the user will be required to provide input.
        show_default (bool, optional): Show the default value. Defaults to True.
        exist_ok (bool, optional): Allow existing paths. Defaults to True.
        must_exist (bool, optional): Require existing paths. Defaults to False.

    Returns:
        The user input as a Path object.
    """
    if isinstance(default, Path):
        default_arg = str(default)
    else:
        default_arg = default

    while True:
        path_str = str_prompt(
            prompt,
            default=default_arg,
            show_default=show_default,
        )
        path = Path(path_str)

        if must_exist and not path.exists():
            error(f"Path does not exist: {path_link(path)}")
        elif not exist_ok and path.exists():
            error(f"Path already exists: {path_link(path)}")
        else:
            return path
