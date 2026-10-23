"""Orchestration of the ledger export: fetch -> convert -> write (+ init/validate/scaffold)."""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from firefly_reports import i18n
from firefly_reports.i18n import t
from firefly_reports.ledger.accounts import AccountResolver
from firefly_reports.ledger.convert import build_ledger
from firefly_reports.ledger.errors import LedgerError
from firefly_reports.ledger.labels import LedgerLabels
from firefly_reports.ledger.mapfile import append_entries, holds_entries, preserves_entries
from firefly_reports.ledger.mapping import CLASSIFY_CATEGORY, LedgerConfig, parse_ledger_config
from firefly_reports.ledger.model import Ledger
from firefly_reports.ledger.scaffold import (
    category_entries,
    new_account_entries,
    render_categories_block,
    render_categories_table,
    render_new_accounts,
    render_scaffold,
    render_table,
)
from firefly_reports.ledger.validate import ValidationResult, run_bean_check
from firefly_reports.ledger.writers import (
    BeancountWriter,
    LedgerWriter,
    WriterOptions,
    atomic_write,
)

INVESTMENTS_FILE = "investments.beancount"
PRICES_FILE = "prices.beancount"
MAIN_FILE = "main.beancount"
FAVA_OPTION_DATE = "1970-01-01"

LAYOUT_YEARLY = "yearly"
LAYOUT_SINGLE = "single"
DEFAULT_MAP = "beancount_map.yaml"
LAYOUTS = (LAYOUT_YEARLY, LAYOUT_SINGLE)


class TransactionSource(Protocol):
    def get_transactions(
        self, start: date | None = None, end: date | None = None, tx_type: str | None = None
    ) -> list[dict[str, Any]]: ...

    def get_transaction_links(self, resolve_types: bool = True) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class ExportRequest:
    start: date | None
    end: date | None
    out: Path  # output directory
    config: LedgerConfig
    layout: str = LAYOUT_YEARLY
    dry_run: bool = False
    validate: bool = False
    init: bool = False
    timestamp: bool = True
    # The mapping file in use (None: there is none) and whether to export without it.
    map_path: Path | None = None
    allow_unmapped: bool = False


def build_from_splits(
    splits: list[dict[str, Any]], config: LedgerConfig, labels: LedgerLabels
) -> Ledger:
    """Convert flat Firefly splits to the neutral model (network-free entry point)."""
    return build_ledger(splits, AccountResolver(config, labels))


# ---- file layout ----------------------------------------------------------


def single_name(writer: LedgerWriter) -> str:
    return f"firefly{writer.extension}"


def accounts_name(writer: LedgerWriter) -> str:
    return f"accounts{writer.extension}"


def year_name(writer: LedgerWriter, year: int) -> str:
    return f"firefly-{year}{writer.extension}"


def plan_files(
    ledger: Ledger, layout: str, writer: LedgerWriter, options: WriterOptions
) -> dict[str, str]:
    """File name -> content for the chosen layout (pure, deterministic order)."""
    if layout == LAYOUT_SINGLE:
        return {single_name(writer): writer.render(ledger, options)}
    files = {accounts_name(writer): writer.render_accounts(ledger, options)}
    for year, year_ledger in ledger.by_year().items():
        files[year_name(writer, year)] = writer.render_transactions(year_ledger, options)
    return files


def find_orphans(out_dir: Path, produced: Collection[str], writer: LedgerWriter) -> list[str]:
    """Generator-managed files already in *out_dir* that this run did not produce."""
    ext = re.escape(writer.extension)
    managed = re.compile(rf"^(firefly(-\d{{4}})?|accounts){ext}$")
    if not out_dir.is_dir():
        return []
    return sorted(
        p.name for p in out_dir.iterdir() if managed.match(p.name) and p.name not in produced
    )


# ---- init -----------------------------------------------------------------


