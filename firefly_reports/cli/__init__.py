"""Command line interface: ``firefly-reports report | export | init | demo``.

Exit codes: 0 success; 1 error (configuration, credentials, API, ledger); 2 usage error
(argparse) or a bare invocation with nothing to do; 3 the run finished but some output
files could not be written; 130 interrupted (Ctrl-C). Errors go to stderr.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tomllib
from collections.abc import Mapping, Sequence
from typing import Any

from firefly_reports import __version__, i18n
from firefly_reports.cli._console import print_error, reconfigure_streams
from firefly_reports.cli._legacy import command_hint, rewrite_legacy
from firefly_reports.cli._options import (
    default_prompt,
    load_environment,
    make_client,
    parse_cli_date,
    resolve_credentials,
    resolve_language,
)
from firefly_reports.cli.config import load_config, unknown_keys
from firefly_reports.cli.demo import add_demo_parser, run_demo
from firefly_reports.cli.export import add_export_parser, run_export_command
from firefly_reports.cli.init import run_init
from firefly_reports.cli.report import add_report_parser, run_report
from firefly_reports.errors import FireflyReportsError

COMMANDS = ("report", "export", "init", "demo")

EPILOG = """examples:
  firefly-reports report --year 2025 --owner "Mario Rossi"
  firefly-reports export beancount --scaffold
  firefly-reports demo --out ./output

Credentials may also come from FIREFLY_URL / FIREFLY_TOKEN, a .env file or
./firefly-reports.toml. Run 'firefly-reports <command> --help' for the options of a command.
"""


def _common_options() -> argparse.ArgumentParser:
    """Global options shared by every subcommand (SUPPRESS keeps values given before it)."""
    sup = argparse.SUPPRESS
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--url", default=sup, help="Firefly III base URL")
    common.add_argument("--token", default=sup, help="Personal Access Token")
    common.add_argument("--lang", default=sup, choices=["en", "it"], help="Language of the output")
    common.add_argument(
        "--debug", action="store_const", const=True, default=sup, help="Enable debug log to file"
    )
    common.add_argument("--debug-file", default=sup, metavar="PATH", help="Log file path")
    return common


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="firefly-reports",
        description="Firefly III -> PDF + Excel reports and plain-text ledger export.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    root.add_argument("--version", action="version", version=f"firefly-reports {__version__}")
    root.add_argument("--url", default=None, help="Firefly III base URL")
    root.add_argument("--token", default=None, help="Personal Access Token")
    root.add_argument(
        "--lang", default=None, choices=["en", "it"], help="Language of the output (default: en)"
    )
    root.add_argument("--debug", action="store_true", help="Enable debug log to file")
    root.add_argument(
        "--debug-file",
        default=None,
        metavar="PATH",
        help="Log file path (default: <out>/debug_<timestamp>.log)",
    )
    # 1.x placed these before the subcommand (`--out X export beancount`): accepted, not advertised.
    for flag in ("--out", "--start", "--end"):
        root.add_argument(flag, default=None, help=argparse.SUPPRESS)
    common = _common_options()
    sub = root.add_subparsers(dest="command", metavar="<command>")
    add_report_parser(sub, common)
    add_export_parser(sub, common)
    sub.add_parser("init", parents=[common], help="Create ./firefly-reports.toml interactively")
    add_demo_parser(sub, common)
    return root


def _value_options(parser: argparse.ArgumentParser) -> frozenset[str]:
    """Option strings that take a value, derived from the parsers (never hard-coded)."""
    found: set[str] = set()
    parsers = [parser]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            parsers.extend(action.choices.values())
    for p in parsers:
        for action in p._actions:
            if action.option_strings and action.nargs != 0:
                found.update(action.option_strings)
    return frozenset(found)


def _dispatch(args: argparse.Namespace, config: Mapping[str, Any], env: Mapping[str, str]) -> int:
    if args.command == "init":
        run_init()
        return 0
    if args.command == "demo":
        return run_demo(args, config, env)
    if args.command == "export":

        def client() -> Any:
            url, token = resolve_credentials(
                args.url, args.token, config, env, prompt=default_prompt
            )
            return make_client(url, token, logging.getLogger("firefly_reports.client"))

        return run_export_command(args, client, parse_cli_date, config)
    return run_report(args, config, env)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of ``firefly-reports``; returns the process exit code."""
    reconfigure_streams()
    load_environment()
    env = os.environ
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config()
    except tomllib.TOMLDecodeError as exc:
        print(i18n.t("cli.err_config_malformed").format(error=exc), file=sys.stderr)
        return 1

    parser = build_parser()
    argv2, legacy = rewrite_legacy(
        raw,
        value_options=_value_options(parser),
        commands=COMMANDS,
        config_year=config.get("year"),
    )
    if not argv2:
        parser.print_help()
        return 2
    args = parser.parse_args(argv2)
    i18n.load(resolve_language(args, config, env))
    for key, suggestion in unknown_keys(config):
        if suggestion:
            msg = i18n.t("cli.warn_unknown_config_key_hint").format(key=key, suggestion=suggestion)
        else:
            msg = i18n.t("cli.warn_unknown_config_key").format(key=key)
        print(msg, file=sys.stderr)
    if legacy:
        print(
            i18n.t("cli.deprecated_no_subcommand").format(command=command_hint(raw)),
            file=sys.stderr,
        )
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return _dispatch(args, config, env)
    except FireflyReportsError as exc:
        print_error(exc)
        return 1
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 130
