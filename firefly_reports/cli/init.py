"""``init`` subcommand: interactive creation of ./firefly-reports.toml."""

import getpass
import os
from pathlib import Path


def run_init() -> None:
    """Generate ./firefly-reports.toml interactively."""
    config_path = Path("./firefly-reports.toml")

    if config_path.exists():
        answer = input("Config file already exists. Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted. Existing config unchanged.")
            return

    print("Firefly Reports — Config Setup")
    print("(Press Enter to keep the shown default)\n")

    url = input("URL [https://firefly.example.com]: ").strip()
    if not url:
        url = "https://firefly.example.com"

    token = getpass.getpass("Token (leave blank to enter at runtime): ").strip()

    owner = input("Owner name []: ").strip()

    currency = input("Currency symbol [€]: ").strip()
    if not currency:
        currency = "€"

    lang = input("Language [en/it, default en]: ").strip().lower()
    if lang not in ("en", "it"):
        lang = "en"

    legacy_report = input("Use legacy report styles? [y/N]: ").strip().lower() == "y"

    out = input("Output directory [./output]: ").strip()
    if not out:
        out = "./output"

    tags_raw = input("Tags for tagged report (comma-separated) []: ").strip()
    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

    lines = [
        "# firefly-reports.toml",
        "# WARNING: do not commit this file if it contains a token.",
        "# Ensure firefly-reports.toml is listed in your .gitignore.",
        "",
        f'url      = "{url}"',
    ]
    if token:
        lines.append(f'token    = "{token}"')
    else:
        lines.append('# token = ""  # leave blank to be prompted at runtime')
    lines += [
        f'owner    = "{owner}"',
        f'currency = "{currency}"',
        f'lang     = "{lang}"',
        f"legacy_report = {'true' if legacy_report else 'false'}",
        f'out      = "{out}"',
    ]
    if tags:
        tags_toml = ", ".join(f'"{tag}"' for tag in tags)
        lines.append(f"tags     = [{tags_toml}]")
    else:
        lines.append("tags     = []")

    content = "\n".join(lines) + "\n"
    if token:
        # Create atomically with owner-only permissions before any bytes
        # are written, so the token is never briefly world/group-readable
        # (same convention as ~/.netrc or ~/.pgpass). Also re-applied via
        # fchmod in case a stale, more permissive file already existed.
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        config_path.write_text(content, encoding="utf-8")
    print(f"\nConfig written to {config_path.resolve()}")

    if token:
        gitignore = Path(".gitignore")
        covered = False
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            covered = any(
                line.strip() in ("firefly-reports.toml", "*.toml")
                for line in content.splitlines()
                if not line.startswith("#")
            )
        if not covered:
            print(
                "\nWARNING: 'firefly-reports.toml' contains a token but is not "
                "listed in .gitignore.\n"
                "         Add the following line to .gitignore to prevent "
                "accidental commits:\n"
                "         firefly-reports.toml"
            )
