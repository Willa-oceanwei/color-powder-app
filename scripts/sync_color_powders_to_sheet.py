#!/usr/bin/env python3
"""Preflight or deliver queued Turso color-powder edits to Google Sheets."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.database import DatabaseConfig, database_config_from_secrets
from utils.sheet_export import sync_color_powder_outbox
from utils.sheet_import import read_worksheet_values_with_retry


def open_spreadsheet(secrets_path: Path, sheet_url: str):
    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(secrets_path.read_text(encoding="utf-8"))
    if "gcp" in info and "gcp_service_account" in info["gcp"]:
        info = json.loads(info["gcp"]["gcp_service_account"])
    credentials = Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"],
    )
    return gspread.authorize(credentials).open_by_url(sheet_url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials-json", required=True)
    parser.add_argument("--sheet-url", required=True)
    parser.add_argument("--db", help="Use local SQLite instead of configured Turso.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write safe pending entries. Without this flag the command is read-only.",
    )
    args = parser.parse_args()
    config = (
        DatabaseConfig(backend="sqlite", path=Path(args.db))
        if args.db
        else database_config_from_secrets()
    )
    worksheet = open_spreadsheet(Path(args.credentials_json), args.sheet_url).worksheet("色粉管理")
    result = sync_color_powder_outbox(
        worksheet,
        read_worksheet_values_with_retry(worksheet),
        db_config=config,
        dry_run=not args.apply,
    )
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.ok else 2)


if __name__ == "__main__":
    main()
