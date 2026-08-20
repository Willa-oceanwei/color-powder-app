#!/usr/bin/env python3
"""Run one bounded, delete-free Turso-to-Sheets worker pass."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.database import database_config_from_secrets
from utils.sync_worker import run_safe_worker


def open_spreadsheet(credentials_json: str, sheet_url: str):
    import gspread
    from google.oauth2.service_account import Credentials

    info = json.loads(credentials_json)
    credentials = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(credentials).open_by_url(sheet_url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument(
        "--apply", action="store_true",
        help="Write safe insert/update events. The default is a read-only dry-run.",
    )
    args = parser.parse_args()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if not credentials_json or not sheet_url:
        parser.error("GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_URL are required")
    result = run_safe_worker(
        open_spreadsheet(credentials_json, sheet_url),
        db_config=database_config_from_secrets(),
        dry_run=not args.apply,
        batch_size=args.batch_size,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.ok else 2)


if __name__ == "__main__":
    main()
