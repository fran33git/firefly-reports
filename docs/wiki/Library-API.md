# Library API

The `firefly_reports` package exposes a small Python facade on top of the pipeline described in
[[Architecture]]. It lets an application connect to a Firefly III instance, fetch the data, build
the reports and write the PDFs and the Excel workbook without going through the command line.
**The facade is provisional in 2.x:** the names and signatures listed here may change in a minor
release until they are declared stable. The stable contract is the `firefly-reports` command
line; everything not exported from the package is internal and may change without notice. The
facade never prints and never exits the process: progress comes through an optional callback and
failures are exceptions or entries of `ReportResult.failures`.

## Functions

All functions are importable directly from `firefly_reports` (the package loads them lazily, so
`import firefly_reports` stays cheap).

| Function | Does |
|---|---|
| `connect(url, token, *, request_delay=0.2, logger=None)` | Creates a Firefly III API client (`FireflySource`) from a base URL and a Personal Access Token. |
| `fetch_data(source, period, options, *, progress=None)` | Downloads everything the reports need and returns one immutable `SourceData`; API failures raise `FireflyAPIError`. |
| `build_reports(data, period, options)` | Builds every applicable report into plain dicts (money as `Decimal`). Pure: no files, no network. |
| `write_reports(built, period, options, out_dir, *, progress=None)` | Writes the PDFs and the workbook to `out_dir`; a file that fails lands in `result.failures`. |
| `generate_reports(source, period, options, out_dir, *, progress=None)` | `fetch_data` + `build_reports` + `write_reports` in one call. |
| `available_reports()` | Returns one `ReportInfo` per registered report: its key, the formats it produces (`pdf`, `xlsx`), whether it needs year mode and whether it applies in standard or legacy mode. |

## Data types

| Name | Role |
|---|---|
| `Period` | The reporting period: `Period.for_year(2025)` or `Period.between(start, end)`. |
| `ReportOptions` | Owner, currency, language, tags, filters, output switches; `GlobalFilters` holds the account/category/transfer filters. |
| `FireflySource` | The protocol a data source implements; `connect` returns the real client, `firefly_reports.demo.client.DemoClient` an offline one. |
| `SourceData` | Everything fetched for a run, passed to `build_reports`. |
| `ReportResult` | What `write_reports`/`generate_reports` return: `files` (generated), `failures` (failed), `headline` (the summary figures), `ok`. |
| `Headline` | `total_in`, `total_out`, `net`, `transactions`, `savings_rate`, `cash_runway`. |
| `ReportInfo` | Key, `formats`, `requires_year` and `mode` (`any`, `standard`, `legacy`) of one report. |
| `GeneratedFile`, `FailedFile` | One output file each: the path, and for failures also the reason. |

## Errors

Every failure of the facade raises a subclass of `FireflyReportsError`:

| Exception | Raised when |
|---|---|
| `ConfigurationError` | Invalid year, fiscal start, dates, URL, credentials or configuration. |
| `FireflyAPIError` | The Firefly III API cannot be reached or answers with an error. |
| `ReportError` | A report cannot be built (the report key is in the params). |
| `UntrustedChainError` | The certificate chain of the server contains a blocked CA key; raised before any request is sent (the token is not sent). |

`connect()` also takes `trust_insecure_ssl` (turns certificate verification and the CA lists off) and
`on_notice`, a callable that receives a `TrustNotice` (a warning-level CA, a chain that could not be
checked, or the insecure mode). Without a callback the notices become `TrustWarning` (a `UserWarning`)
through `warnings`; the library never prints.

The exception message is rendered lazily in the language active when it is shown, so it follows
the caller, not the raise site.

## A complete offline example

The demo client serves the built-in sample data, so the whole pipeline runs without a Firefly III
instance (this is also how the test suite exercises it, see [[Testing]]):

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from firefly_reports import (
    Period,
    ReportOptions,
    available_reports,
    generate_reports,
)
from firefly_reports.demo.client import DemoClient

source = DemoClient()
period = Period.for_year(2025)
options = ReportOptions(owner="Ada Lovelace", tags=("consulting", "travel"), all_tags=True)

with TemporaryDirectory() as tmp:
    result = generate_reports(source, period, options, Path(tmp))
    print("ok:", result.ok)
    print("files:", len(result.files))
    print("failures:", len(result.failures))
    h = result.headline
    print("income:", h.total_in, "| expenses:", h.total_out, "| net:", h.net)
    print("transactions:", h.transactions, "| savings rate:", h.savings_rate, "| runway:", h.cash_runway)

infos = available_reports()
print("registered reports:", len(infos))
first = infos[0]
print("first:", first.key, sorted(first.formats), first.requires_year, first.mode)
```

Output of a run (deterministic, from the frozen demo data):

```text
ok: True
files: 28
failures: 0
income: 17150.00 | expenses: 5598.08 | net: 11551.92
transactions: 30 | savings rate: 67.4 | runway: 18.5
registered reports: 28
first: cash_flow ['pdf', 'xlsx'] False any
```

## Stability

- **Provisional:** every name in `firefly_reports.__all__` may change in a minor release until the
  maintainer declares the API stable. Pin the version and read the changelog before upgrading.
- **Stable:** the command line (commands, flags, exit codes, config keys, output file names).
- **Internal:** everything else (`reports`, `render`, `cli`, `ledger`, `firefly_client`, `i18n`,
  `clock`, `demo`), including the structure of the report data dicts.
