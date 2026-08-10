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
- SSL certificate error → if your instance uses a self-signed certificate, you may need to configure requests to trust it.

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

## Compatibility

Tested against Firefly III v6.x. The tool uses the v1 REST API (`/api/v1/`). Firefly III v5.x may work but is not officially supported.
