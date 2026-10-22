# Ledger Architecture (developer guide)

How the plain-text-accounting export (`firefly_reports/ledger/`) is built, which guarantees it gives, and how
to add a new output format such as hledger. User documentation: [[Beancount-Export|Beancount Export]].

## Goals and non-goals

* Reuse the existing client, credentials and i18n; add no network code outside `firefly_client.py`.
* Separate **fetch -> neutral model -> writer** so a new format is a new writer only.
* Money is `Decimal` end to end; mapping and normalisation are testable without the network.
* Deterministic output and atomic writes.
* Non-goal: generating investment positions (the data does not exist in Firefly III).

## Data flow

```mermaid
flowchart TD
    CLIIN["main.py / ledger/cli.py<br/>arguments, mapping, labels"] --> RUN["export.run_export()"]
    RUN --> GT["FireflyClient.get_transactions(start?, end?)<br/>flat per-split dicts"]
    GT --> BL["convert.build_ledger(splits, AccountResolver)<br/>pure; ConversionError, AccountCollisionError"]
    BL --> LG["model.Ledger<br/>frozen dataclasses, format-neutral"]
    LG --> PF["export.plan_files(ledger, layout, writer, options)<br/>file name -> content (pure)"]
    PF --> WR["LedgerWriter.render / render_accounts / render_transactions"]
    PF --> AW["writers.base.atomic_write(path)<br/>only when the content changed"]
    AW -.-> VB["validate.run_bean_check(path)"]
    AW -.-> IN["export.init_ledger_files()"]
    GT -.-> SC["export.run_scaffold()<br/>resolver.resolutions() -> scaffold.render_scaffold()"]
```

The scaffold (`--scaffold`) shares the fetch and the conversion but stops before the writers: it builds the
ledger with `check_collisions=False` so that clashes are reported in the YAML instead of aborting.

`export.run_export()` wires these steps; `ledger/cli.run_export_command()` loads the mapping and labels and
turns exceptions into exit codes; `main.cmd_export()` is a thin adapter that supplies credentials and the client.

## Module map

```mermaid
flowchart LR
    main["main.py"] --> cli["ledger/cli.py"]
    cli --> export["ledger/export.py"]
    cli --> mapping["ledger/mapping.py"]
    cli --> labels["ledger/labels.py"]
    cli --> errors["ledger/errors.py"]
    export --> convert["ledger/convert.py"]
    export --> writers["ledger/writers/"]
    export --> validate["ledger/validate.py"]
    convert --> accounts["ledger/accounts.py"]
    convert --> model["ledger/model.py"]
    accounts --> mapping
    accounts --> labels
    writers --> model
    writers --> labels
    labels --> i18n["i18n.py"]
    errors --> i18n
    mapping --> yaml(["PyYAML"])
    main --> client["firefly_client.py"]
```


| Module | Responsibility | Depends on |
|---|---|---|
| `ledger/model.py` | `Amount`, `Posting`, `LedgerTransaction`, `Ledger`; balance and first-use helpers | stdlib |
| `ledger/errors.py` | `LedgerError(message_key, **params)` and subclasses; message rendered lazily via `i18n.t` | `i18n` |
| `ledger/labels.py` | `LedgerLabels`: translatable strings + validation of metadata keys | `i18n`, `errors` |
| `ledger/mapping.py` | `LedgerConfig`, `parse_ledger_config()`, `load_ledger_config()` (PyYAML) | `errors`, `labels` |
| `ledger/accounts.py` | `normalize_component()`, `classify()`, `AccountResolver` (precedence, collisions) | `config`, `labels`, `errors` |
| `ledger/convert.py` | Firefly split -> `LedgerTransaction`; grouping, foreign amounts, merging, balance check | `accounts`, `model`, `errors` |
| `ledger/writers/base.py` | `LedgerWriter` protocol, `WriterOptions`, `atomic_write()` | `labels`, `model` |
| `ledger/writers/beancount.py` | `BeancountWriter`, `quote()`, `format_number()` | `writers.base`, `model` |
| `ledger/validate.py` | optional `bean-check` runner (`shutil.which` + `subprocess`, argv list, no shell) | stdlib |
| `ledger/cli.py` | `add_export_parser()` (argparse `export <format>`) and `run_export_command()` (mapping lookup, labels, exit codes); credentials/client and date parsing are injected by `main.py` | `export`, `mapping`, `labels`, `errors` |
| `ledger/scaffold.py` | `render_scaffold()`, `render_new_accounts()`, `render_table()`: draft of `beancount_map.yaml` from `Resolution` records (pure, templated text so comments survive) | `accounts`, `i18n` |
| `ledger/export.py` | `ExportRequest`, `plan_files()` (layouts), `run_export()`, `run_scaffold()`, `--init` file creation, orphan detection, validation | all of the above |

