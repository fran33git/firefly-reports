"""The 1.x invocation form (no subcommand means ``report``): detection and deprecation hint."""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Collection, Sequence

SECRET_OPTIONS = ("--token",)


def find_command(
    argv: Sequence[str], value_options: Collection[str], commands: Collection[str]
) -> int | None:
    """Index of the first token that is a subcommand, skipping option values.

    ``--opt value`` consumes the next token, ``--opt=value`` consumes nothing; scanning
    stops at ``--``.
    """
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--":
            return None
        if arg.startswith("-"):
            if "=" not in arg and arg in value_options:
                i += 1  # the next token is this option's value
        elif arg in commands:
            return i
        i += 1
    return None


def rewrite_legacy(
    argv: Sequence[str],
    *,
    value_options: Collection[str],
    commands: Collection[str],
    config_year: object,
) -> tuple[list[str], bool]:
    """``(argv, False)`` for current-form invocations, ``(["report", *argv], True)`` otherwise."""
    args = list(argv)
    if find_command(args, value_options, commands) is not None:
        return args, False
    if args and all(a in ("-h", "--help", "--version") for a in args):
        return args, False
    if not args and not config_year:
        return args, False
    return ["report", *args], True


def _is_secret_option(option: str) -> bool:
    """``--token`` or any prefix of it (argparse accepts unique abbreviations such as ``--tok``)."""
    return (
        len(option) > 2
        and option.startswith("--")
        and any(secret.startswith(option) for secret in SECRET_OPTIONS)
    )


def redact(argv: Sequence[str]) -> list[str]:
    """Copy of *argv* with the values of secret options replaced by ``***``."""
    out: list[str] = []
    skip = False
    for arg in argv:
        if skip:
            out.append(MASK)
            skip = False
        elif "=" not in arg and _is_secret_option(arg):
            out.append(arg)
            skip = True
        elif "=" in arg and _is_secret_option(arg.split("=", 1)[0]):
            out.extend([arg.split("=", 1)[0], MASK])
        else:
            out.append(arg)
    return out


_USERINFO = re.compile(r"(://)[^/@\s]+@")


MASK = "***"
_CMD_SPECIAL = re.compile(r'[\s"&|<>^()%]')


def _quote(part: str, windows: bool) -> str:
    if part == MASK:  # the placeholder stays unquoted so the hint reads `--token ***`
        return part
    if not windows:
        return shlex.quote(part)
    if part and not _CMD_SPECIAL.search(part):
        return part
    return '"' + part.replace('"', '\\"') + '"'  # cmd.exe / CommandLineToArgvW convention


def command_hint(argv: Sequence[str], *, windows: bool | None = None) -> str:
    """The equivalent current-form command line for the console it was typed in.

    Secrets are masked: the value of ``--token`` (and its abbreviations) and any
    ``user:password@`` part of a URL. Quoting follows the platform (``cmd.exe`` on Windows).
    """
    windows = os.name == "nt" if windows is None else windows
    masked = [_USERINFO.sub(r"\1***@", token) for token in redact(argv)]
    return " ".join(_quote(t, windows) for t in ["firefly-reports", "report", *masked])
