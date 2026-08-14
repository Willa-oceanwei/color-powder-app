#!/usr/bin/env python3
"""Safe Google Sheets -> configured SQLite-compatible database import command."""

import argparse
import json
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from utils.database import DatabaseConfig, database_config_from_secrets
from utils.sheet_import import import_worksheets


def open_spreadsheet(secrets_path: Path, sheet_url: str):
    info = json.loads(secrets_path.read_text(encoding="utf-8"))
    if "gcp" in info and "gcp_service_account" in info["gcp"]:
        info = json.loads(info["gcp"]["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    return gspread.authorize(creds).open_by_url(sheet_url)


def main():
    parser = argparse.ArgumentParser(description="Copy Google Sheets data into Turso or local SQLite without modifying Sheets.")
    parser.add_argument("--credentials-json", required=True, help="Service account JSON file, or JSON containing Streamlit gcp_service_account.")
    parser.add_argument("--sheet-url", required=True, help="Existing Google Sheets URL.")
    parser.add_argument(
        "--db",
        help="Force a local SQLite database path. If omitted, TURSO_DATABASE_URL and TURSO_AUTH_TOKEN select Turso.",
    )
    parser.add_argument("--sheets", nargs="*", help="Worksheet names to import. Defaults to known system sheets.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count changes without writing imported rows to the selected database.",
    )
    args = parser.parse_args()

    config = (
        DatabaseConfig(backend="sqlite", path=Path(args.db))
        if args.db
        else database_config_from_secrets()
    )
    print(f"Database backend: {config.backend}")
    spreadsheet = open_spreadsheet(Path(args.credentials_json), args.sheet_url)
    results = import_worksheets(
        spreadsheet,
        sheet_names=args.sheets,
        db_config=config,
        dry_run=args.dry_run,
    )
    for result in results:
        status = "OK" if result.ok else "CHECK"
        mode = "DRY-RUN" if result.dry_run else "WRITE"
        print(f"[{status}][{mode}] {result.sheet_name}: Google Sheets={result.sheet_rows}, SQLite={result.sqlite_rows}, insert={result.to_insert}, update={result.to_update}, unchanged={result.unchanged}, written={result.inserted_or_updated}, errors={len(result.errors)}, duplicates={len(result.duplicate_ids)}, conflicts={result.conflicts}, inventory_duplicate_risk={result.inventory_duplicate_risk}")
        for error in result.errors[:10]:
            print(f"  error: {error}")
        for duplicate in result.duplicate_ids[:10]:
            print(f"  duplicate: {duplicate}")
        for warning in result.warnings[:10]:
            print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