Rules: `model`, `convert`, `accounts` and the writers do no I/O (only `atomic_write`, `validate`, `config.load_*`
and `export` touch the disk or processes); writers never call `i18n`, they receive a `LedgerLabels`.

## The neutral model

```mermaid
classDiagram
    class Ledger {
        +transactions
        +accounts_first_use()
        +currencies_first_use()
    }
    class LedgerTransaction {
        +date
        +reconciled
        +narration
        +payee
        +tags
        +firefly_id
        +firefly_group_id
        +category
        +budget
        +note
        +sort_key
        +balance()
    }
    class Posting {
        +account
        +amount
        +price_total
        +category
        +budget
        +note
        +weight
    }
    class Amount {
        +number : Decimal
        +currency : str
    }
    Ledger "1" o-- "*" LedgerTransaction
    LedgerTransaction "1" o-- "2..*" Posting
    Posting --> Amount : amount
    Posting --> Amount : price_total
```


* `Amount(number: Decimal, currency: str)`.
* `Posting(account, amount, price_total=None, category=None, budget=None, note=None)`. `price_total` is a
  *total* price (Beancount `@@`). `Posting.weight` is the amount that counts for balancing: the price total
  (signed like the units) when present, otherwise the amount.
* `LedgerTransaction(date, reconciled, narration, postings, firefly_id, firefly_group_id, payee, tags,
  category, budget, note)`. `sort_key` is `(date, numeric id, id string)`. `balance()` returns the residual
  per currency (all zeros for a valid transaction).
* `Ledger(transactions)` with `accounts_first_use()` and `currencies_first_use()` (both sorted).

The model carries semantics (`reconciled`, `category`) not syntax (`*`, `categoria:`): flag characters, metadata
key names and quoting belong to the writer and its labels.

## Conversion algorithm (`convert.py`)

```mermaid
flowchart TD
    A["Flat splits"] --> B["Group by group_id<br/>order by journal id"]
    B --> C["Per split: source minus, destination plus<br/>strict Decimal parsing"]
    C --> D{"foreign amount?"}
    D -- yes --> E["Counterpart in foreign currency<br/>with total price @@"]
    D -- no --> F
    E --> F["Hoist category, budget, note<br/>when all splits agree"]
    F --> G["Merge plain postings<br/>same account and currency"]
    G --> H{"Balances per currency?"}
    H -- no --> X["ConversionError"]
    H -- yes --> I["LedgerTransaction"]
    I --> J["After all groups:<br/>collision check"]
    J --> K["Sort by date, then numeric id"]
```


1. **Group** flat splits by `group_id` (fallback: journal id). Splits are ordered by numeric journal id.
2. **Pair postings** for each split (`_split_postings`): source `-amount`, destination `+amount`, both in
   `currency_code`. Amounts go through a strict `Decimal(str(x))` parser; `NaN`, `Infinity`, empty or invalid
   values raise `ConversionError` (no silent zero). `_negate` avoids `-0.00`.
3. **Foreign amount**: if `foreign_currency_code` differs from the base currency and `foreign_amount` is
   non-zero, the counterpart posting is expressed in the foreign currency with
   `price_total = |amount| in base currency`. Counterpart = source for `deposit`, destination otherwise.
4. **Uniform metadata**: for category, budget and note, if every split agrees the value is hoisted to the
   transaction and removed from the postings; otherwise it stays on each destination posting.
5. **Narration / payee / tags / flag / date**: see the user page; payee is set only when all splits share one
   non-placeholder counterpart; date is the minimum split date; `reconciled` requires all splits reconciled.
6. **Merge** (`_merge_postings`): postings with the same account and currency, no price and no metadata are
   summed, preserving first-seen order.
7. **Balance check**: `tx.balance()` must be all zeros or `ConversionError("ledger.err_unbalanced")`.
8. After all groups, `AccountResolver.raise_on_collisions()` then a stable sort by `sort_key`.

## Account resolution (`accounts.py`)

`AccountResolver.resolve(name, firefly_type, account_id, side)`:

1. `classify()` maps the Firefly account type string (`"Asset account"`, `"Expense account"`, `"Loan"`,
   `"Initial balance account"`, ...) to a kind; unknown types fall back to `expense` for destinations and
   `income` for sources.
2. Precedence: explicit `accounts` (by name or id) -> `investment_accounts` (asset kind only) -> opening /
   reconciliation / cash specials -> fallback (strict mode or empty/`(no name)`) -> `normalize_component()`.
3. Every result is recorded as `ledger account -> {(kind, firefly name): explicit?}`. A collision is a ledger
   account with more than one identity where at least one was **automatically** generated. Explicit many-to-one
   mapping is intentional and never reported.
4. Each decision is also stored as a `Resolution(name, firefly_type, kind, account, origin)`, origin being
   `explicit`, `investment`, `special`, `fallback` or `auto`. `resolutions()` feeds the scaffold and its table.

`normalize_component()`: transliterate letters NFKD cannot decompose (`ß ø æ œ đ ł`), NFKD + drop combining
marks, replace runs of `[^A-Za-z0-9]` by `-`, strip dashes, capitalise the first letter.

## Writer contract and the Beancount writer

```python
class LedgerWriter(Protocol):
    extension: str                                                      # ".beancount"
    def render(self, ledger, options) -> str: ...               # self-contained single file
    def render_accounts(self, ledger, options) -> str: ...      # commodity + open only
    def render_transactions(self, ledger, options) -> str: ...  # transactions only

@dataclass(frozen=True)
class WriterOptions:
    labels: LedgerLabels
    commodities: tuple[str, ...] = ()
    generated_at: datetime | None = None   # None -> no timestamp line
```

Every method returns a complete file (header included). `BeancountWriter.render()` is
`render_accounts()` + `render_transactions()` under one header: `commodity` directives, `open` directives, then each
transaction. Number alignment uses **per-file** column widths (deterministic, and a long new account name does
not rewrite closed years). Strings go through `quote()`
(escapes `\` and `"`, flattens newlines). Numbers go through `format_number()` (`format(d, "f")`: positional,
decimals preserved).

The `; Generated:` timestamp is written only where a rerun is expected to rewrite the file anyway:
`render_accounts()` and the single-file `render()`. `render_transactions()` (the per-year files) never carries it,
so unchanged years stay byte-identical and are not rewritten.

Determinism checklist for any writer: iterate only over sorted structures, never over `dict`/`set` order you did
not build deterministically, no locale-dependent formatting, no environment-dependent data except the optional
timestamp.

## i18n design

* Strings live under `[ledger]` in both `translations/en.toml` and `it.toml` (keys must match).
* `LedgerLabels.from_i18n(overrides)` snapshots the active language into an immutable object. Metadata keys are
  validated against `[a-z][a-zA-Z0-9_-]*` (a translation with an accented or capitalised key fails loudly, and a
  test checks both languages).
* Errors store a message key and parameters; `str(exc)` translates at display time. Add a key to **both** TOML
  files whenever you add a message.
* Technical keys (`firefly_id`, `firefly_group_id`) are constants of `LedgerLabels` and not translated.

## Config and CLI wiring

```mermaid
sequenceDiagram
    participant U as User
    participant M as main.main()
    participant C as ledger/cli.py
    participant Y as mapping.py
    participant FC as FireflyClient
    participant X as export.run_export()
    participant W as BeancountWriter
    U->>M: firefly-reports export beancount ...
    M->>M: load_config(), i18n.load(lang)
    M->>C: run_export_command(args, make_client, parse_date)
    C->>Y: load_ledger_config(map)
    C->>C: LedgerLabels.from_i18n(overrides)
    C->>M: make_client() (credentials chain)
    M-->>C: FireflyClient
    C->>X: run_export(client, request, labels)
    X->>FC: get_transactions(start, end)
    X->>X: build_ledger()
    X->>W: render(ledger, options)
    X->>X: atomic_write(), optional init / validate
    X-->>C: exit code
    C-->>U: messages (stderr) and exit status
```


* `ledger.cli.add_export_parser()` (called from `main.parse_args()`) registers `export <format>`; shared options (`--url --token --start --end --lang
  --out`) use `argparse.SUPPRESS` so values given before the subcommand are kept (argparse otherwise lets
  subparser defaults overwrite them).
