#!/usr/bin/env python3
"""Open, update, or resolve one deduplicated GitHub Issue for a sync workflow."""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from typing import Any


API_ROOT = "https://api.github.com"


def _request(
    path: str,
    *,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "color-powder-sync-alert",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read()
    return json.loads(body) if body else None


def _open_alert_issue(repo: str, title: str, *, token: str) -> dict[str, Any] | None:
    page = 1
    while page <= 5:
        issues = _request(
            f"/repos/{repo}/issues?state=open&per_page=100&page={page}", token=token
        )
        for issue in issues:
            if "pull_request" not in issue and issue.get("title") == title:
                return issue
        if len(issues) < 100:
            return None
        page += 1
    return None


def update_sync_alert(
    *, repo: str, workflow: str, status: str, run_url: str, token: str
) -> str:
    title = f"[Sync Alert] {workflow} failed"
    issue = _open_alert_issue(repo, title, token=token)
    if status == "failure":
        message = (
            f"The sync workflow failed and requires manual review.\n\n"
            f"Run: {run_url}\n\n"
            "Do not bypass conflict/error checks with a manual apply."
        )
        if issue is None:
            created = _request(
                f"/repos/{repo}/issues",
                token=token,
                method="POST",
                payload={"title": title, "body": message},
            )
            return f"opened issue #{created['number']}"
        _request(
            f"/repos/{repo}/issues/{issue['number']}/comments",
            token=token,
            method="POST",
            payload={"body": f"Another failure occurred.\n\nRun: {run_url}"},
        )
        return f"updated issue #{issue['number']}"

    if issue is None:
        return "no open alert issue"
    _request(
        f"/repos/{repo}/issues/{issue['number']}/comments",
        token=token,
        method="POST",
        payload={"body": f"A later workflow run succeeded.\n\nRun: {run_url}"},
    )
    _request(
        f"/repos/{repo}/issues/{issue['number']}",
        token=token,
        method="PATCH",
        payload={"state": "closed"},
    )
    return f"resolved issue #{issue['number']}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", choices=("success", "failure"), required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-url", required=True)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repo:
        parser.error("GITHUB_TOKEN and GITHUB_REPOSITORY are required")
    print(update_sync_alert(
        repo=repo, workflow=args.workflow, status=args.status,
        run_url=args.run_url, token=token,
    ))


if __name__ == "__main__":
    main()