def render_main_beancount(
    ledger: Ledger,
    config: LedgerConfig,
    layout: str = LAYOUT_YEARLY,
    writer: LedgerWriter | None = None,
) -> str:
    """Minimal main.beancount: options plus includes of the generated/manual files."""
    writer = writer or BeancountWriter()
    operating = list(config.operating_currency)
    if not operating:
        counts = Counter(p.amount.currency for tx in ledger.transactions for p in tx.postings)
        operating = [cur for cur, _ in counts.most_common(1)]
    if layout == LAYOUT_YEARLY:
        generated = [accounts_name(writer), f"firefly-*{writer.extension}"]
    else:
        generated = [single_name(writer)]
    lines = [
        f"; {t('ledger.init_note')}",
        f'option "title" "{t("ledger.init_title")}"',
        *(f'option "operating_currency" "{cur}"' for cur in operating),
        # Beancount rejects unknown options; Fava reads its own settings from custom directives.
        f'{FAVA_OPTION_DATE} custom "fava-option" "language" "{i18n.current().lang}"',
        "",
        *(f'include "{name}"' for name in generated),
        f'include "{INVESTMENTS_FILE}"',
        f'include "{PRICES_FILE}"',
        "",
    ]
    return "\n".join(lines)


def init_ledger_files(
    out_dir: Path,
    ledger: Ledger,
    config: LedgerConfig,
    layout: str = LAYOUT_YEARLY,
    writer: LedgerWriter | None = None,
) -> list[Path]:
    """Create main.beancount (and empty manual stubs) ONLY when they do not exist."""
    created: list[Path] = []
    stubs = {
        out_dir / MAIN_FILE: render_main_beancount(ledger, config, layout, writer),
        out_dir / INVESTMENTS_FILE: f"; {t('ledger.stub_investments')}\n",
        out_dir / PRICES_FILE: f"; {t('ledger.stub_prices')}\n",
    }
    for path, content in stubs.items():
        if path.exists():
            print(t("ledger.init_exists").format(path=path))
            continue
        atomic_write(path, content)
        created.append(path)
        print(t("ledger.init_created").format(path=path))
    return created


# ---- validation -----------------------------------------------------------


def print_validation(result: ValidationResult) -> int:
    """Print a readable summary of a bean-check run; return a process exit code."""
    if not result.available:
        print(t("ledger.validate_missing"), file=sys.stderr)
        return 2
    if result.ok:
        print(t("ledger.validate_ok"), file=sys.stderr)
        return 0
    print(t("ledger.validate_fail").format(count=len(result.problems)), file=sys.stderr)
    for block in result.problems:
        print("  " + block.replace("\n", "\n  "), file=sys.stderr)
    return 1


def _validate(base: Path, names: list[str], layout: str, writer: LedgerWriter) -> int:
    """bean-check the generated files in *base* (the yearly layout through an aggregator)."""
    if layout == LAYOUT_SINGLE:
        return print_validation(run_bean_check(base / single_name(writer)))
    with tempfile.TemporaryDirectory() as tmp:
        aggregator = Path(tmp) / f"check{writer.extension}"
        aggregator.write_text(
            "".join(f'include "{(base / name).resolve().as_posix()}"\n' for name in sorted(names)),
            encoding="utf-8",
        )
        return print_validation(run_bean_check(aggregator))


# ---- export ---------------------------------------------------------------


def _check_categories(request: ExportRequest, resolver: AccountResolver) -> None:
    """Stop on categories the mapping does not list, unless ``allow_unmapped``; warn on stale keys."""
    if resolver.classify_by != CLASSIFY_CATEGORY:
        return
    unmapped = resolver.unmapped_categories()
    if unmapped and not request.allow_unmapped:
        details = "\n".join(f"  {u.lane}: {u.name!r} ({u.splits} splits)" for u in unmapped)
        raise LedgerError("ledger.err_unmapped_categories", details=details)
    for use in unmapped:
        print(
            t("ledger.warn_unmapped_category").format(
                lane=use.lane, name=use.name, account=use.account
            ),
            file=sys.stderr,
        )
    for lane, key in resolver.unused_category_keys():
        print(t("ledger.warn_unused_category_key").format(lane=lane, name=key), file=sys.stderr)


