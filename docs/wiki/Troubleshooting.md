# Troubleshooting

## Authentication errors

**Symptom:** `HTTP 401 Unauthorized` or `requests.exceptions.HTTPError: 401`

**Causes and fixes:**

- Token is incorrect or expired → regenerate the PAT in Firefly III (Profile → OAuth).
- Token has leading or trailing whitespace → check the value in your `.env` or `firefly-reports.toml`. The tool strips whitespace automatically, but check older configs.
- Wrong URL → confirm the URL matches your Firefly III instance (including scheme: `https://`).

---

## Connection errors

**Symptom:** `requests.exceptions.ConnectionError` or `requests.exceptions.Timeout`

**Causes and fixes:**

- Firefly III is unreachable from the machine running this tool → check network/VPN/firewall.
- Wrong base URL → the URL must point to the root of the instance (e.g. `https://firefly.example.com`), not to a sub-path.
- SSL certificate error → if your instance uses a self-signed certificate, trust it properly (`REQUESTS_CA_BUNDLE=/path/to/ca.pem`). `--trust-insecure-ssl` also works but turns off **all** certificate verification.

---

## Refusing to connect: untrusted CA

**Symptom:** `Error: refusing to connect to <host>: its certificate chain contains '<CA>' (...). Nothing was sent.` (exit code 1)

**Cause:** the certificate chain of your Firefly III server contains a CA key on the internal blocklist: a key known to be compromised (for example the eMudhra intermediates of October 2026, including their Sectigo cross-signed certificates). The check runs right after the TLS handshake, so your token was **not** sent.

**Fix:** get a certificate for your instance from another CA (for example Let's Encrypt). `--trust-insecure-ssl` bypasses the check, but it also turns off every other certificate check, so use it only for a server you control and on a network you trust.

## Warnings about the certificate chain

- `... contains '<CA>', a CA under review` → the chain includes a CA that browsers and root programs are reviewing. The connection continues; plan to move to another CA.
- `... could not be checked against the CA lists (<reason>)` → this Python or proxy does not let the tool read the verified chain, or the TLS session was resumed. The standard certificate verification still applied. If it persists, run with `--debug` and look for the `TLS chain for ...` lines in the log.
- `--trust-insecure-ssl is active` → verification is off; remove the flag as soon as you can.

Lists ship with each release: an older installation or executable does not know about newer incidents, so keep the tool up to date.

---

## Rate limiting with `--fetch-links`

**Symptom:** The deep-fetch phase is very slow, or `requests.exceptions.HTTPError: 429`

The `--fetch-links` flag fetches each linked transaction individually with a delay between requests. The default delay is 0.2 seconds.

**Tune the delay:**

```bash
# Faster (only for local/LAN instances with no rate limit)
firefly-reports ... --fetch-links --link-delay 0.05

# Slower (for remote instances or when hitting 429 errors)
firefly-reports ... --fetch-links --link-delay 0.5
```

On HTTP 429, the tool automatically retries once using the `Retry-After` header value (or double the current delay). Failed transactions are skipped and counted; a summary is logged at the end.

---

## Empty or zero-value reports

**Symptom:** A report PDF is blank or shows all zeros.

**Causes and fixes:**

- Date range has no transactions → verify `--year` or `--start` and `--end` match a period with data in Firefly III.
- Transaction types not matching → the tool uses Firefly III transaction types: `deposit` (income), `withdrawal` (expense), `transfer` (neutral). Check that your Firefly III transactions are correctly typed.
- Tax Summary shows all non-deductible → add `deductible_keywords` to the `[tax]` section of `firefly-reports.toml`.

---

## Using `--debug`

Enable the debug log to capture the full HTTP request/response cycle, timing per report, and data summaries:

```bash
firefly-reports ... --debug
# Writes: output/debug_20250523_143022.log

# Or specify the log path:
firefly-reports ... --debug --debug-file /tmp/firefly-debug.log
```

The log includes:
- Each API endpoint called and its response status + size
- Pagination: pages fetched per endpoint
- Timing per report (fetch, processing, PDF render)
- Cash flow and KPI summary values
- Deep-fetch progress (if `--fetch-links` is active)

**Security:** The debug log never writes the token in plain text. The `Authorization` header is always redacted.

---

## Beancount export

Problems with `firefly-reports export beancount` (account collisions, `--scaffold` TODO lines, yearly layout and date filters,
leftover files, invalid mapping file, `bean-check` errors, exit codes) are listed in the
[Beancount Export troubleshooting table](Beancount-Export#troubleshooting). Authentication, connection and
rate-limit errors above apply to it unchanged (it prints `Request to Firefly III failed: ...` and exits 1).

---

## Compatibility

Tested against Firefly III v6.x. The tool uses the v1 REST API (`/api/v1/`). Firefly III v5.x may work but is not officially supported.
