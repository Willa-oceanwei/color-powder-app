#!/usr/bin/env python3
"""Run controlled Google Sheets to Turso preflight or apply."""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.database import database_config_from_secrets
from utils.inbound_worker import INBOUND_SHEETS, run_controlled_inbound_worker


def open_spreadsheet(credentials_json: str, sheet_url: str):
    import gspread
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_info(
        json.loads(credentials_json),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(credentials).open_by_url(sheet_url)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-changes", type=int, default=25)
    parser.add_argument("--sheets", nargs="+", choices=INBOUND_SHEETS)
    parser.add_argument("--report-path")
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply only after a fresh safe preflight. Default is read-only.",
    )
    args = parser.parse_args()
    credentials_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "").strip()
    if not credentials_json or not sheet_url:
        parser.error("GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_URL are required")

    result = run_controlled_inbound_worker(
        open_spreadsheet(credentials_json, sheet_url),
        db_config=database_config_from_secrets(),
        dry_run=not args.apply,
        sheet_names=args.sheets,
        max_changes=args.max_changes,
    )
    report = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    print(report)
    if args.report_path:
        path = Path(args.report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report + "\n", encoding="utf-8")
    raise SystemExit(0 if result.ok else 2)


if __name__ == "__main__":
    main()
