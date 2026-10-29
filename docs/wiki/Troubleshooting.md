# Troubleshooting

This page helps users diagnose the most common problems with firefly-reports: credential and connection
errors, configuration messages, deprecation warnings, files that fail to generate, empty reports, and how
to collect a debug log. Errors are printed on stderr, prefixed with `Error:`, in the output language; the
exit codes are listed in [[Configuration]].

## Authentication errors

**Symptom:** `Error: Firefly III request failed: 401 Client Error: Unauthorized ...` (exit code `1`).

- The token is incorrect or expired: create a new Personal Access Token in Firefly III (Profile -> OAuth).
- A stale token is configured somewhere else: the first value found wins, in the order command line,
  `firefly-reports.toml`, environment (`FIREFLY_TOKEN`, `.env`). Since 2.0 a token in
  `firefly-reports.toml` beats one in the environment. See [[Configuration]].
- Leading or trailing whitespace is stripped automatically.

## Missing or invalid URL and token

| Message | Fix |
|---|---|
| `Error: Firefly III URL is required. ...` | Pass `--url`, set `FIREFLY_URL`, or add `url` to `firefly-reports.toml` |
| `Error: invalid Firefly III URL '...'. It must include the scheme, ...` | Use the full base URL, e.g. `https://firefly.example.com` |
| `Error: token is required. ...` | Pass `--token`, set `FIREFLY_TOKEN`, add it to `.env` or `firefly-reports.toml`. The interactive prompt is only offered when the terminal is interactive (not in cron or CI) |

## Connection errors

**Symptom:** `Error: Firefly III request failed: HTTPConnectionPool(...) ... Connection refused` or a
timeout (exit code `1`).

- Firefly III is unreachable from this machine: check the network, VPN or firewall.
- Wrong base URL: it must point to the root of the instance (e.g. `https://firefly.example.com`), not to a
  sub-path.
- TLS certificate errors: a self-signed certificate must be trusted by the Python `requests` library of
  the machine running the tool (for example `REQUESTS_CA_BUNDLE=/path/to/ca.pem`). `--trust-insecure-ssl`
  also works but turns off **all** certificate verification.

## Refusing to connect: untrusted CA

**Symptom:** `Error: refusing to connect to <host>: its certificate chain contains '<CA>' (...). No request was sent on this connection.` (exit code 1)

**Cause:** the certificate chain of your Firefly III server contains a CA key on the internal blocklist: a key known to be compromised (for example the eMudhra intermediates of October 2026, including their Sectigo cross-signed certificates). The check runs right after the TLS handshake, so your token was **not** sent.