def run_export(
    client: TransactionSource,
    request: ExportRequest,
    labels: LedgerLabels,
    writer: LedgerWriter | None = None,
    now: Callable[[], datetime] = datetime.now,
) -> int:
    """Run the full export; returns the process exit code."""
    writer = writer or BeancountWriter()
    if request.layout == LAYOUT_YEARLY and (request.start or request.end):
        raise LedgerError("ledger.err_yearly_filters")

    if request.map_path is None and not request.allow_unmapped:
        raise LedgerError("ledger.err_map_missing", path=DEFAULT_MAP)

    splits = client.get_transactions(request.start, request.end, tx_type="all")
    links = client.get_transaction_links(resolve_types=False)
    resolver = AccountResolver(request.config, labels)
    ledger = build_ledger(splits, resolver, links=links)
    _check_categories(request, resolver)
    if ledger.skipped_links:
        print(t("ledger.warn_links_skipped").format(count=ledger.skipped_links), file=sys.stderr)
    if not ledger.transactions:
        # Never touch existing files with an empty result: accounts.beancount
        # would become header-only and orphan years would fail bean-check.
        print(t("ledger.no_transactions"), file=sys.stderr)
        return 1
    for name, firefly_type, account in resolver.warnings():
        print(
            t("ledger.warn_mapping_root").format(name=name, type=firefly_type, account=account),
            file=sys.stderr,
        )

    options = WriterOptions(
        labels=labels,
        commodities=request.config.commodities,
        generated_at=now().astimezone() if request.timestamp else None,
    )
    # Everything is rendered before anything is written: an error leaves no partial output.
    files = plan_files(ledger, request.layout, writer, options)

    if request.dry_run:
        multi = len(files) > 1
        for name, content in files.items():
            if multi:
                sys.stdout.write(f"; ===== {name} =====\n")
            sys.stdout.write(content)
            if multi:
                sys.stdout.write("\n")
        if not request.validate:
            return 0
        with tempfile.TemporaryDirectory() as tmp:
            for name, content in files.items():
                (Path(tmp) / name).write_text(content, encoding="utf-8")
            return _validate(Path(tmp), list(files), request.layout, writer)

    for name, content in files.items():
        path = request.out / name
        try:
            if path.is_file() and path.read_text(encoding="utf-8") == content:
                continue
            atomic_write(path, content)
        except (OSError, UnicodeDecodeError) as exc:
            raise LedgerError("ledger.err_write", path=path, reason=exc) from exc
    print(
        t("ledger.wrote_files").format(
            count=len(ledger.transactions), files=len(files), path=request.out
        )
    )
    orphans = find_orphans(request.out, files, writer)
    if orphans:
        print(t("ledger.warn_orphan_files").format(files=", ".join(orphans)), file=sys.stderr)
    if request.init:
        init_ledger_files(request.out, ledger, request.config, request.layout, writer)

    if not request.validate:
        return 0
    return _validate(request.out, list(files), request.layout, writer)


# ---- scaffold -------------------------------------------------------------


SCAFFOLD_PRINT = "print"
SCAFFOLD_APPEND = "append"
SCAFFOLD_OVERWRITE = "overwrite"