* `main()` dispatches `export` right after `init` and before the `--year/--start/--end` report validation.
* `ledger.cli.run_export_command()` resolves the mapping path (`--map` > `./beancount_map.yaml`), builds labels,
  calls the injected `make_client()` (`main.cmd_export` builds it with the existing `_resolve_credentials()` and
  `FireflyClient`, so `ledger.cli` never imports `main`), and maps `LedgerError` / `requests.RequestException`
  to exit code 1.
* `FireflyClient.get_transactions(start=None, end=None, tx_type=None)`: omitted bounds are not sent.

## `run_export` step by step

```mermaid
flowchart TD
    A["run_export(request)"] --> B{"yearly layout and<br/>--start / --end?"}
    B -- yes --> X1["LedgerError err_yearly_filters"]
    B -- no --> C["get_transactions + build_ledger<br/>(collision check)"]
    C --> D["plan_files: name -> content<br/>everything rendered up front"]
    D --> E{"--dry-run?"}
    E -- yes --> F["print files (separators if several)<br/>optional validate on a temp copy"]
    E -- no --> G["per file: write only if the content changed<br/>(atomic_write)"]
    G --> H["warn about orphan generated files"]
    H --> I{"--init?"}
    I -- yes --> J["create main / investimenti / prices if absent"]
    I -- no --> K
    J --> K{"--validate?"}
    K -- yes --> L["bean-check: file (single)<br/>or aggregator include (yearly)"]
    K -- no --> M["exit 0"]
```

## Safety properties

* `atomic_write()`: temp file in the target directory, `os.replace`, mode of an existing target preserved
  (default 0644), temp file removed on failure. The previous file survives any error.
* `--init` creates `main.beancount` / `investimenti.beancount` / `prices.beancount` only when absent.
* `run_export` renders **every** file before writing the first one; unchanged files are not rewritten; files it did
  not produce are only reported (`find_orphans`), never deleted.
* The scaffold never writes into an existing mapping file.
* `validate.run_bean_check()` uses an argv list and the path from `shutil.which`; no shell.
* No tokens are written to any output or log by this code path.

## Adding a new format (hledger example)

1. Create `firefly_reports/ledger/writers/hledger.py`:
   ```python
   class HledgerWriter:
       def render(self, ledger: Ledger, options: WriterOptions) -> str:
           lines = [f"; {options.labels.header_notice}"]
           for tx in ledger.transactions:
               flag = "*" if tx.reconciled else "!"
               lines.append(f"{tx.date:%Y-%m-%d} {flag} {tx.payee or ''} | {tx.narration}")
               for p in tx.postings:
                   lines.append(f"    {p.account}  {p.amount.number} {p.amount.currency}"
                                + (f" @@ {p.price_total.number} {p.price_total.currency}" if p.price_total else ""))
           return "\n".join(lines) + "\n"
   ```
   (Illustrative only: hledger has different account-name rules, so also add its own normaliser or a
   `style` switch in `AccountResolver`, and its own escaping.)
2. Export it in `writers/__init__.py`.
3. Extend `FORMATS` in `ledger/cli.py` and select the writer in `run_export_command()` (pass it to
   `run_export(..., writer=HledgerWriter())`; `run_export` already accepts any `LedgerWriter`).
4. Add tests: unit tests for the writer, a determinism test, and an integration test guarded by
   `shutil.which("hledger")`.
5. Update the user page, README, CHANGELOG and AGENTS.md table.

`convert.py`, `model.py` and the Firefly client need no change. If the new format needs different account
rules, make them a parameter of `AccountResolver` rather than forking it.

## Tests

| File | Covers |
|---|---|
| `tests/test_ledger.py` | normalisation, resolver precedence and collisions, mapping validation, conversion (all transaction types, splits, foreign amounts), writer text/escaping/determinism, atomic write, i18n, export orchestration, `bean-check` integration |
| `tests/test_ledger_cli.py` | argument parsing, defaults, `--dry-run`, `--init`, mapping/language selection, error exits |
| `tests/test_ledger_layout.py` | yearly vs single layout (partition, determinism, no-op reruns, orphans), `bean-check` with the glob include, scaffold (draft validity, collisions, ambiguous names, existing mapping untouched), two-pass CLI flow |
| `tests/test_firefly_client.py` | optional `start`/`end` in `get_transactions` |
| `tests/fixtures/firefly_transactions.json` | API-shaped payload: opening balance, deposit, withdrawal, transfer, 3-split group, foreign amount (both directions), investment transfer, reconciliation, `(no name)`, cash account, liability, accented/quoted names |

`bean-check` based tests are skipped when the binary is missing (`pip install beancount` to run them).