**Fix:** get a certificate for your instance from another CA (for example Let's Encrypt). `--trust-insecure-ssl` bypasses the check, but it also turns off every other certificate check, so use it only for a server you control and on a network you trust.

## Warnings about the certificate chain

- `... contains '<CA>', a CA under review` → the chain includes a CA that browsers and root programs are reviewing. The connection continues; plan to move to another CA.
- `... could not be checked against the CA lists (<reason>)` → this Python or proxy does not let the tool read the verified chain, or the TLS session was resumed. The standard certificate verification still applied. If it persists, run with `--debug` and look for the `TLS chain for ...` lines in the log.
- `--trust-insecure-ssl is active` → verification is off; remove the flag as soon as you can.

Lists ship with each release: an older installation or executable does not know about newer incidents, so keep the tool up to date.

## Period and date errors

| Message | Fix |
|---|---|
| `Error: provide --year YYYY (full year, all reports) or both --start and --end.` | Give a period, or set `year` in `firefly-reports.toml` |
| `Error: use either --year or --start/--end, not both.` | Choose one form. A `year` key in `firefly-reports.toml` counts as `--year`: remove it to run a custom range |
| `Error: invalid date for --start: '...' (expected format YYYY-MM-DD).` | Use ISO dates |
| `Error: --start (...) must not be after --end (...).` | Swap the dates |
| `Error: invalid fiscal year start '...' (expected MM-DD).` | Fix `--fiscal-year-start` or `[filters] fiscal_year_start` |

## Configuration file messages

- `Config error: firefly-reports.toml is malformed — <details>`: the file is not valid TOML; the
  details give the line and column. Exit code `1`.
- `Warning: unknown key 'x' in firefly-reports.toml is ignored. Did you mean 'y'?`: a key that nothing
  reads, usually a typo. The run continues; fix the key name. The supported keys are listed in
  [[Configuration]].
- `Error: Config error: export.layout must be one of yearly, single (got '...').`: an invalid value in the
  `[export]` section.

## Deprecation warnings

- `Warning: running reports without a subcommand is deprecated and will stop working in firefly-reports 3.0. Use: firefly-reports report ...`:
  the 1.x form (`firefly-reports --year 2025 ...`) still runs the reports. Use the command shown (the token
  is masked in it). A bare `firefly-reports` also runs the reports this way when `year` is set in
  `firefly-reports.toml`.
- `Warning: 'python -m firefly_reports.main' is deprecated ...` (or `firefly_reports.demo`): use
  `firefly-reports` or `python -m firefly_reports` with a command (`report`, `demo`).

## Some files failed

**Symptom:** a `FAIL <file>: <error>` line during generation, then `[!] N files failed: ...` and exit code
`3`.

The other files were written normally; one failing report never stops the run. Rerun with `--debug` and
look for the traceback of that file in the debug log (see below).

## Rate limiting with `--fetch-links`

**Symptom:** the deep-fetch phase is very slow, or the log shows `Rate limited (429)`.

`--fetch-links` fetches each linked transaction individually with a delay between requests (default
0.2 seconds, `--link-delay` or `[reports] link_delay`):

```bash
# Faster (only for local or LAN instances without a rate limit)
firefly-reports report --year 2025 --fetch-links --link-delay 0.05

# Slower (remote instances, or when hitting HTTP 429)
firefly-reports report --year 2025 --fetch-links --link-delay 0.5
```

On HTTP 429 the client retries once, after the `Retry-After` delay (or twice the configured delay).

## Empty or zero-value reports

**Symptom:** a report PDF is blank or shows only zeros.

- The period has no transactions: check `--year` or `--start`/`--end` against your data.
- A filter removes everything: check `--accounts-include`, `--categories-include`, `--reconciled-only` and
  the `[filters]` section of `firefly-reports.toml`. The console shows
  `-> global filters: N -> M transactions` when filters are active.
- Transaction types: `deposit` counts as income, `withdrawal` as expense, `transfer` is neutral and
  `opening balance` is ignored. Check that your transactions are typed correctly in Firefly III.
- Tax Summary shows every expense as non-deductible: add `deductible_keywords` to the `[tax]` section of
  `firefly-reports.toml` (a warning about it is printed at the start of the run).
- A report is missing altogether: some reports exist only in year mode, only with a flag, or not in
  legacy mode; see [[Reports-Reference|Reports Reference]].

## Using `--debug`

The debug log records the API calls, the pagination, timings and summary values:

```bash
firefly-reports report --year 2025 --debug
# [*] Debug log: /path/to/output/debug_<timestamp>.log

firefly-reports report --year 2025 --debug --debug-file "$HOME/firefly-debug.log"
```

The log includes each API endpoint called with its HTTP status and size, the pages fetched per endpoint,
the time spent on each PDF and on the workbook, the cash-flow and KPI summary values, warnings such as rate
limiting, and the full traceback of any file that failed. The command-line arguments are logged with the
token masked, and bearer tokens are redacted from logged messages.

## Beancount export

Problems with `firefly-reports export beancount` (missing mapping file, unmapped categories, account
collisions, `--scaffold` TODO lines, yearly layout and date filters, leftover files, invalid mapping file,
`bean-check` errors, exit codes) are covered in the troubleshooting table of
[[Beancount-Export|Beancount Export]]. The authentication, connection and rate-limit sections above apply
to it unchanged (it prints `Request to Firefly III failed: ...` and exits with code `1`).

## Compatibility

Tested against Firefly III v6.x through the v1 REST API (`/api/v1/`). Firefly III v5.x may work but is
not supported.
