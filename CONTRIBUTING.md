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

## Full developer documentation

See the [GitHub Wiki](https://github.com/fran33git/firefly-reports/wiki):

- [Architecture](https://github.com/fran33git/firefly-reports/wiki/Architecture)
- [Adding a New Report](https://github.com/fran33git/firefly-reports/wiki/Adding-a-New-Report)
- [Testing](https://github.com/fran33git/firefly-reports/wiki/Testing)
- [Contributing Guide](https://github.com/fran33git/firefly-reports/wiki/Contributing) — code style, commit messages, PR checklist
