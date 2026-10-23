"""The 1.x invocation form (no subcommand means ``report``): detection and deprecation hint."""

from __future__ import annotations

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


def redact(argv: Sequence[str]) -> list[str]:
    """Copy of *argv* with the values of secret options replaced by ``***``."""
    out: list[str] = []
    skip = False
    for token in argv:
        if skip:
            out.append("***")
            skip = False
        elif token in SECRET_OPTIONS:
            out.append(token)
            skip = True
        elif any(token.startswith(f"{opt}=") for opt in SECRET_OPTIONS):
            out.extend([token.split("=", 1)[0], "***"])
        else:
            out.append(token)
    return out


def command_hint(argv: Sequence[str]) -> str:
    """The equivalent current-form command line, secrets redacted."""
    tokens = ["firefly-reports", "report", *redact(argv)]
    # the placeholder stays unquoted so the hint reads `--token ***`
    return " ".join(t if t == "***" else shlex.quote(t) for t in tokens)
