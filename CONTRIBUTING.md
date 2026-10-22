# Contributing

## Development setup

```bash
git clone https://github.com/fran33git/firefly-reports.git
cd firefly-reports
pip install -e ".[dev]"
pre-commit install
```

## Running tests

```bash
PYTHONPATH=firefly_reports pytest tests/ -v
PYTHONPATH=firefly_reports pytest tests/ --cov=firefly_reports --cov-report=term-missing
```

## Linting and type checking

```bash
ruff check firefly_reports/
mypy firefly_reports/
```

Both run automatically on `git commit` via pre-commit.

To also run the Beancount export integration tests (they call `bean-check` and are skipped otherwise):

```bash
pip install beancount
pytest tests/test_ledger.py tests/test_ledger_cli.py -v
```

Design notes for the export: wiki page *Ledger Architecture* (`docs/wiki/Ledger-Architecture.md`).

## Full developer documentation

See the [GitHub Wiki](https://github.com/fran33git/firefly-reports/wiki):

- [Architecture](https://github.com/fran33git/firefly-reports/wiki/Architecture)
- [Adding a New Report](https://github.com/fran33git/firefly-reports/wiki/Adding-a-New-Report)
- [Testing](https://github.com/fran33git/firefly-reports/wiki/Testing)
- [Contributing Guide](https://github.com/fran33git/firefly-reports/wiki/Contributing) — code style, commit messages, PR checklist
