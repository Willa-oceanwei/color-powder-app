#!/usr/bin/env python3
"""備份 color-powder-app 的程式碼與 Git 歷史。"""

import argparse
import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory
from time import time
from urllib.error import URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZIP_STORED, ZipFile

REPOSITORY = "https://github.com/Willa-oceanwei/color-powder-app.git"
TAIPEI = timezone(timedelta(hours=8))
PROJECT = "color-powder-app"
MAX_BACKUP_BYTES = 25 * 1024 * 1024


def upload_to_drive(path, url, key):
    if path.stat().st_size > MAX_BACKUP_BYTES:
        raise ValueError("ZIP exceeds the 25 MiB upload limit.")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    timestamp = int(time())
    signed = f"{path.name}\n{timestamp}\n{digest}".encode()
    payload = json.dumps({
        "name": path.name,
        "timestamp": timestamp,
        "sha256": digest,
        "signature": hmac.new(key.encode(), signed, hashlib.sha256).hexdigest(),
        "data": base64.b64encode(data).decode("ascii"),
    }).encode()
    request = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=360) as response:
            receipt = json.loads(response.read(16384))
    except (URLError, TimeoutError, ValueError) as error:
        raise ValueError("Google did not return a valid upload receipt.") from error
    if (
        not isinstance(receipt, dict)
        or receipt.get("ok") is not True
        or receipt.get("name") != path.name
        or receipt.get("size") != len(data)
        or receipt.get("sha256") != digest
        or not isinstance(receipt.get("id"), str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", receipt["id"])
    ):
        raise ValueError("Google Drive upload or checksum verification failed.")
    return receipt["id"]


def git(*args, capture=False):
    result = subprocess.run(
        ["git", *map(str, args)],
        check=True,
        stdout=subprocess.PIPE if capture else None,
        timeout=600,
    )
    return result.stdout.decode("utf-8").strip() if capture else None


def build_backup(workspace):
    repository = workspace / "source.git"
    archive_path = workspace / "backup.zip"
    bundle = workspace / f"{PROJECT}.bundle"

    git("clone", "--quiet", "--bare", "--", REPOSITORY, repository)
    branch = git("-C", repository, "symbolic-ref", "--short", "HEAD", capture=True)
    commit = git("-C", repository, "rev-parse", "HEAD", capture=True)
    git("-C", repository, "bundle", "create", bundle, "HEAD", "--all")
    git("-C", repository, "bundle", "verify", "--quiet", bundle)

    git(
        "-C", repository, "archive", "--format=zip", f"--prefix={PROJECT}/",
        f"--output={archive_path}", commit,
    )
    metadata = (
        f"Repository: {REPOSITORY}\n"
        f"Default branch: {branch}\n"
        f"Commit: {commit}\n"
        f"Backed up at: {datetime.now(TAIPEI).isoformat(timespec='seconds')}\n"
        f"Git restore: git clone {PROJECT}.bundle {PROJECT}-restored\n"
        "For all backed-up branch refs and tags, add --mirror after git clone.\n"
        "Scope: tracked GitHub source and Git history. Live databases and hosted "
        "credentials/settings are outside this archive.\n"
    )
    with ZipFile(archive_path, "a", compression=ZIP_STORED) as archive:
        archive.write(bundle, bundle.name)
        archive.writestr("backup-info.txt", metadata)
    return archive_path, commit


def write_to_destination(archive_path, destination, commit):
    timestamp = datetime.now(TAIPEI).strftime("%Y%m%d-%H%M%S-%f")
    final_path = destination / f"{PROJECT}-backup-{timestamp}-{commit[:12]}.zip"
    # Copy under a temporary name. Only expose the final ZIP name after it passes CRC checks.
    with NamedTemporaryFile(
        prefix=f".{PROJECT}-", suffix=".part", dir=destination, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        shutil.copyfile(archive_path, temporary_path)
        with ZipFile(temporary_path) as archive:
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                raise BadZipFile(f"檔案校驗失敗：{corrupt_member}")
        os.replace(temporary_path, final_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return final_path


def main():
    parser = argparse.ArgumentParser(
        description="從 GitHub 下載程式及 Git 歷史，備份到現有資料夾。"
    )
    parser.add_argument("destination", type=Path, help="備份 ZIP 的暫存資料夾")
    parser.add_argument("--upload", action="store_true", help="上傳到 Google Drive")
    args = parser.parse_args()
    destination = args.destination.expanduser()
    if not destination.is_dir():
        parser.error(f"找不到備份資料夾：{destination}")
    if shutil.which("git") is None:
        parser.error("找不到 Git。請安裝 Git 並確認 git --version 可以執行。")
    if args.upload:
        url = os.getenv("BACKUP_UPLOAD_URL", "")
        key = os.getenv("BACKUP_UPLOAD_KEY", "")
        if not re.fullmatch(r"https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec", url):
            parser.error("BACKUP_UPLOAD_URL 必須是已部署的 Apps Script /exec 網址。")
        if len(key) < 32:
            parser.error("BACKUP_UPLOAD_KEY 需要至少 32 個字元。")

    try:
        with TemporaryDirectory(prefix=f"{PROJECT}-") as temporary:
            archive, commit = build_backup(Path(temporary))
            backup_path = write_to_destination(archive, destination, commit)
        if args.upload:
            file_id = upload_to_drive(backup_path, url, key)
            print(f"Google Drive 備份已校驗：{backup_path.name} ({file_id})")
    except (OSError, subprocess.SubprocessError, BadZipFile, ValueError) as error:
        print(f"備份失敗：{error}", file=sys.stderr)
        return 1
    print(f"備份已寫入：{backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
