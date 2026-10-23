# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project overview

**firefly-reports** generates 26 financial reports (PDF + Excel) from a [Firefly III](https://www.firefly-iii.org/) instance, plus a Beancount ledger export, for individuals, freelancers and small businesses who want a complete annual financial overview.

- Language: Python >= 3.11 (CI runs 3.11 and 3.12)
- License: GPL-3.0-or-later
- Repository: https://github.com/fran33git/firefly-reports
- Packaging: setuptools (`pyproject.toml`); distribution `firefly-iii-reports`, import package `firefly_reports`, command `firefly-reports`. Dependencies are locked in `firefly_reports/requirements.txt` (pip-compile from `requirements.in`, caps on `numpy` and `contourpy` for Python 3.11)
- Runtime dependencies: `requests`, `reportlab` (PDF), `openpyxl` (Excel), `matplotlib` (charts), `python-dateutil`, `python-dotenv`, `pyyaml` (ledger mapping). Optional extra `beancount` (only for `--validate`)

## Architecture

The pipeline is strictly linear: **fetch -> build -> write**, driven by a registry of report packages.

```
firefly_client.py -> reports/fetch.py -> reports/<key>/build.py -> reports/<key>/pdf.py
                                                              -> reports/<key>/xlsx.py
```

Everything lives in `firefly_reports/` and is imported with package-qualified absolute imports (`from firefly_reports.reports.options import Period`). pytest resolves them through `pythonpath = ["."]`.

| Package / module | Role |
|---|---|
| `cli/` | The only place with `argparse`, `print`, `input`, `sys.exit`, `.env` and `./firefly-reports.toml`. `__init__.main(argv) -> int` and `build_parser()`; subcommands `report.py`, `export.py` (Beancount), `init.py`, `demo.py`; `_options.py` (credentials, dates, settings precedence), `_console.py` (progress lines, debug log), `_legacy.py` (the 1.x form without a subcommand), `config.py` |
| `api.py` | Provisional library facade: `connect`, `fetch_data`, `build_reports`, `write_reports`, `generate_reports`, `available_reports`. The CLI consumes it. Never prints or exits |
| `reports/` | `registry.py` (`REPORTS`: every `ReportSpec` in canonical order), `fetch.py` (`fetch_source_data`), `pipeline.py` (`build_all`, `plan_outputs`, `write_outputs`), `workbook.py`, `spec.py` (`ReportSpec`, `ReportContext`, `SourceData`, `FireflySource`), `options.py` (`Period`, `GlobalFilters`, `ReportOptions`), `events.py` (progress events), `filters.py`, `_money.py` (`_d`), `_labels.py` |
| `reports/<key>/` | One package per report (26 reports + the two dashboards `dashboard_income_expense` and `dashboard_kpi_trend`): `build.py` (pure, `Decimal`, `from_source` adapter), `pdf.py` (ReportLab), `xlsx.py` (openpyxl sheet, `write_sheet`) and `__init__.py` with `SPEC` |
| `render/` | What many reports share and that knows nothing about reports: `fmt.py` (number/date/period formats), `charts.py` (matplotlib object-oriented API, no `pyplot`), `pdf/` (palette, styles, page, tables, widgets), `xlsx/` (styles, layout) |
| `ledger/` | Plain-text-accounting export (`firefly-reports export beancount`): `convert.py` (Firefly splits -> neutral `model.py`, pure), `accounts.py`, `mapping.py` (YAML mapping), `mapfile.py` (safe textual edits of the mapping), `scaffold.py` (mapping draft), `labels.py` (i18n strings), `writers/` (`LedgerWriter` protocol, `BeancountWriter`, `atomic_write`), `validate.py` (optional `bean-check`), `export.py` (orchestration, `--init`) |
| `firefly_client.py` | `FireflyClient` wraps the Firefly III REST API; the only module (with `api.py` and `cli/`) that imports `requests` |
| `i18n.py` | `Translator` (frozen), process default set by `load(lang)`, per-thread/task override `using(lang)` (a `ContextVar`), `current()`, `t("pdf.category")` (falls back to `en`, then to the key) |
| `clock.py` | `now()`, `today()`, `frozen(at)`: the only way to read the time, so output can be deterministic |
| `errors.py` | `FireflyReportsError` (`ConfigurationError`, `FireflyAPIError`, `ReportError`; `ledger.errors.LedgerError` derives from it): a translation key plus parameters, rendered lazily |
| `demo/` | `data.py` (mock data), `client.py` (`DemoClient`, an offline `FireflySource`); `firefly-reports demo` runs the real pipeline on it |
| `main.py`, `demo/__main__.py` | Deprecated shims (`python -m firefly_reports.main`, `python -m firefly_reports.demo`), removed in 3.0 |
| `translations/` | `en.toml`, `it.toml` (output languages English and Italian): sections `[cli]`, `[errors]`, `[ledger]`, `[pdf]`, `[excel]` ... |

The old modules `data_processor`, `pdf_exporter`, `excel_exporter`, `chart_engine` and `config` were removed in 2.0 (internal, replaced by the packages above).

### Public surface and compatibility

- **Stable (semver):** the command line: commands, flags, exit codes, config keys, environment variables and output file names.
- **Provisional:** the names in `firefly_reports.__all__` (`api.py`). They may change in a minor release until declared stable.
- **Internal:** everything else (`reports`, `render`, `cli`, `ledger`, `firefly_client`, `i18n`, `clock`, `demo`).
- Deprecation: announce in release N.x (stderr warning for the CLI, `DeprecationWarning` for Python), keep for the rest of that major, remove in the next major. Deprecated in 2.0 and removed in 3.0: the command without a subcommand, the hidden root `--out/--start/--end`, `firefly_reports.main`, `python -m firefly_reports.demo`.

### Configuration precedence

Token/URL come from CLI flags (`--url`, `--token`), a `firefly-reports.toml` config file, env vars `FIREFLY_URL`/`FIREFLY_TOKEN` (a `.env` file feeds the environment), or an interactive prompt (token only). `cli/_options.resolve_report_settings` holds the precedence table for the other settings (CLI > config file > environment > default), pinned by `tests/cli/test_settings.py`. Every on/off setting has an explicit off on the command line (`--no-legacy-report`, `--no-fetch-links`, `--no-all-tags`, `--no-reconciled-only`, `--show-transfers`), so a `true` in the config file can be overridden; a range given with `--start/--end` wins over a `year` kept in the config file (`--year` together with a range is still an error). URL/token follow the same order (`resolve_credentials`; before 2.0 the environment beat the config file). `cli/config.py::KNOWN_KEYS` lists every key of `firefly-reports.toml` (including the `[export]` section: `out`, `layout`, `classify_by`, `map`, resolved by `cli/export.resolve_export_settings`); an unlisted key only produces a stderr warning with a suggestion. When the CLI reads a new key, add it to `KNOWN_KEYS` and to the commented template in `cli/init.py` (`test_init_template_lists_only_known_keys` guards the pair). See `.env.example` and `docs/wiki/Configuration.md`.

### Transaction type semantics

| Firefly type | Behaviour |
|---|---|
| `deposit` | Income (+) |
| `withdrawal` | Expense (−) |
| `transfer` | Shown in the register, neutral for cash flow |
| `opening balance` | Ignored in all reports |

### Exit codes

`0` success, `1` error (configuration, credentials, API, ledger), `2` usage error, a bare invocation with nothing to do, or `export --validate` without `bean-check` installed, `3` the run finished but some files failed, `130` interrupted. Errors, warnings and the failed-files summary go to stderr; results and progress lines go to stdout.

## Build and test commands

There is no compiled build step; it is a plain Python application. Use `python -m <tool>` for dev tools (the console scripts of a moved venv can have broken shebangs).

```bash
# Setup (Python 3.11 venv in .venv; match the lock so goldens agree with CI)
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r firefly_reports/requirements.txt -e ".[dev,beancount]" pyinstaller
pre-commit install

# Run against a real instance
python -m firefly_reports report --url https://firefly.example.com --year 2025 --owner "Your Name" --out ./output
# Or with built-in sample data (no Firefly III needed)
python -m firefly_reports demo --out ./output

# Local gate (all must pass before a commit)
python -m pytest tests -q --cov=firefly_reports --cov-fail-under=90
ruff check firefly_reports tests tools && ruff format --check firefly_reports tests tools
python -m mypy firefly_reports
python -m bandit -q -r firefly_reports -l -ii --exclude firefly_reports/.venv
python tools/ab_snapshot.py compare "$TMPDIR/ab/baseline"   # only while refactoring output code
pip-audit -r firefly_reports/requirements.txt

# Exe packaging smoke test (PyInstaller build + probes). Run before touching the exe build config.
./tools/test-exe.sh
```

## Code style guidelines

- Ruff: `line-length = 100`, target `py311`; lint rules `E, W, F, I, N, UP, B, SIM`; `E501` ignored. The only per-file ignore is `N806` for `reports/*/pdf.py` (ReportLab layout code uses `W`, `H`, `COL_W`): do not "fix" those.
- Ruff format is enforced in CI (`ruff format --check`).
- mypy is strict everywhere (`disallow_untyped_defs`, `warn_return_any`, no relaxed modules). Missing-import stubs ignored for `reportlab`, `openpyxl`, `matplotlib`, `dateutil`.
- Use package-qualified absolute imports.
- Monetary values are always `Decimal` (2 decimal places) produced via `_d()` (`reports/_money.py`) — never raw floats for money.
- No 3.12-only syntax or APIs (the floor is 3.11).

### Layering rules (enforced by `tests/test_architecture.py`)

- Builders (`reports/*/build.py`, `_money`, `_labels`, `filters`, `options`, `spec`) do zero I/O: they import none of `reportlab`, `openpyxl`, `matplotlib`, `requests`, `os`, `pathlib`, `io`, `render`, `cli`.
- `render/` imports neither `reports`, `api`, `cli` nor `ledger`; `ledger/` imports none of `reports`, `render`, `cli`, `api`.
- `requests` is imported only by `firefly_client.py`, `api.py` and `cli/`. Nothing outside `cli/`, `main.py` and `demo/__main__.py` imports `cli`.
- `print`, `input` and `sys.exit` live in `cli/` only (grandfathered: `ledger/export.py`).
- No `importlib` / `__import__`: PyInstaller follows static imports only (the registry imports every report package explicitly).

## Testing instructions

- Framework: pytest (with `pytest-cov`; CI enforces `--cov-fail-under=90`). Config in `pyproject.toml` (`testpaths = ["tests"]`, marker `golden`).
- Run from the repo root with plain pytest (`pythonpath = ["."]`): `python -m pytest tests -q`.
- Tests must not require a live Firefly III instance: use `DemoClient` (`firefly_reports/demo/client.py`) or the `responses` library. An autouse fixture in `conftest.py` refuses every socket `connect()`, so a test that escapes its mock fails instead of reaching a real instance. `conftest.py` loads English translations per test (`i18n.load("en")`).
- **Golden tests** (`tests/golden/`, marker `golden`) pin the output of the builders, the PDF documents (flowable tree, strings, page count), the workbook cells, the CLI pipeline stdout, the `--help` texts and the Beancount export. Regenerate on purpose with `FIREFLY_UPDATE_GOLDEN=1 python -m pytest -m golden` and name the reason in the commit message. They depend on the dependency versions of the lock: generate them in a venv built from `requirements.txt`.
- `tools/ab_snapshot.py write|compare DIR` is a local-only byte-level A/B check of the PDFs (ReportLab `invariant` mode and a frozen clock) used while refactoring output code; it is not a test.
- Ledger tests (`tests/test_ledger*.py`) use `tests/fixtures/firefly_transactions.json` (plus `firefly_account_types.json`); the `bean-check` integration tests need `beancount` (CI installs it; install it locally so they run).
- `tests/test_packaging.py::test_wheel_contents` builds the wheel with `FIREFLY_BUILD_WHEEL=1`.

## Ledger export (Beancount)

- Entry point: `firefly-reports export beancount` (parser and runner in `firefly_reports/cli/export.py`; logic in `firefly_reports/ledger/`).
- Layering is strict: `convert.py` (pure) -> `model.py` -> `writers/*` (pure, no `i18n` calls; they receive `LedgerLabels`). Only `export.py`, `validate.py`, `writers/base.atomic_write` and `mapping.load_ledger_config` do I/O.
- A new output format = a new `LedgerWriter` (`extension`, `render`, `render_accounts`, `render_transactions`) plus a CLI choice; do not fork `convert.py`.
- Layouts (`yearly` default, `single`) are built by `export.plan_files()`; everything is rendered before any file is written, unchanged files are not rewritten and orphans are only reported. `--scaffold` never writes ledger files.
- Expense/income accounts come from the Firefly **category** by default (`--classify-by category`; `account` keeps the counterpart accounts). `convert._split_postings` picks the real account and the counterpart per split; the counterpart then lives in `payee`. Transfers and any transaction with two real sides keep a `category` metadata instead of a category account.
- Two passes: `--scaffold` drafts `beancount_map.yaml` (accounts, `categories:` with split counts). On an existing mapping it only prints the missing entries, unless `--append` (inserts them via `mapfile.append_entries`, `.bak` copy) or `--overwrite` (regenerates after the user types the file name, never when stdin is not interactive). The export is blocked (exit 1, nothing written) without a mapping file or with categories it does not list, unless `--allow-unmapped`.
- Beyond the core postings the writer emits `^firefly-link-<id>` links, fixed-key metadata (`bill`, `reference`, `external_id`, `external_url`, `book_date`, `interest_date`), `iban` on `open` directives and always the `*` flag. `main.beancount` declares the output language with a Fava `custom "fava-option" "language"` directive (Beancount rejects unknown `option` lines).
- Errors are `LedgerError(message_key, **params)` with keys in the `[ledger]` section of both translation files.
- Output must stay deterministic (sorted, no dict/set order reliance) and `Decimal`-only; adding a transaction shape means extending `tests/fixtures/firefly_transactions.json`.
- Docs: `docs/wiki/Beancount-Export.md` (user) and `docs/wiki/Ledger-Architecture.md` (developer); keep both and `beancount_map.example.yaml` in sync with behaviour changes.

## Adding a new report

1. Create `reports/<key>/` with `__init__.py` (the `SPEC`), `build.py` (a pure `build_<key>()` returning a plain dict, plus the `from_source(src, ctx, built)` adapter), `pdf.py` (`render_<key>_pdf(data, path, legacy=False)`) and, if it has a sheet, `xlsx.py` (`write_sheet(wb, data)`). Copy a small existing package (for example `reports/savings_goals/`).
2. Add one line to `REPORTS` in `reports/registry.py` (the order is the Excel sheet order, then the other reports, then the views; a report must come after the ones it `depends_on`) and the package name to the import list there.
3. Add the strings to **both** `translations/en.toml` and `translations/it.toml`.
4. Extend the demo data if the report needs a shape it lacks (`demo/data.py`) and add the report's unit tests (builder, PDF, sheet) next to the existing ones in `tests/test_data_processor.py`, `tests/test_pdf_exporter.py` and `tests/test_excel_exporter.py`, or in a new `tests/reports/test_<key>.py`.
5. Update what counts the reports by hand: `tests/reports/test_registry.py`, `tests/test_api.py`, `tests/cli/test_demo.py`, `tests/reports/test_pipeline.py`, `tests/test_golden_pipeline.py`; the entries of `tests/golden/harness.py` (`build_demo_suite`, `DEMO_PDFS`); and the PDF count (`27`) in the exe probe of `.github/workflows/ci.yml`.
6. Regenerate the goldens (`FIREFLY_UPDATE_GOLDEN=1 python -m pytest -m golden`) and review the diff.
7. Update the user docs (`docs/wiki/Reports-Reference.md`, README, CHANGELOG).

## CI and deployment

- GitHub Actions (`.github/workflows/ci.yml`) runs on pushes to `main`/`develop` and on all PRs: ruff lint + format check (package, tests, tools), mypy, pytest matrix on Python 3.11/3.12 with the coverage threshold, `pip-audit`, `bandit`, and the Windows exe smoke test (PyInstaller build from `firefly_reports/__main__.py`, translation, legacy-form, `--version` and offline `demo` probes).
- Pre-commit hooks (`.pre-commit-config.yaml`) run ruff (with `--fix`), ruff-format, and mypy on commit.
- Release workflow (`.github/workflows/release.yml`): pushing a tag `v*` checks the tag matches the package version, runs tests, builds the sdist/wheel, publishes to PyPI via OIDC Trusted Publishing (configure the Trusted Publisher on pypi.org), builds a standalone Windows executable with PyInstaller, and creates a GitHub Release. The PyPI distribution is named `firefly-iii-reports` (`firefly-reports` was already taken by an unrelated project); the import package stays `firefly_reports` and the CLI command `firefly-reports`.
- Wiki sync workflow (`.github/workflows/wiki-sync.yml`): a push to `main` touching `docs/wiki/**` pushes the pages to the GitHub Wiki repository automatically.

## Git identity

Commits in this repository are authored as the GitHub account: name `fran33git`, an address under `users.noreply.github.com` (the `<id>+fran33git@users.noreply.github.com` form listed under GitHub > Settings > Emails). Never use a personal address or another name, and do not override `user.name`/`user.email` to get around this. Check with `git config user.name` before the first commit of a session. `bash tools/check-identity.sh` (no argument: the next commit; `BASE..HEAD`: a range) is run by CI on the maintainer's pull requests. The name on commits made on github.com (merges) comes from the GitHub profile name, so it must be `fran33git` too. Co-author trailers are not covered by the rule.

## Security considerations

- **Never commit tokens.** The Firefly III Personal Access Token comes from `FIREFLY_TOKEN`, `.env`, or `firefly-reports.toml`; `.env` is gitignored (see `.env.example`). The deprecation hint of the legacy command form masks `--token`.
- Bandit runs in CI (no exclusions except the Windows venv); `pip-audit` audits `firefly_reports/requirements.txt`.
- Do not introduce network calls outside `firefly_client.py`; keep mock/test data offline.

## Documentation

Full user/developer documentation mirrors the GitHub Wiki under `docs/wiki/` (Installation, Configuration, Reports Reference, Architecture, Testing, Troubleshooting, Adding a New Report, Contributing). `docs/wiki/` is the single source of truth — edit pages only there; the `wiki-sync` workflow pushes them to the GitHub Wiki automatically. Keep `README.md`, `CONTRIBUTING.md`, `CLAUDE.md`, and the wiki files in sync when changing workflows or report lists. (The wiki pages still describe the 1.x module layout and commands until the documentation is migrated; the code and this file are authoritative.)
