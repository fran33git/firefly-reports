# Security Policy

## Supported versions

firefly-reports is distributed as source only (no packaged releases yet).
Security fixes are made against the latest commit on `main`; there is no
older version receiving patches.

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Instead, use [GitHub Security Advisories](https://github.com/fran33git/firefly-reports/security/advisories/new)
to report privately. Include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (a minimal example is ideal)
- The affected file(s)/function(s), if known

You should receive an initial response within a few days. This is a
solo-maintained open-source project — no guaranteed SLA, but reports are
taken seriously and fixed as soon as practical.

## Scope

firefly-reports is a local CLI tool: it reads data from a Firefly III
instance you control and writes PDF/Excel files to your local filesystem.
It does not run a server and does not send data to any third party.
Relevant security topics for this project include:

- Handling of the Firefly III Personal Access Token (credential storage,
  redaction in logs, `.env`/TOML file handling)
- Generated file output (PDF/Excel) — e.g. injection via crafted
  transaction descriptions, categories, or tags
- Dependency vulnerabilities (tracked via `pip-audit` in CI)

Issues in Firefly III itself (the server your token connects to) should be
reported to the [Firefly III project](https://github.com/firefly-iii/firefly-iii/security), not here.