def _read_mapping_text(path: Path) -> str:
    """The file as text, keeping its line endings (``read_text`` would translate CRLF)."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LedgerError("ledger.err_config_read", path=path, reason=exc) from exc


def _backup(path: Path, suffix: str, *, unique: bool) -> Path:
    """Copy *path* next to itself; with *unique* an earlier copy is never overwritten."""
    target = path.with_name(path.name + suffix)
    n = 1
    while unique and target.exists():
        n += 1
        target = path.with_name(f"{path.name}{suffix}-{n}")
    try:
        shutil.copy2(path, target)
    except OSError as exc:
        raise LedgerError("ledger.err_backup", path=path, reason=exc) from exc
    return target


def _write_mapping(path: Path, content: str) -> None:
    try:
        atomic_write(path, content)
    except OSError as exc:
        raise LedgerError("ledger.err_write", path=path, reason=exc) from exc


def _valid_mapping(text: str) -> bool:
    try:
        parse_ledger_config(yaml.safe_load(text))
    except (yaml.YAMLError, LedgerError):
        return False
    return True


def _try_append(
    map_path: Path,
    request: ExportRequest,
    accounts: list[str],
    entries: dict[str, list[str]],
) -> bool:
    """Add the new entries to the mapping file; False when nothing was written."""
    text = _read_mapping_text(map_path)
    new_text = append_entries(
        text, accounts=accounts, expense=entries["expense"], income=entries["income"]
    )
    if (
        new_text is None
        or not _valid_mapping(new_text)
        or not preserves_entries(text, new_text)
        or not holds_entries(
            new_text, accounts=accounts, expense=entries["expense"], income=entries["income"]
        )
    ):
        print(t("ledger.append_unsafe").format(path=map_path), file=sys.stderr)
        return False
    if request.dry_run:
        print(t("ledger.append_dry_run").format(path=map_path), file=sys.stderr)
        return False
    _backup(map_path, ".bak", unique=False)
    _write_mapping(map_path, new_text)
    count = len(accounts) + sum(len(v) for v in entries.values())
    print(t("ledger.append_done").format(path=map_path, count=count))
    return True


def run_scaffold(
    client: TransactionSource,
    request: ExportRequest,
    labels: LedgerLabels,
    map_path: Path,
    *,
    mode: str = SCAFFOLD_PRINT,
    confirm: Callable[[Path], bool] | None = None,
) -> int:
    """First pass: propose a mapping file from the accounts and categories found in Firefly.

    No ledger file is written. A missing mapping file is created. An existing one is left
    alone and the entries it lacks are printed, unless the caller asks for ``append``
    (add them in place, after a ``.bak`` copy) or ``overwrite`` (regenerate it from scratch
    after *confirm* approves, keeping a timestamped copy).
    """
    splits = client.get_transactions(request.start, request.end, tx_type="all")
    resolver = AccountResolver(request.config, labels)
    ledger = build_ledger(splits, resolver, check_collisions=False)
    resolutions = resolver.resolutions()
    collisions = resolver.collisions()

    by_category = resolver.classify_by == CLASSIFY_CATEGORY
    uses = resolver.category_uses() if by_category else []

    print(render_table(resolutions, collisions), end="", file=sys.stderr)
    if collisions:
        print(t("ledger.scaffold_collisions_found").format(count=len(collisions)), file=sys.stderr)
    if uses:
        print(render_categories_table(uses), end="", file=sys.stderr)

    def new_file_content() -> str:
        counts = Counter(p.amount.currency for tx in ledger.transactions for p in tx.postings)
        return render_scaffold(
            resolutions,
            collisions,
            operating=[cur for cur, _ in counts.most_common(1)]
            or list(request.config.operating_currency),
            commodities=sorted(counts),
            fallback_expense=request.config.fallback_expense or labels.fallback_expense,
            fallback_income=request.config.fallback_income or labels.fallback_income,
            investment_root=request.config.investment_root or labels.investment_root,
            classify_by=resolver.classify_by,
            categories=uses,
        )

    if not map_path.is_file():
        content = new_file_content()
        if request.dry_run:
            sys.stdout.write(content)
            return 0
        _write_mapping(map_path, content)
        print(t("ledger.scaffold_created").format(path=map_path))
        return 0

    if mode == SCAFFOLD_OVERWRITE:
        content = new_file_content()
        if request.dry_run:
            print(t("ledger.overwrite_dry_run").format(path=map_path), file=sys.stderr)
            sys.stdout.write(content)
            return 0
        if confirm is None or not confirm(map_path):
            print(t("ledger.overwrite_aborted").format(path=map_path), file=sys.stderr)
            return 1
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = _backup(map_path, f".bak-{stamp}", unique=True)
        _write_mapping(map_path, content)
        print(t("ledger.overwrite_done").format(path=map_path, backup=backup))
        return 0

    print(t("ledger.scaffold_exists").format(path=map_path), file=sys.stderr)
    mapped = {
        "expense": set(request.config.categories_expense),
        "income": set(request.config.categories_income),
    }
    account_entries = new_account_entries(resolutions, collisions, set(request.config.accounts))
    category_lines = category_entries(uses, skip=mapped)
    nothing_new = not (account_entries or any(category_lines.values()))
    if nothing_new:
        print(t("ledger.scaffold_new_none").format(path=map_path), file=sys.stderr)
        return 0
    if mode == SCAFFOLD_APPEND and _try_append(map_path, request, account_entries, category_lines):
        return 0

    accounts_snippet = render_new_accounts(resolutions, collisions, set(request.config.accounts))
    categories_snippet = render_categories_block(
        uses, skip=mapped, header=not (mapped["expense"] or mapped["income"])
    )
    if accounts_snippet:
        print(t("ledger.scaffold_new_header").format(path=map_path), file=sys.stderr)
        sys.stdout.write(accounts_snippet)
    if categories_snippet:
        print(t("ledger.scaffold_new_categories_header").format(path=map_path), file=sys.stderr)
        sys.stdout.write(categories_snippet)
    return 0
